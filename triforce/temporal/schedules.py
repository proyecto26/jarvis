"""Temporal Schedule definitions for Dream and Consolidation workflows.

Creates Temporal Schedules for:
- DreamWorkflow: every 6 hours (configurable via DREAM_INTERVAL_HOURS)
- ConsolidationWorkflow: daily at 03:00 UTC (configurable via CONSOLIDATION_HOUR_UTC)

Create both with: python -m triforce.temporal.schedules

Requires: temporalio
Install with: pip install jarvis-triforce[temporal]
"""

from __future__ import annotations

import asyncio
import logging

from triforce.config import Config

logger = logging.getLogger(__name__)

DREAM_INTERVAL_HOURS = Config.DREAM_INTERVAL_HOURS
CONSOLIDATION_HOUR_UTC = Config.CONSOLIDATION_HOUR_UTC
TASK_QUEUE = Config.TEMPORAL_TASK_QUEUE


def _is_not_found(exc: BaseException) -> bool:
    """True only if ``exc`` means the schedule does not exist yet.

    A describe() on a missing schedule raises an RPCError with status
    NOT_FOUND — that is the one case where "create it" is correct. Every
    other failure (server unreachable, permission denied, timeout) is a
    genuine error that must propagate rather than be silently swallowed as
    "does not exist". When temporalio's typed errors are unavailable we
    fall back to sniffing the message for 'not found'.
    """
    try:
        from temporalio.service import RPCError, RPCStatusCode

        if isinstance(exc, RPCError):
            return exc.status == RPCStatusCode.NOT_FOUND
    except ImportError:
        pass
    msg = str(exc).lower()
    return "not found" in msg or "not_found" in msg


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
            SchedulePolicy,
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
        except Exception as exc:
            if not _is_not_found(exc):
                raise  # Genuine failure (unreachable/denied) — don't swallow.
            # Schedule doesn't exist yet — fall through and create it.

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
                policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
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
            SchedulePolicy,
            ScheduleRange,
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
        except Exception as exc:
            if not _is_not_found(exc):
                raise  # Genuine failure (unreachable/denied) — don't swallow.
            # Schedule doesn't exist yet — fall through and create it.

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
                            # temporalio requires ScheduleRange entries here, not
                            # bare ints — a raw int has no _to_proto() and crashes
                            # create_schedule() on serialize.
                            hour=[ScheduleRange(CONSOLIDATION_HOUR_UTC)],
                            minute=[ScheduleRange(0)],
                        )
                    ],
                ),
                policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
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


async def _main() -> None:
    """Connect to Temporal and create both Trinity schedules (idempotent)."""
    try:
        from temporalio.client import Client
    except ImportError:
        logger.error(
            "temporalio is not installed. "
            "Install with: pip install jarvis-triforce[temporal]"
        )
        raise SystemExit(1)

    logger.info(
        "Connecting to Temporal at %s (namespace=%s)",
        Config.TEMPORAL_ADDRESS,
        Config.TEMPORAL_NAMESPACE,
    )
    client = await Client.connect(
        Config.TEMPORAL_ADDRESS, namespace=Config.TEMPORAL_NAMESPACE
    )

    dream_id = await create_dream_schedule(client)
    consolidation_id = await create_consolidation_schedule(client)

    logger.info(
        "Trinity schedules ready: dream=%s, consolidation=%s",
        dream_id,
        consolidation_id,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
