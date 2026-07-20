"""Lazy async Temporal client for starting Trinity workflows from production.

This is the seam that lets in-process code (the ADK Executor) hand a task to
the durable Temporal layer. Two entry points:

- ``get_client()`` — a cached singleton client, connected once to
  ``Config.TEMPORAL_ADDRESS`` / ``Config.TEMPORAL_NAMESPACE``.
- ``run_awake_workflow(...)`` — start ``AwakeWorkflow`` durably and return its
  result as a plain dict.

Both degrade gracefully. Local-first + graceful degradation are invariants:
this module imports cleanly with no ``temporalio`` installed (nothing is
imported from ``temporalio`` at module load), ``get_client`` raises a single
``TemporalUnavailable`` type whether the dependency is missing or the server is
unreachable, and ``run_awake_workflow`` never raises — it returns a structured
error dict so the caller can keep working in-process.

Requires (only for actual durable execution): temporalio
Install with: uv sync --extra temporal
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import timedelta
from typing import Any, Optional

from triforce.config import Config

logger = logging.getLogger(__name__)


class TemporalUnavailable(RuntimeError):
    """Raised by ``get_client`` when a Temporal client cannot be obtained.

    Covers both "temporalio not installed" and "server unreachable" so callers
    can degrade to in-process execution behind a single ``except`` clause.
    """


# Cached singleton client + a lock so concurrent first-callers connect once.
# The lock binds to the running loop lazily (Python 3.10+), so importing this
# module never touches an event loop.
_client: Any = None
_client_lock = asyncio.Lock()


async def get_client() -> Any:
    """Return a connected Temporal client, connecting once and caching it.

    The first call connects to ``Config.TEMPORAL_ADDRESS`` in
    ``Config.TEMPORAL_NAMESPACE`` and caches the client; later calls return the
    cached instance. Raises ``TemporalUnavailable`` — never a bare
    ``ImportError`` or connection error — if ``temporalio`` is missing or the
    server cannot be reached, so callers fall back to in-process execution with
    one ``except``.
    """
    global _client
    if _client is not None:
        return _client

    async with _client_lock:
        # Re-check inside the lock: another coroutine may have connected while
        # this one waited to acquire it.
        if _client is not None:
            return _client

        try:
            from temporalio.client import Client
        except ImportError as exc:
            raise TemporalUnavailable(
                "temporalio is not installed — durable execution unavailable. "
                "Install with: uv sync --extra temporal"
            ) from exc

        logger.info(
            "Connecting to Temporal at %s (namespace=%s)",
            Config.TEMPORAL_ADDRESS,
            Config.TEMPORAL_NAMESPACE,
        )
        try:
            _client = await Client.connect(
                Config.TEMPORAL_ADDRESS, namespace=Config.TEMPORAL_NAMESPACE
            )
        except Exception as exc:  # noqa: BLE001 — any connect failure degrades
            raise TemporalUnavailable(
                f"Cannot reach Temporal server at {Config.TEMPORAL_ADDRESS}: {exc}"
            ) from exc

    return _client


async def run_awake_workflow(
    user_message: str,
    system_instruction: str = "",
    model: Optional[str] = None,
    timeout_s: int = 120,
) -> dict:
    """Start ``AwakeWorkflow`` durably and return its result as a dict.

    Escalation seam from the in-process ADK path to the durable Temporal ReAct
    loop. Never raises: on success returns the workflow result, and if Temporal
    is unavailable/unreachable or the durable run fails it returns a structured
    error dict so the caller can keep working in-process.

    Returns one of:
      - ``{"status": "completed", "response": str, "tool_calls": int, "iterations": int}``
      - ``{"status": "unavailable", "error": str}`` — Temporal not reachable
      - ``{"status": "error", "error": str}`` — durable run failed/timed out

    Args:
        user_message: The task/request to execute in the durable loop.
        system_instruction: Optional system prompt (e.g. the Judge's guidance).
        model: Gemini model id; defaults to ``Config.EXECUTOR_MODEL``.
        timeout_s: Max seconds to wait for the durable run before giving up.
    """
    try:
        client = await get_client()
    except TemporalUnavailable as exc:
        logger.warning("Awake escalation skipped — %s", exc)
        return {"status": "unavailable", "error": str(exc)}

    # Safe whether temporalio is installed or not (workflows.py exposes stubs),
    # but only reached once a real client connected.
    from triforce.temporal.workflows import AwakeWorkflow, AwakeWorkflowInput

    workflow_input = AwakeWorkflowInput(
        user_message=user_message,
        system_instruction=system_instruction,
        model=model or Config.EXECUTOR_MODEL,
    )

    try:
        result = await client.execute_workflow(
            AwakeWorkflow.run,
            workflow_input,
            id=f"awake-{uuid.uuid4()}",
            task_queue=Config.TEMPORAL_TASK_QUEUE,
            run_timeout=timedelta(seconds=timeout_s),
        )
    except Exception as exc:  # noqa: BLE001 — durable run failed; degrade
        logger.warning("AwakeWorkflow execution failed: %s", exc)
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

    return {
        "status": "completed",
        "response": result.response_text,
        "tool_calls": result.tool_calls_made,
        "iterations": result.iterations,
    }
