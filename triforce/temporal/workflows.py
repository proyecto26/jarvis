"""Temporal Workflows for durable Trinity execution.

Three workflows:
- AwakeWorkflow: Durable ReAct loop for user interactions
- DreamWorkflow: Scheduled Dreamer cycles with breakthrough detection
- ConsolidationWorkflow: Nightly memory consolidation

Requires: temporalio
Install with: pip install jarvis-triforce[temporal]
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from types import SimpleNamespace
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# How often the run_consolidation activity heartbeats. Must be comfortably
# below the workflow's heartbeat_timeout (30s) so healthy long-running LLM
# work is never killed.
_CONSOLIDATION_HEARTBEAT_SECONDS = 10

# ---------------------------------------------------------------------------
# Workflow input/output data classes (always importable)
# ---------------------------------------------------------------------------


@dataclass
class AwakeWorkflowInput:
    """Input for the AwakeWorkflow."""

    user_message: str = ""
    system_instruction: str = ""
    model: str = "gemini-3.5-flash"
    max_iterations: int = 20


@dataclass
class AwakeWorkflowResult:
    """Result from the AwakeWorkflow."""

    response_text: str = ""
    tool_calls_made: int = 0
    iterations: int = 0


@dataclass
class DreamWorkflowInput:
    """Input for the DreamWorkflow.

    ``dreamer_model`` / ``judge_model`` default to ``None`` and are resolved to
    ``Config.DREAMER_MODEL`` / ``Config.JUDGE_MODEL`` inside ``run()`` so the
    DREAMER_MODEL / JUDGE_MODEL env overrides are honored. Config cannot be read
    at class-definition time inside the Temporal workflow sandbox, so the
    resolution is deferred to ``run()`` (where Config is passed through). Passing
    an explicit id still overrides the env default.
    """

    dreamer_model: Optional[str] = None
    judge_model: Optional[str] = None
    max_iterations: int = 8


@dataclass
class DreamWorkflowResult:
    """Result from the DreamWorkflow."""

    breakthrough: bool = False
    breakthrough_insight: str = ""
    iterations: int = 0
    seeds_generated: int = 0
    # Best idea produced this cycle — the last Dreamer seed text. A cycle that
    # ends on max-iterations still surfaces its work instead of discarding
    # everything.
    final_idea: str = ""


# ---------------------------------------------------------------------------
# Consolidation + reflection tool handlers (always importable — no temporalio)
# ---------------------------------------------------------------------------


def check_reflection_due_activity() -> dict:
    """Tool handler: is an importance-triggered reflection due?

    Consults the journal's persistent importance accumulator (Stanford
    generative-agents pattern). The nightly schedule remains the fallback
    trigger — this only surfaces early-reflection pressure.
    """
    from triforce.memory import journal

    return {
        "reflection_due": journal.check_reflection_due(),
        "accumulated": journal.accumulated_importance(),
    }


def reset_accumulator_activity(consumed: int | None = None) -> dict:
    """Tool handler: reset the importance accumulator after a reflection ran.

    ``consumed`` is the accumulated importance the caller observed when it
    decided a reflection was due; only that much is subtracted so importance
    accrued while the (long) consolidation ran is never silently discarded.
    When ``consumed`` is omitted the accumulator is zeroed.
    """
    from triforce.memory import journal

    journal.reset_accumulator(consumed=consumed)
    return {"status": "reset"}


def _temporal_heartbeat() -> Optional[Callable[[], None]]:
    """Return ``activity.heartbeat`` when running inside a Temporal activity."""
    try:
        from temporalio import activity

        if activity.in_activity():
            return activity.heartbeat
    except ImportError:
        pass
    return None


async def run_consolidation_activity() -> dict:
    """Tool handler: run the full nightly consolidation pipeline.

    The pipeline can spend minutes in LLM calls, so while it runs a
    background task heartbeats every ``_CONSOLIDATION_HEARTBEAT_SECONDS`` —
    keeping the workflow's ``heartbeat_timeout`` a dead-worker detector
    instead of a killer of healthy long-running work. Outside a Temporal
    activity context (direct calls, tests) heartbeating is skipped.
    """
    from triforce.memory.consolidation import ConsolidationWorker

    heartbeat = _temporal_heartbeat()

    async def _beat() -> None:
        while True:
            heartbeat()  # type: ignore[misc]
            await asyncio.sleep(_CONSOLIDATION_HEARTBEAT_SECONDS)

    beat_task = asyncio.create_task(_beat()) if heartbeat is not None else None
    try:
        return await ConsolidationWorker().run_nightly()
    finally:
        if beat_task is not None:
            beat_task.cancel()


# ---------------------------------------------------------------------------
# Executor tool adapters (always importable — real tools imported lazily)
# ---------------------------------------------------------------------------
#
# The Executor's ADK tools take an injected ``tool_context: ToolContext`` that
# only exists inside an ADK runner. Inside a Temporal activity there is no ADK
# session, so each tool is registered as a thin *adapter* with a model-facing
# signature (which yields a clean schema for FunctionDeclaration.from_callable
# and matches the args Gemini emits) that injects a lightweight shim context at
# call time. The real tool modules are imported lazily so this module keeps
# importing without google-adk installed.

# Executor tools offered to Gemini during the Awake ReAct loop. Each name is a
# registry key the dynamic activity dispatches on.
EXECUTOR_TOOL_NAMES: list[str] = [
    "recall_episodic",
    "check_belief_conflict",
    "reinforce_memory",
    "write_journal_entry",
    "append_to_state",
]


class _ShimToolContext:
    """Minimal stand-in for ADK's ToolContext outside an ADK runner.

    Exposes ``state`` (a plain-dict scratchpad) and ``actions`` — the only
    attributes the Executor's memory/journal/state tools touch. The scratchpad
    is NOT durable: every dynamic-tool dispatch is a fresh Temporal activity, so
    it lives for that one call only. The durable conversation is the workflow's
    ``contents`` / ``dream_context``, never ADK session state.
    """

    def __init__(self) -> None:
        self.state: dict[str, Any] = {}
        self.actions = SimpleNamespace(escalate=False)


def recall_episodic_tool(query: str) -> dict:
    """Recall past experiences similar to a natural-language query."""
    from triforce.tools.memory_tools import recall_episodic

    return recall_episodic(query, _ShimToolContext())


def check_belief_conflict_tool(belief_a: str, belief_b: str) -> dict:
    """Check whether two beliefs potentially contradict each other."""
    from triforce.tools.memory_tools import check_belief_conflict

    return check_belief_conflict(belief_a, belief_b, _ShimToolContext())


def reinforce_memory_tool(entry_date: str) -> dict:
    """Reinforce an episodic memory, resetting its decay clock."""
    from triforce.tools.memory_tools import reinforce_memory

    return reinforce_memory(entry_date, _ShimToolContext())


def write_journal_entry_tool(section: str, content: str) -> dict:
    """Append an entry to a section of today's journal."""
    from triforce.tools.journal_tools import write_journal_entry

    return write_journal_entry(section, content, _ShimToolContext())


