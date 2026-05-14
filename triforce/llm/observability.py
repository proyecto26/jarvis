"""Routing decision logger — append-only JSONL with atomic writes.

Every Router.route() call ends with a log_decision() entry. The Judge's
router-audit Skill (future work) reads these to detect regressions over time.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from triforce.config import Config
from triforce.llm.types import RouteDecision, RouteRequest

logger = logging.getLogger(__name__)


def _log_dir() -> Path:
    base = Config.JOURNAL_DIR / "llm-routing"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _log_path(when: Optional[datetime] = None) -> Path:
    when = when or datetime.utcnow()
    return _log_dir() / f"{when.strftime('%Y-%m-%d')}.jsonl"


def _atomic_append(path: Path, line: str) -> None:
    """Append a single line atomically.

    Append-only JSONL — we open in append mode with a single write call so
    POSIX guarantees the bytes are appended atomically up to PIPE_BUF.
    """
    # JSON encoding of one record never exceeds PIPE_BUF for the fields we log
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def log_decision(
    request: RouteRequest,
    decision: Optional[RouteDecision],
    *,
    reason: str,
    level: str = "info",
    reasoning: Optional[Sequence[str]] = None,
    candidates_considered: Optional[Sequence[str]] = None,
) -> None:
    """Append a structured record to today's routing log.

    Args:
        request: The RouteRequest that triggered the decision.
        decision: The RouteDecision if one was made; None for refusals/errors.
        reason: Short tag describing the outcome category.
        level: ``info`` | ``warning`` | ``error``.
        reasoning: Per-step reasoning trace (used when decision is None).
        candidates_considered: Candidate model ids considered (when decision is None).
    """
    try:
        record = {
            "ts": time.time(),
            "iso": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "reason": reason,
            "agent": request.agent,
            "task_type": request.task_type,
            "privacy_class": request.privacy_class,
            "max_latency_ms": request.max_latency_ms,
        }
        if decision is not None:
            record.update(
                {
                    "decision_id": decision.decision_id,
                    "model_id": decision.model.id,
                    "base_id": decision.model.base_id,
                    "provider": decision.provider_name,
                    "is_local": decision.is_local,
                    "adapter_id": (decision.adapter.id if decision.adapter else None),
                    "fallback_depth": decision.fallback_depth,
                    "reasoning": list(decision.reasoning),
                    "candidates_considered": list(decision.candidates_considered),
                }
            )
        else:
            record["reasoning"] = list(reasoning or [])
            record["candidates_considered"] = list(candidates_considered or [])

        _atomic_append(_log_path(), json.dumps(record, default=str))
    except Exception as exc:
        # Never raise from the logger — routing must not fail because logging did
        logger.warning("Failed to log routing decision: %s", exc)
