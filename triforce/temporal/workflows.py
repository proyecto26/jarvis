"""Temporal Workflows for durable Trinity execution.

Three workflows:
- AwakeWorkflow: Durable ReAct loop for user interactions
- DreamWorkflow: Scheduled Dreamer cycles with breakthrough detection
- ConsolidationWorkflow: Nightly memory consolidation

Requires: temporalio
Install with: pip install jarvis-triforce[temporal]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Workflow input/output data classes (always importable)
# ---------------------------------------------------------------------------


@dataclass
class AwakeWorkflowInput:
    """Input for the AwakeWorkflow."""

    user_message: str = ""
    system_instruction: str = ""
    model: str = "gemini-2.0-flash"
    max_iterations: int = 20


@dataclass
class AwakeWorkflowResult:
    """Result from the AwakeWorkflow."""

    response_text: str = ""
    tool_calls_made: int = 0
    iterations: int = 0


@dataclass
class DreamWorkflowInput:
    """Input for the DreamWorkflow."""

    dreamer_model: str = "gemini-2.0-pro-exp"
    judge_model: str = "gemini-1.5-pro"
    max_iterations: int = 8


@dataclass
class DreamWorkflowResult:
    """Result from the DreamWorkflow."""

    breakthrough: bool = False
    breakthrough_insight: str = ""
    iterations: int = 0
    seeds_generated: int = 0


# ---------------------------------------------------------------------------
# Temporal Workflows (guarded import)
# ---------------------------------------------------------------------------

try:
    from temporalio import workflow

    with workflow.unsafe.imports_passed_through():
        from triforce.temporal.activities import (
            GeminiChatRequest,
            GeminiChatResponse,
            generate_content,
            dynamic_tool_activity,
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

                # LLM call as durable activity
                request = GeminiChatRequest(
                    model=input.model,
                    system_instruction=input.system_instruction,
                    contents=contents,
                )
                response: GeminiChatResponse = await workflow.execute_activity(
                    generate_content,
                    request,
                    start_to_close_timeout=timedelta(seconds=60),
                )

                # If no function calls, we have the final response
                if not response.function_calls:
                    return AwakeWorkflowResult(
                        response_text=response.text,
                        tool_calls_made=tool_calls_made,
                        iterations=iterations,
                    )

                # Append assistant response to contents
                contents.append({
                    "role": "model",
                    "parts": response.raw_parts,
                })

                # Execute each tool call as a separate durable activity
                tool_results = []
                for fc in response.function_calls:
                    result = await workflow.execute_activity(
                        dynamic_tool_activity,
                        args=[fc["name"], [fc.get("args", {})]],
                        start_to_close_timeout=timedelta(seconds=30),
                    )
                    tool_calls_made += 1
                    tool_results.append({
                        "function_response": {
                            "name": fc["name"],
                            "response": result,
                        }
                    })

                # Append tool results to contents
                contents.append({
                    "role": "user",
                    "parts": tool_results,
                })

            return AwakeWorkflowResult(
                response_text="Max iterations reached",
                tool_calls_made=tool_calls_made,
                iterations=iterations,
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
            seeds_generated = 0
            dream_context: list[dict[str, Any]] = []

            for iteration in range(input.max_iterations):
                # Dreamer generates ideas
                dreamer_request = GeminiChatRequest(
                    model=input.dreamer_model,
                    system_instruction="You are the Dreamer — generate unconstrained ideas.",
                    contents=dream_context + [
                        {"role": "user", "parts": [{"text": "Generate new dream seeds."}]}
                    ],
                )
                dreamer_response: GeminiChatResponse = await workflow.execute_activity(
                    generate_content,
                    dreamer_request,
                    start_to_close_timeout=timedelta(seconds=60),
                )
                seeds_generated += 1

                # Judge evaluates for breakthrough
                judge_request = GeminiChatRequest(
                    model=input.judge_model,
                    system_instruction="You are the Judge collaborator — evaluate for breakthroughs.",
                    contents=[
                        {"role": "user", "parts": [{"text": dreamer_response.text}]}
                    ],
                )
                judge_response: GeminiChatResponse = await workflow.execute_activity(
                    generate_content,
                    judge_request,
                    start_to_close_timeout=timedelta(seconds=60),
                )

                # Check for breakthrough signal in Judge response
                if '"breakthrough": true' in judge_response.text.lower() or \
                   '"breakthrough":true' in judge_response.text.lower():
                    return DreamWorkflowResult(
                        breakthrough=True,
                        breakthrough_insight=judge_response.text,
                        iterations=iteration + 1,
                        seeds_generated=seeds_generated,
                    )

                # Add to dream context for next iteration
                dream_context.append(
                    {"role": "model", "parts": [{"text": dreamer_response.text}]}
                )

            return DreamWorkflowResult(
                breakthrough=False,
                iterations=input.max_iterations,
                seeds_generated=seeds_generated,
            )

    @workflow.defn
    class ConsolidationWorkflow:
        """Nightly memory consolidation workflow.

        Wraps ConsolidationWorker.run_nightly() as a durable workflow
        with heartbeating for long-running consolidation tasks.
        """

        @workflow.run
        async def run(self) -> dict:
            """Execute nightly consolidation as a single activity."""
            from triforce.temporal.activities import dynamic_tool_activity

            result = await workflow.execute_activity(
                dynamic_tool_activity,
                args=["run_consolidation", []],
                start_to_close_timeout=timedelta(minutes=10),
                heartbeat_timeout=timedelta(seconds=30),
            )
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