def append_to_state_tool(key: str, value: str) -> dict:
    """Append a value to a list key in scratch state, or set a scalar key."""
    from triforce.tools.state_tools import append_to_state

    return append_to_state(key, value, _ShimToolContext())


# Adapter name -> (module to probe for availability, adapter callable).
_EXECUTOR_TOOL_ADAPTERS: dict[str, tuple[str, Callable[..., dict]]] = {
    "recall_episodic": ("triforce.tools.memory_tools", recall_episodic_tool),
    "check_belief_conflict": ("triforce.tools.memory_tools", check_belief_conflict_tool),
    "reinforce_memory": ("triforce.tools.memory_tools", reinforce_memory_tool),
    "write_journal_entry": ("triforce.tools.journal_tools", write_journal_entry_tool),
    "append_to_state": ("triforce.tools.state_tools", append_to_state_tool),
}


def _detect_breakthrough(text: str) -> bool:
    """Heuristic breakthrough detector for the Dreamer/Judge collaborator loop.

    Still string-based on purpose — in the durable path the Judge emits
    free-form text, not a structured tool call — but it matches a few
    affirmative markers instead of a single exact JSON literal, so it is a
    little less brittle. A fully robust version would have the Judge emit a
    structured ``breakthrough`` field (tool/JSON schema) and parse that.
    """
    if not text:
        return False
    haystack = text.lower()
    markers = (
        '"breakthrough": true',
        '"breakthrough":true',
        "breakthrough detected",
        "breakthrough confirmed",
        "breakthrough achieved",
    )
    return any(marker in haystack for marker in markers)


