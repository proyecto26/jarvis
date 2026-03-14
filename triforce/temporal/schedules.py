"""Temporal Schedule definitions for Dream and Consolidation workflows.

Creates Temporal Schedules for:
- DreamWorkflow: every 6 hours (configurable via DREAM_INTERVAL_HOURS)
- ConsolidationWorkflow: daily at 03:00 UTC

Requires: temporalio
Install with: pip install jarvis-triforce[temporal]
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

DREAM_INTERVAL_HOURS = int(os.getenv("DREAM_INTERVAL_HOURS", "6"))
CONSOLIDATION_HOUR_UTC = int(os.getenv("CONSOLIDATION_HOUR_UTC", "3"))
TASK_QUEUE = "jarvis-trinity"


async def create_dream_schedule(client: object) -> str:
    """Create (or update) the Temporal Schedule for DreamWorkflow.

    Idempotent — if the schedule already exists, it is not duplicated.

    Args:
        client: A connected temporalio.client.Client instance.

    Returns:
        The schedule ID.
    """
    try:
        from datetime import timedelta

        from temporalio.client import (
            Client,
            Schedule,
            ScheduleActionStartWorkflow,
            ScheduleIntervalSpec,
            ScheduleOverlapPolicy,
            ScheduleSpec,
        )

        assert isinstance(client, Client)

        from triforce.temporal.workflows import DreamWorkflow, DreamWorkflowInput

        schedule_id = "jarvis-dream-cycle"

        try:
            handle = client.get_schedule_handle(schedule_id)
            await handle.describe()
            logger.info("Dream schedule '%s' already exists — skipping creation", schedule_id)
            return schedule_id
        except Exception:
            pass  # Schedule doesn't exist yet — create it

        await client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    DreamWorkflow.run,
                    DreamWorkflowInput(),
                    id="jarvis-dream",
                    task_queue=TASK_QUEUE,
                ),
                spec=ScheduleSpec(
                    intervals=[
                        ScheduleIntervalSpec(every=timedelta(hours=DREAM_INTERVAL_HOURS))
                    ],
                ),
                policy=ScheduleOverlapPolicy.SKIP,
            ),
        )

        logger.info(
            "Dream schedule created: every %d hours (SKIP overlap)",
            DREAM_INTERVAL_HOURS,
        )
        return schedule_id

    except ImportError:
        raise NotImplementedError(
            "create_dream_schedule requires temporalio. "
            "Install with: pip install jarvis-triforce[temporal]"
        )


async def create_consolidation_schedule(client: object) -> str:
    """Create (or update) the Temporal Schedule for ConsolidationWorkflow.

    Runs daily at CONSOLIDATION_HOUR_UTC (default 03:00 UTC).
    Idempotent — if the schedule already exists, it is not duplicated.

    Args:
        client: A connected temporalio.client.Client instance.

    Returns:
        The schedule ID.
    """
    try:
        from temporalio.client import (
            Client,
            Schedule,
            ScheduleActionStartWorkflow,
            ScheduleCalendarSpec,
            ScheduleOverlapPolicy,
            ScheduleSpec,
        )

        assert isinstance(client, Client)

        from triforce.temporal.workflows import ConsolidationWorkflow

        schedule_id = "jarvis-nightly-consolidation"

        try:
            handle = client.get_schedule_handle(schedule_id)
            await handle.describe()
            logger.info("Consolidation schedule '%s' already exists — skipping", schedule_id)
            return schedule_id
        except Exception:
            pass

        await client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    ConsolidationWorkflow.run,
                    id="jarvis-consolidation",
                    task_queue=TASK_QUEUE,
                ),
                spec=ScheduleSpec(
                    calendars=[
                        ScheduleCalendarSpec(
                            hour=[CONSOLIDATION_HOUR_UTC],
                            minute=[0],
                        )
                    ],
                ),
                policy=ScheduleOverlapPolicy.SKIP,
            ),
        )

        logger.info(
            "Consolidation schedule created: daily at %02d:00 UTC",
            CONSOLIDATION_HOUR_UTC,
        )
        return schedule_id

    except ImportError:
        raise NotImplementedError(
            "create_consolidation_schedule requires temporalio. "
            "Install with: pip install jarvis-triforce[temporal]"
        )
