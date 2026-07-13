"""Nightly consolidation worker — FadeMem decay, SSGM audit, compression.

`ConsolidationWorker.run_nightly()` is the Temporal-callable entry point. The
worker runs four passes in order; each pass is independently testable and
returns a stats dict.

Pass implementation status (July 2026):
- `run_fade_decay()` — IMPLEMENTED. Walks the singleton EpisodicMemory's
  `_last_access` map and reports decay strength + removal candidates.
- `run_ssgm_audit()` — IMPLEMENTED. Scans the last 24 h of belief mutations
  and reports SSGMGuard conflicts.
- `compress_old_episodes()` — IMPLEMENTED. Groups 30+ day old journal weeks
  and compresses them into `Learning` OKF docs via the LLM router
  (`consolidation` policy). Falls back to a deferred stub result when no LLM
  is reachable — graceful degradation, never crashes.
- `consolidate_journal_tier()` — IMPLEMENTED. TiMem-style weekly tier:
  writes `journal/YYYY-Www-summary.md` per completed ISO week via the same
  LLM adapter, with the same deferred fallback.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from triforce.config import Config
from triforce.memory.beliefs import load_beliefs
from triforce.memory.okf import OKFBundle, OKFDocument, _atomic_write
from triforce.memory.ssgm import SSGMGuard

logger = logging.getLogger(__name__)

# Ebbinghaus decay constants
FADE_DECAY_RATE = 0.02
FADE_REMOVAL_THRESHOLD = 0.05

# Episode compression constants
COMPRESSION_AGE_DAYS = 30
HIGH_LOAD_THRESHOLD = 0.8  # cognitive_load_score at/above this is preserved
MAX_LEARNINGS_PER_WEEK = 7
LLM_TIMEOUT_SECONDS = 120

# Bullet / numbered list items in an LLM summary reply.
_LEARNING_LINE_RE = re.compile(r"^(?:[-*•]|\d+[.)])\s+(.*\S)")


# ----------------------------------------------------------------------
# LLM adapter — the ONLY place consolidation talks to the router
# ----------------------------------------------------------------------


def _is_availability_error(exc: Exception) -> bool:
    """True for errors that mean "no LLM reachable" — not a bug in our code.

    Availability: no routing candidate, local-only refusal, unhealthy
    provider, and network/timeout errors from the provider call. Everything
    else (policy schema errors, router/provider API drift, TypeError/KeyError
    style bugs) is NOT availability and must be logged loudly.
    """
    from triforce.llm.errors import (
        LocalOnlyRouteFailure,
        NoCandidateError,
        ProviderUnhealthy,
    )

    if isinstance(exc, (NoCandidateError, LocalOnlyRouteFailure, ProviderUnhealthy)):
        return True
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    try:
        import httpx
    except ImportError:
        return False
    return isinstance(exc, httpx.HTTPError)


def _llm_summarize(prompt: str) -> str | None:
    """Run one summarization prompt through the LLM router.

    Routes with the ``consolidation`` policy (cheap local model preferred,
    cloud fallback allowed), resolves the decided provider from the provider
    registry, and runs a single completion.

    Returns the completion text, or ``None`` on ANY failure — callers treat
    ``None`` as "LLM unavailable" and defer their pass (graceful degradation
    is a repo invariant). Genuine availability failures (router disabled, no
    candidate, provider missing/unhealthy, network/timeout) are logged at
    INFO; anything else is a bug or config error and is logged at WARNING
    with a traceback so it can never masquerade as mere unavailability.

    NOTE: this is a synchronous, blocking call (up to ``LLM_TIMEOUT_SECONDS``)
    — async callers must offload it via ``asyncio.to_thread`` so the worker
    event loop (and Temporal heartbeating) keeps running.
    """
    try:
        if not Config.router_enabled():
            logger.info("_llm_summarize: router disabled (DANTE_ROUTER=off)")
            return None

        from triforce.llm.providers import get_provider
        from triforce.llm.router import get_router
        from triforce.llm.types import RouteRequest

        decision = get_router().route(
            RouteRequest(
                agent="consolidation",
                task_type="summarization",
                requires_tools=False,
            )
        )
        provider = get_provider(decision.provider_name)
        if provider is None:
            logger.info(
                "_llm_summarize: provider %r not registered", decision.provider_name
            )
            return None
        response = provider.generate(
            decision.model.base_id,
            [{"role": "user", "content": prompt}],
            params={"temperature": 0.2, "timeout_seconds": LLM_TIMEOUT_SECONDS},
        )
        text = (response.text or "").strip()
        return text or None
    except Exception as exc:
        if _is_availability_error(exc):
            logger.info("_llm_summarize: LLM unavailable (%s)", exc)
        else:
            logger.warning(
                "_llm_summarize: unexpected failure — likely a bug or config "
                "error, NOT LLM unavailability: %s",
                exc,
                exc_info=True,
            )
        return None


# ----------------------------------------------------------------------
# Journal / ISO-week helpers
# ----------------------------------------------------------------------


def _journal_dates() -> list[date]:
    """Dates of all daily journal entries (from their JSON backing files)."""
    if not Config.JOURNAL_DIR.exists():
        return []
    dates: list[date] = []
    for path in sorted(Config.JOURNAL_DIR.glob("*.json")):
        try:
            dates.append(date.fromisoformat(path.stem))
        except ValueError:
            continue  # not a daily entry (e.g. sidecar state files)
    return dates


def _iso_week_key(d: date) -> str:
    """ISO week key, e.g. ``2026-W05``."""
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _iso_week_end(d: date) -> date:
    """The Sunday closing the ISO week containing ``d``."""
    iso = d.isocalendar()
    return date.fromisocalendar(iso[0], iso[1], 7)


def _parse_learning_items(text: str) -> list[str]:
    """Extract learning statements from an LLM bullet-list reply.

    Falls back to non-empty lines when the model ignored the bullet format.
    Clamped to ``MAX_LEARNINGS_PER_WEEK`` items.
    """
    items: list[str] = []
    for line in text.splitlines():
        match = _LEARNING_LINE_RE.match(line.strip())
        if match:
            items.append(match.group(1).strip())
    if not items:
        items = [line.strip() for line in text.splitlines() if line.strip()]
    return items[:MAX_LEARNINGS_PER_WEEK]


# ----------------------------------------------------------------------
# Compression state sidecar (knowledge/.consolidation-state.json)
# ----------------------------------------------------------------------


class ConsolidationStateError(RuntimeError):
    """The compression state sidecar exists but cannot be read or parsed."""


def _state_path() -> Path:
    return Config.KNOWLEDGE_DIR / ".consolidation-state.json"


def _load_consolidation_state() -> dict:
    """Load the sidecar. Missing file means a fresh install ({}).

    A file that EXISTS but cannot be read/parsed raises
    :exc:`ConsolidationStateError` instead of silently "starting fresh" —
    losing ``compressed_weeks`` would re-compress every historical week into
    duplicate Learning docs, which is irreversible. The compression pass
    aborts for the night; a transient read error self-heals on the next run.
    """
    path = _state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ConsolidationStateError(
            f"consolidation state {path} is unreadable: {exc}"
        ) from exc


def _save_consolidation_state(state: dict) -> None:
    _atomic_write(_state_path(), json.dumps(state, indent=2) + "\n")


class ConsolidationWorker:
    """Nightly memory consolidation pipeline.

    Execution sequence:
      1. ``run_fade_decay()`` — Ebbinghaus decay over episodic memory
      2. ``compress_old_episodes()`` — LLM compression into Learning OKF docs
      3. ``run_ssgm_audit()`` — SSGM conflict scan over last 24 h of beliefs
      4. ``consolidate_journal_tier()`` — TiMem weekly summaries via LLM
    """

    def __init__(self) -> None:
        logger.info("ConsolidationWorker initialised")

    async def run_nightly(self) -> dict:
        """Execute the full nightly consolidation pipeline.

        Each pass is independently guarded — one failing pass is reported in
        its result slot but never aborts the remaining passes or the audit
        writeback.
        """
        logger.info("ConsolidationWorker.run_nightly starting")

        passes = (
            ("fade_decay", self.run_fade_decay),
            ("compression", self.compress_old_episodes),
            ("ssgm_audit", self.run_ssgm_audit),
            ("journal_tier", self.consolidate_journal_tier),
        )
        results: dict = {}
        for name, run_pass in passes:
            try:
                results[name] = await run_pass()
            except Exception as exc:
                logger.exception("Consolidation pass %r failed", name)
                results[name] = {"status": "error", "error": str(exc)}

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
    # Pass 2: Episode compression (LLM → Learning OKF docs)
    # ------------------------------------------------------------------

    async def compress_old_episodes(self) -> dict:
        """Compress 30+ day old judgments into weekly learning summaries.

        Journal entries older than ``COMPRESSION_AGE_DAYS`` are grouped by
        ISO week; a week becomes eligible only once ALL of its days have aged
        past the cutoff (no partial-week compression). Each eligible week's
        judgments and executions are LLM-summarized into 3-7 ``Learning`` OKF
        docs in the knowledge bundle. High-cognitive-load days
        (``cognitive_load_score >= HIGH_LOAD_THRESHOLD``) are preserved
        verbatim — excluded from compression.

        Compressed weeks are recorded in
        ``knowledge/.consolidation-state.json`` (atomic write, persisted per
        week) so re-runs are idempotent. When no LLM is reachable the pass
        returns the deferred stub result unchanged.
        """
        from triforce.memory.journal import load_entry

        cutoff = date.today() - timedelta(days=COMPRESSION_AGE_DAYS)
        try:
            state = _load_consolidation_state()
        except ConsolidationStateError as exc:
            # Never "start fresh" over a corrupt/unreadable sidecar — that
            # would re-compress every historical week into duplicate docs.
            logger.error(
                "compress_old_episodes: %s — skipping compression this run",
                exc,
            )
            return {
                "status": "skipped",
                "reason": "consolidation state unreadable",
                "weeks_compressed": 0,
                "entries_compressed": 0,
                "high_load_preserved": 0,
            }
        compressed_weeks = set(state.get("compressed_weeks", []))

        # Group aged entries by ISO week, skipping already-compressed weeks
        # and weeks still straddling the cutoff.
        weeks: dict[str, list] = {}
        for entry_date in _journal_dates():
            if entry_date >= cutoff or _iso_week_end(entry_date) >= cutoff:
                continue
            key = _iso_week_key(entry_date)
            if key in compressed_weeks:
                continue
            entry = load_entry(entry_date.isoformat())
            if entry is not None:
                weeks.setdefault(key, []).append(entry)

        if not weeks:
            logger.info("compress_old_episodes: no uncompressed aged weeks")
            return {
                "status": "ok",
                "weeks_compressed": 0,
                "entries_compressed": 0,
                "high_load_preserved": 0,
            }

        bundle = OKFBundle()
        weeks_compressed = 0
        entries_compressed = 0
        high_load_preserved = 0
        llm_unavailable = False

        for key in sorted(weeks):
            entries = weeks[key]
            compressible = [
                e
                for e in entries
                if e.metadata.cognitive_load_score < HIGH_LOAD_THRESHOLD
            ]
            preserved = len(entries) - len(compressible)

            if compressible:
                # Blocking LLM call — offload so the worker event loop (and
                # Temporal heartbeating) keeps running.
                summary = await asyncio.to_thread(
                    _llm_summarize, self._compression_prompt(key, compressible)
                )
                if summary is None:
                    llm_unavailable = True
                    break
                week_end = _iso_week_end(
                    date.fromisoformat(compressible[0].metadata.date)
                )
                # Idempotency across partial failures: a crashed/retried run
                # may already have written some of this week's learnings
                # (the week is only marked compressed after ALL its docs are
                # written) — skip items that already exist.
                already_written = {
                    doc.body.strip()
                    for _, doc in bundle.documents("learnings")
                    if doc.extras.get("source_week") == key
                }
                try:
                    for item in _parse_learning_items(summary):
                        if item in already_written:
                            continue
                        doc = OKFDocument(
                            type="Learning",
                            title=" ".join(item.split()[:8]),
                            description=item,
                            tags=["consolidation", key],
                            extras={"source_week": key},
                            body=item,
                        )
                        bundle.write(
                            doc,
                            "learnings",
                            doc_date=week_end.isoformat(),
                            action="Consolidation",
                        )
                except Exception:
                    # A mid-week write failure (disk full, locked log.md)
                    # must not abort the other weeks or the remaining nightly
                    # passes. The week stays unmarked and is retried next
                    # run; the dedupe above prevents duplicate docs then.
                    logger.exception(
                        "compress_old_episodes: week %s failed mid-write; "
                        "will retry next run",
                        key,
                    )
                    continue
                entries_compressed += len(compressible)
                weeks_compressed += 1

            high_load_preserved += preserved
            compressed_weeks.add(key)
            state["compressed_weeks"] = sorted(compressed_weeks)
            _save_consolidation_state(state)  # persist per week — crash-safe

        if weeks_compressed:
            bundle.rebuild_indexes(only_dirty=True)

        if llm_unavailable and weeks_compressed == 0:
            logger.info("compress_old_episodes: deferred — LLM unavailable")
            return {
                "status": "deferred",
                "reason": "requires DANTE_ROUTER=on with local compression model",
                "weeks_compressed": 0,
                "entries_compressed": 0,
                # High-load-only weeks processed before the LLM became
                # unavailable were consumed from state — report their count
                # rather than a hardcoded 0, or it is lost from every run.
                "high_load_preserved": high_load_preserved,
            }

        logger.info(
            "compress_old_episodes: %d weeks, %d entries compressed, %d preserved",
            weeks_compressed,
            entries_compressed,
            high_load_preserved,
        )
        return {
            "status": "ok",
            "weeks_compressed": weeks_compressed,
            "entries_compressed": entries_compressed,
            "high_load_preserved": high_load_preserved,
        }

    @staticmethod
    def _compression_prompt(week_key: str, entries: list) -> str:
        """Build the compression prompt from a week's judgments/executions."""
        lines = [
            f"You are consolidating an AI agent's journal for ISO week {week_key}.",
            "Distill the judgments and executions below into 3-7 durable,",
            "generalizable learnings the agent should keep after the raw",
            "entries are archived.",
            "Reply with ONLY a markdown bullet list — one learning per line,",
            "prefixed with '- '.",
            "",
        ]
        for entry in entries:
            lines.append(f"## {entry.metadata.date}")
            for j in entry.judgments:
                lines.append(
                    f"- Judgment [{j.verdict}] {j.action} "
                    f"(weight {j.action_weight}): {j.reasoning}"
                )
            for e in entry.executions:
                lines.append(f"- Execution [{e.status}] {e.action}: {e.outcome}")
            lines.append("")
        return "\n".join(lines)

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
    # Pass 4: TiMem-style weekly tier (LLM → journal/YYYY-Www-summary.md)
    # ------------------------------------------------------------------

    async def consolidate_journal_tier(self) -> dict:
        """Summarize completed weeks into ``journal/YYYY-Www-summary.md``.

        A week is eligible once it has fully elapsed (its Sunday is in the
        past) and has at least one daily entry but no summary file yet — the
        summary file's existence is the idempotency marker. When no LLM is
        reachable the pass returns the deferred stub result unchanged.
        """
        today = date.today()

        weeks: dict[str, list[date]] = {}
        for entry_date in _journal_dates():
            if _iso_week_end(entry_date) >= today:
                continue  # week not complete yet
            weeks.setdefault(_iso_week_key(entry_date), []).append(entry_date)

        pending = {
            key: sorted(dates)
            for key, dates in weeks.items()
            if not (Config.JOURNAL_DIR / f"{key}-summary.md").exists()
        }
        if not pending:
            logger.info("consolidate_journal_tier: no unsummarised weeks")
            return {"status": "ok", "weeks_summarised": 0}

        weeks_summarised = 0
        llm_unavailable = False
        for key in sorted(pending):
            # Blocking LLM call — offload so the worker event loop (and
            # Temporal heartbeating) keeps running.
            summary = await asyncio.to_thread(
                _llm_summarize, self._weekly_summary_prompt(key, pending[key])
            )
            if summary is None:
                llm_unavailable = True
                break
            content = f"# Weekly Summary — {key}\n\n{summary.strip()}\n"
            _atomic_write(Config.JOURNAL_DIR / f"{key}-summary.md", content)
            weeks_summarised += 1

        if llm_unavailable and weeks_summarised == 0:
            logger.info("consolidate_journal_tier: deferred — LLM unavailable")
            return {
                "status": "deferred",
                "reason": "requires DANTE_ROUTER=on with local summarization model",
                "weeks_summarised": 0,
            }

        logger.info(
            "consolidate_journal_tier: %d weeks summarised", weeks_summarised
        )
        return {"status": "ok", "weeks_summarised": weeks_summarised}

    @staticmethod
    def _weekly_summary_prompt(week_key: str, dates: list[date]) -> str:
        """Build the weekly summary prompt from that week's daily markdown."""
        lines = [
            "Write a concise weekly summary of an AI agent's journal for ISO",
            f"week {week_key}. Cover dominant themes, key judgments, execution",
            "outcomes, and learnings. Reply in markdown, at most ~300 words.",
            "",
        ]
        for d in dates:
            path = Config.JOURNAL_DIR / f"{d.isoformat()}.md"
            if path.exists():
                lines.append(f"<!-- {d.isoformat()} -->")
                lines.append(path.read_text(encoding="utf-8", errors="replace"))
                lines.append("")
        return "\n".join(lines)

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