def _register_tool_handlers() -> None:
    """Register tool handlers for dynamic activity dispatch.

    The consolidation / reflection handlers have no optional dependencies and
    are always registered. The Executor tool adapters are imported lazily and
    guarded — each pulls in ``google-adk``; if that (or a tool module) is
    unavailable the adapter is logged and skipped so this module still loads
    and the durable ReAct loop simply offers fewer tools.
    """
    from triforce.temporal.activities import register_tool

    register_tool("check_reflection_due", check_reflection_due_activity)
    register_tool("reset_accumulator", reset_accumulator_activity)
    register_tool("run_consolidation", run_consolidation_activity)

    import importlib

    for name, (module_path, adapter) in _EXECUTOR_TOOL_ADAPTERS.items():
        try:
            importlib.import_module(module_path)
        except Exception as exc:  # noqa: BLE001 — optional dep; degrade gracefully
            logger.warning(
                "Executor tool %r unavailable (%s) — skipping registration",
                name,
                exc,
            )
            continue
        register_tool(name, adapter)


_register_tool_handlers()


# ---------------------------------------------------------------------------
# Temporal Workflows (guarded import)
# ---------------------------------------------------------------------------

try:
    from temporalio import workflow
    from temporalio.common import RetryPolicy

    with workflow.unsafe.imports_passed_through():
        from triforce.temporal.activities import (
            GeminiChatRequest,
            GeminiChatResponse,
            generate_content,
            dynamic_tool_activity,
        )
        from triforce.config import Config

    # Real Trinity prompts for the Dream cycle. Imported through the sandbox
    # passthrough so the workflow uses the true prompts at runtime, but guarded
    # independently of the outer temporalio guard: importing them pulls in the
    # agents package (which builds ADK Agent objects and needs google-adk). If
    # that is unavailable we fall back to concise role prompts rather than
    # disabling every workflow — the Dream cycle still runs, and the Awake /
    # Consolidation workflows are wholly unaffected.
    _DREAMER_SYSTEM_PROMPT = (
        "You are the Dreamer — the subconscious of Jarvis. Operate without "
        "feasibility filters: generate ideas freely, associate wildly, connect "
        "distant concepts, and explore the edges of the possible. Each cycle, "
        "produce 3-5 specific new seeds, connections, or 'what-if' scenarios; "
        "vague dreams do not lead to breakthroughs."
    )
    _JUDGE_COLLABORATOR_PROMPT = (
        "You are the Judge in Collaborator Mode — not a filter but a connector. "
        "Deepen the Dreamer's seeds by linking them to past experience and known "
        "patterns; ask where you have seen something like this before. A "
        "breakthrough is a REFRAME, not merely a good idea — call one out only "
        "when something familiar suddenly looks completely different or two "
        "unconnected things reveal a deep structural similarity."
    )
    try:
        with workflow.unsafe.imports_passed_through():
            from triforce.agents.dreamer.prompts import (
                DREAMER_INSTRUCTION as _DREAMER_SYSTEM_PROMPT,
            )
            from triforce.agents.judge.prompts import (
                COLLABORATOR_PROMPT as _JUDGE_COLLABORATOR_PROMPT,
            )
    except Exception as exc:  # noqa: BLE001 — agents package import side effects
        logger.warning(
            "Real Dream prompts unavailable (%s) — using fallback role prompts",
            exc,
        )

    # A permanent error (bad request, validation, wrong type) must fail the
    # workflow fast instead of retrying unbounded — the core "spins forever"
    # fix. Transient / infrastructure errors still get a few attempts. Applied
    # to every generate_content call and to tool dispatch (where an
    # unregistered tool name surfaces as a non-retryable ValueError).
    _RETRY_POLICY = RetryPolicy(
        maximum_attempts=3,
        non_retryable_error_types=["ValueError", "ValidationError", "TypeError"],
    )

    @workflow.defn
    class AwakeWorkflow:
        """Durable ReAct agentic loop for user interactions.

        Each Gemini call and tool invocation is a separate durable Activity.
        On crash after N tool calls, worker restart resumes from Activity N+1
        without re-executing completed activities.
        """

        @workflow.run
        async def run(self, input: AwakeWorkflowInput) -> AwakeWorkflowResult:
            """Execute the durable ReAct loop."""
            contents: list[dict[str, Any]] = [
                {"role": "user", "parts": [{"text": input.user_message}]}
            ]
            tool_calls_made = 0
            iterations = 0

            for _ in range(input.max_iterations):
                iterations += 1

                # LLM call as durable activity. Offer the Executor's real tools
                # by name so a function call dispatches to a registered handler
                # instead of raising.
                request = GeminiChatRequest(
                    model=input.model,
                    system_instruction=input.system_instruction,
                    contents=contents,
                    tool_names=EXECUTOR_TOOL_NAMES,
                )
                response: GeminiChatResponse = await workflow.execute_activity(
                    generate_content,
                    request,
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=_RETRY_POLICY,
                )

                # If no function calls, we have the final response.
                if not response.function_calls:
                    # Persist the exchange before returning — a text-only turn
                    # otherwise leaves no trace in the journal.
                    await self._journal_exchange(input.user_message, response.text)
                    return AwakeWorkflowResult(
                        response_text=response.text,
                        tool_calls_made=tool_calls_made,
                        iterations=iterations,
                    )

                # Append assistant response to contents.
                contents.append({
                    "role": "model",
                    "parts": response.raw_parts,
                })

                # Execute each tool call as a separate durable activity.
                tool_results = []
                for fc in response.function_calls:
                    # Invoked by name string — unregistered activity types are
                    # routed to dynamic_tool_activity on the worker. The bounded
                    # retry policy makes a bad/unregistered tool name (a
                    # ValueError from the dispatcher) fail fast instead of
                    # retrying forever.
                    result = await workflow.execute_activity(
                        fc["name"],
                        args=[fc.get("args", {})],
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=_RETRY_POLICY,
                    )
                    tool_calls_made += 1
                    tool_results.append({
                        "function_response": {
                            "name": fc["name"],
                            "response": result,
                        }
                    })

                # Append tool results to contents.
                contents.append({
                    "role": "user",
                    "parts": tool_results,
                })

            return AwakeWorkflowResult(
                response_text="Max iterations reached",
                tool_calls_made=tool_calls_made,
                iterations=iterations,
            )

        async def _journal_exchange(
            self, user_message: str, response_text: str
        ) -> None:
            """Persist a completed awake exchange to today's journal.

            Routed through the same durable ``write_journal_entry`` tool path
            (section ``executions``). A journal failure must never sink an
            already-computed response, so the activity is bounded by
            ``_RETRY_POLICY`` and any error is swallowed after logging.
            """
            content = json.dumps({
                "action": f"Responded to: {user_message[:200]}",
                "status": "completed",
                "outcome": response_text[:4000],
            })
            try:
                await workflow.execute_activity(
                    "write_journal_entry",
                    args=[{"section": "executions", "content": content}],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=_RETRY_POLICY,
                )
            except Exception:  # noqa: BLE001 — persistence is best-effort
                workflow.logger.warning(
                    "Awake exchange journal write failed — response returned anyway",
                    exc_info=True,
                )

    @workflow.defn
    class DreamWorkflow:
        """Scheduled Dreamer cycle with breakthrough detection.

        Triggered by Temporal Schedule every 6 hours (configurable).
        Loops Dreamer→Judge-collaborator until breakthrough or max iterations.
        """

        @workflow.run
        async def run(self, input: DreamWorkflowInput) -> DreamWorkflowResult:
            """Execute a dream cycle."""
            # Resolve models here (not at class-def time) so the DREAMER_MODEL /
            # JUDGE_MODEL env overrides apply. Config is passed through the
            # sandbox; these attributes are constants set once at import.
            dreamer_model = input.dreamer_model or Config.DREAMER_MODEL
            judge_model = input.judge_model or Config.JUDGE_MODEL

            seeds_generated = 0
            last_idea = ""
            dream_context: list[dict[str, Any]] = []

            for iteration in range(input.max_iterations):
                # Dreamer generates ideas.
                dreamer_request = GeminiChatRequest(
                    model=dreamer_model,
                    system_instruction=_DREAMER_SYSTEM_PROMPT,
                    contents=dream_context + [
                        {"role": "user", "parts": [{"text": "Generate new dream seeds."}]}
                    ],
                )
                dreamer_response: GeminiChatResponse = await workflow.execute_activity(
                    generate_content,
                    dreamer_request,
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=_RETRY_POLICY,
                )
                seeds_generated += 1
                if dreamer_response.text:
                    last_idea = dreamer_response.text

                # Judge evaluates for breakthrough.
                judge_request = GeminiChatRequest(
                    model=judge_model,
                    system_instruction=_JUDGE_COLLABORATOR_PROMPT,
                    contents=[
                        {"role": "user", "parts": [{"text": dreamer_response.text}]}
                    ],
                )
                judge_response: GeminiChatResponse = await workflow.execute_activity(
                    generate_content,
                    judge_request,
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=_RETRY_POLICY,
                )

                # Check for breakthrough signal in Judge response.
                if _detect_breakthrough(judge_response.text):
                    return DreamWorkflowResult(
                        breakthrough=True,
                        breakthrough_insight=judge_response.text,
                        iterations=iteration + 1,
                        seeds_generated=seeds_generated,
                        final_idea=last_idea,
                    )

                # Add to dream context for next iteration.
                dream_context.append(
                    {"role": "model", "parts": [{"text": dreamer_response.text}]}
                )

            # No breakthrough — return the best (last) idea rather than
            # discarding a cycle's worth of generation.
            return DreamWorkflowResult(
                breakthrough=False,
                iterations=input.max_iterations,
                seeds_generated=seeds_generated,
                final_idea=last_idea,
            )

    @workflow.defn
    class ConsolidationWorkflow:
        """Nightly memory consolidation workflow.

        Wraps ConsolidationWorker.run_nightly() as a durable workflow
        with heartbeating for long-running consolidation tasks.

        Before consolidating, consults the importance accumulator
        (check_reflection_due) so an importance-triggered reflection is
        acknowledged and the accumulator is reset once consolidation ran.
        The nightly schedule remains the fallback trigger — accumulator
        failures degrade gracefully and never block consolidation.
        """

        @workflow.run
        async def run(self) -> dict:
            """Execute nightly consolidation as a single activity."""
            reflection_due = False
            observed_importance = 0
            try:
                check = await workflow.execute_activity(
                    "check_reflection_due",
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )
                reflection_due = bool(check.get("reflection_due"))
                observed_importance = int(check.get("accumulated", 0))
            except Exception:
                # Accumulator unavailable — the schedule is the trigger.
                reflection_due = False

            result = await workflow.execute_activity(
                "run_consolidation",
                start_to_close_timeout=timedelta(minutes=10),
                heartbeat_timeout=timedelta(seconds=30),
            )

            if reflection_due:
                try:
                    # Subtract only the importance observed BEFORE the (long)
                    # consolidation activity — weight accrued while it ran
                    # must survive the reset (no check-then-reset lost update).
                    await workflow.execute_activity(
                        "reset_accumulator",
                        args=[{"consumed": observed_importance}],
                        start_to_close_timeout=timedelta(seconds=10),
                        retry_policy=RetryPolicy(maximum_attempts=2),
                    )
                except Exception:
                    pass  # Next run re-checks; the accumulator only grows.

            if isinstance(result, dict):
                result["reflection_due"] = reflection_due
            return result

    logger.info("Temporal workflows registered successfully")

except ImportError:
    logger.info(
        "temporalio not installed — Temporal workflows unavailable. "
        "Install with: pip install jarvis-triforce[temporal]"
    )

    class AwakeWorkflow:
        """Stub — temporalio not installed."""
        async def run(self, input: AwakeWorkflowInput) -> AwakeWorkflowResult:
            raise NotImplementedError("Requires temporalio")

    class DreamWorkflow:
        """Stub — temporalio not installed."""
        async def run(self, input: DreamWorkflowInput) -> DreamWorkflowResult:
            raise NotImplementedError("Requires temporalio")

    class ConsolidationWorkflow:
        """Stub — temporalio not installed."""
        async def run(self) -> dict:
            raise NotImplementedError("Requires temporalio")
