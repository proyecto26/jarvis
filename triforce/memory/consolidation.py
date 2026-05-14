"""Nightly consolidation worker — FadeMem decay, SSGM audit, compression.

`ConsolidationWorker.run_nightly()` is the Temporal-callable entry point. The
worker runs four passes in order; each pass is independently testable and
returns a stats dict.

Pass implementation status (May 2026):
- `run_fade_decay()` — IMPLEMENTED. Walks the singleton EpisodicMemory's
  `_last_access` map and reports decay strength + removal candidates.
- `run_ssgm_audit()` — IMPLEMENTED. Scans the last 24 h of belief mutations
  and reports SSGMGuard conflicts.
- `compress_old_episodes()` — STUB. Requires LLM access; deferred until
  the LLM router is enabled by default so we can pick a cheap local model.
- `consolidate_journal_tier()` — STUB. Same LLM dependency.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta
from pathlib import Path

from triforce.config import Config
from triforce.memory.beliefs import load_beliefs
from triforce.memory.ssgm import SSGMGuard

logger = logging.getLogger(__name__)

# Ebbinghaus decay constants
FADE_DECAY_RATE = 0.02
FADE_REMOVAL_THRESHOLD = 0.05


class ConsolidationWorker:
    """Nightly memory consolidation pipeline.

    Execution sequence:
      1. ``run_fade_decay()`` — Ebbinghaus decay over episodic memory
      2. ``compress_old_episodes()`` — LLM compression (currently stub)
      3. ``run_ssgm_audit()`` — SSGM conflict scan over last 24 h of beliefs
      4. ``consolidate_journal_tier()`` — TiMem weekly summaries (currently stub)
    """

    def __init__(self) -> None:
        logger.info("ConsolidationWorker initialised")

    async def run_nightly(self) -> dict:
        """Execute the full nightly consolidation pipeline."""
        logger.info("ConsolidationWorker.run_nightly starting")

        results = {
            "fade_decay": await self.run_fade_decay(),
            "compression": await self.compress_old_episodes(),
            "ssgm_audit": await self.run_ssgm_audit(),
            "journal_tier": await self.consolidate_journal_tier(),
        }

        logger.info("Nightly consolidation complete: %s", results)
        self._append_audit_to_journal(results)
        return results

    # ------------------------------------------------------------------
    # Pass 1: FadeMem decay
    # ------------------------------------------------------------------

    async def run_fade_decay(self) -> dict:
        """Apply Ebbinghaus decay to episodic memory.

        Formula: ``strength = e^(-decay_rate * days_since_last_access)``.
        Entries whose strength falls below ``FADE_REMOVAL_THRESHOLD`` are
        reported (the actual eviction is the EpisodicMemory's responsibility
        and happens at recall time — this pass surfaces the candidates).
        """
        from triforce.tools.memory_tools import _get_memory

        try:
            mem = _get_memory()
        except Exception as exc:
            logger.info("run_fade_decay: episodic memory unavailable (%s)", exc)
            return {
                "status": "skipped",
                "decayed_count": 0,
                "removed_count": 0,
                "preserved_count": 0,
            }

        access_map = getattr(mem, "_last_access", {})
        now = datetime.utcnow()
        decayed = 0
        removed: list[str] = []
        preserved = 0

        for entry_id, last_access in list(access_map.items()):
            try:
                days = (now - last_access).total_seconds() / 86400
            except TypeError:
                continue
            strength = math.exp(-FADE_DECAY_RATE * days)
            if strength < FADE_REMOVAL_THRESHOLD:
                removed.append(entry_id)
                # Forget this entry's access record so it doesn't keep decaying
                access_map.pop(entry_id, None)
            elif days > 1:
                decayed += 1
            else:
                preserved += 1

        logger.info(
            "run_fade_decay: %d decayed, %d below threshold, %d preserved",
            decayed,
            len(removed),
            preserved,
        )
        return {
            "status": "ok",
            "decayed_count": decayed,
            "removed_count": len(removed),
            "removed_ids": removed,
            "preserved_count": preserved,
        }

    # ------------------------------------------------------------------
    # Pass 2: Episode compression (stub — needs LLM)
    # ------------------------------------------------------------------

    async def compress_old_episodes(self) -> dict:
        """Compress 30+ day old judgments into weekly learning summaries.

        Requires an LLM call. Deferred until the router can pick a cheap
        local model for compression.
        """
        logger.info("compress_old_episodes: deferred — needs LLM router enabled")
        return {
            "status": "deferred",
            "reason": "requires DANTE_ROUTER=on with local compression model",
            "weeks_compressed": 0,
            "entries_compressed": 0,
            "high_load_preserved": 0,
        }

    # ------------------------------------------------------------------
    # Pass 3: SSGM audit over last 24 h of beliefs
    # ------------------------------------------------------------------

    async def run_ssgm_audit(self) -> dict:
        """Check all beliefs written in the last 24 h for SSGM conflicts."""
        beliefs = load_beliefs()
        cutoff = datetime.utcnow() - timedelta(hours=24)

        recent: list[dict] = []
        for b in beliefs:
            try:
                created = datetime.fromisoformat(b.get("created", ""))
                if created >= cutoff:
                    recent.append(b)
            except (TypeError, ValueError):
                continue

        guard = SSGMGuard()
        conflicts: list[dict] = []
        # Check each recent belief against the full belief store
        for belief in recent:
            text = belief.get("belief", "")
            if not text:
                continue
            report = guard.check_conflict(text)
            # The belief always conflicts with itself (similarity=1.0); skip
            # those by ignoring self-matches.
            if report.has_conflict and report.conflicting_belief_text != text:
                conflicts.append(
                    {
                        "belief": text,
                        "conflict": report.to_dict(),
                    }
                )

        logger.info(
            "run_ssgm_audit: %d beliefs checked, %d conflicts found",
            len(recent),
            len(conflicts),
        )
        return {
            "status": "ok",
            "beliefs_checked": len(recent),
            "conflicts_found": len(conflicts),
            "conflicts": conflicts,
        }

    # ------------------------------------------------------------------
    # Pass 4: TiMem-style weekly tier (stub — needs LLM)
    # ------------------------------------------------------------------

    async def consolidate_journal_tier(self) -> dict:
        """Summarize completed weeks into ``journal/YYYY-Www-summary.md``.

        Requires an LLM call. Deferred with `compress_old_episodes()`.
        """
        logger.info(
            "consolidate_journal_tier: deferred — needs LLM router enabled"
        )
        return {
            "status": "deferred",
            "reason": "requires DANTE_ROUTER=on with local summarization model",
            "weeks_summarised": 0,
        }

    # ------------------------------------------------------------------
    # Audit writeback
    # ------------------------------------------------------------------

    def _append_audit_to_journal(self, results: dict) -> None:
        """Write a consolidation audit entry to today's journal under open_questions.

        Surfaces SSGM conflicts and FadeMem removal candidates so the Judge
        sees them during the next reflective session.
        """
        try:
            from triforce.memory.journal import append_to_section

            ssgm = results.get("ssgm_audit", {})
            fade = results.get("fade_decay", {})
            conflicts = ssgm.get("conflicts", [])

            if not conflicts and fade.get("removed_count", 0) == 0:
                return  # Nothing to surface

            summary_lines = ["Consolidation audit:"]
            if fade.get("removed_count", 0) > 0:
                summary_lines.append(
                    f"  - FadeMem removed {fade['removed_count']} entries below "
                    f"strength {FADE_REMOVAL_THRESHOLD}"
                )
            if conflicts:
                summary_lines.append(
                    f"  - SSGM detected {len(conflicts)} belief conflicts in last 24h:"
                )
                for c in conflicts[:5]:
                    summary_lines.append(
                        f"    • '{c['belief'][:60]}' vs "
                        f"'{c['conflict']['conflicting_belief_text'][:60]}' "
                        f"(similarity={c['conflict']['similarity_score']})"
                    )
            append_to_section("open_questions", "\n".join(summary_lines))
        except Exception as exc:
            logger.warning("Failed to write consolidation audit: %s", exc)
