"""Executor escalation tool — hand a heavy task to the durable Temporal loop.

This is the opt-in seam from the in-process ADK Executor to the durable
``AwakeWorkflow`` (a crash-proof ReAct loop). The tool always degrades
gracefully: when ``temporalio`` is not installed or the Temporal server is
unreachable it returns a status message (it never raises), so the Executor
simply keeps working in-process.

The tool is only offered to the Executor when ``Config.DANTE_DURABLE_AWAKE`` is
on — see ``triforce/agents/executor/agent.py`` and TEMPORAL.md. The durable
client is imported lazily inside the call, so this module imports cleanly with
no ``temporalio`` installed.
"""

import logging

from google.adk.tools import ToolContext

from triforce.config import Config

logger = logging.getLogger(__name__)


async def escalate_to_durable_workflow(task: str, tool_context: ToolContext) -> dict:
    """Escalate a high-weight or long-running task to the durable Temporal loop.

    Hands ``task`` to the durable AwakeWorkflow so heavy, multi-step, or costly
    work survives worker restarts (each LLM call and tool step becomes a durable
    activity). Use this only for genuinely heavy actions — normal turns should
    run in-process. If the durable backend is unavailable this returns a
    ``status='unavailable'`` message and you should complete the task in-process
    instead of retrying.

    Args:
        task: The full task/request to execute durably.
    """
    from triforce.temporal.client import run_awake_workflow

    # Carry the Judge's guidance into the durable loop when present, so the
    # escalated run keeps the same framing the in-process Executor had.
    system_instruction = ""
    guidance = tool_context.state.get("executor_guidance")
    if isinstance(guidance, str) and guidance:
        system_instruction = guidance

    result = await run_awake_workflow(
        user_message=task,
        system_instruction=system_instruction,
        model=Config.model_for("executor", Config.EXECUTOR_MODEL),
    )

    if result.get("status") == "completed":
        return {
            "status": "escalated",
            "durable_response": result.get("response", ""),
            "tool_calls": result.get("tool_calls", 0),
            "iterations": result.get("iterations", 0),
        }

    # Temporal unavailable or the durable run failed — tell the Executor to
    # finish the task in-process rather than surfacing an exception.
    logger.warning(
        "Durable escalation unavailable (%s) — continue in-process",
        result.get("status"),
    )
    return {
        "status": "unavailable",
        "message": (
            "Durable execution is not available right now; complete the task "
            "in-process instead."
        ),
        "detail": result.get("error", ""),
    }
