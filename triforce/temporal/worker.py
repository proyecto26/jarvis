"""Temporal worker — connects to Temporal server and registers workflows + activities.

Start with: python -m triforce.temporal.worker

Requires: temporalio
Install with: pip install jarvis-triforce[temporal]
"""

from __future__ import annotations

import asyncio
import logging

from triforce.config import Config

logger = logging.getLogger(__name__)


async def start_worker() -> None:
    """Start the Temporal worker, registering all workflows and activities."""
    try:
        from temporalio.client import Client
        from temporalio.worker import Worker
    except ImportError:
        logger.error(
            "temporalio is not installed. "
            "Install with: pip install jarvis-triforce[temporal]"
        )
        raise SystemExit(1)

    from triforce.temporal.workflows import (
        AwakeWorkflow,
        DreamWorkflow,
        ConsolidationWorkflow,
    )
    from triforce.temporal.activities import (
        generate_content,
        dynamic_tool_activity,
    )

    logger.info(
        "Connecting to Temporal at %s (namespace=%s)",
        Config.TEMPORAL_ADDRESS,
        Config.TEMPORAL_NAMESPACE,
    )
    client = await Client.connect(
        Config.TEMPORAL_ADDRESS, namespace=Config.TEMPORAL_NAMESPACE
    )

    worker = Worker(
        client,
        task_queue=Config.TEMPORAL_TASK_QUEUE,
        workflows=[AwakeWorkflow, DreamWorkflow, ConsolidationWorkflow],
        activities=[generate_content, dynamic_tool_activity],
    )

    logger.info(
        "DANTE Trinity worker started on task queue: %s", Config.TEMPORAL_TASK_QUEUE
    )
    await worker.run()


def main() -> None:
    """Entry point for python -m triforce.temporal.worker."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_worker())


if __name__ == "__main__":
    main()
