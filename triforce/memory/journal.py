"""Journal file I/O — create, load, and append to daily Markdown files."""

import json
import logging
import tempfile
from datetime import date, datetime
from pathlib import Path

from triforce.config import Config
from triforce.memory.schema import (
    BeliefMutation,
    DreamCycle,
    Execution,
    JournalEntry,
    JournalMetadata,
    Judgment,
    Learning,
)

logger = logging.getLogger(__name__)

SECTION_MODELS = {
    "dreams": DreamCycle,
    "judgments": Judgment,
    "executions": Execution,
    "learnings": Learning,
    "belief_mutations": BeliefMutation,
}

# Executions carry no action_weight field — they count at a default weight.
_EXECUTION_DEFAULT_WEIGHT = 1


def _journal_path(entry_date: str) -> Path:
    return Config.JOURNAL_DIR / f"{entry_date}.md"


def _json_path(entry_date: str) -> Path:
    return Config.JOURNAL_DIR / f"{entry_date}.json"


def _ensure_dir():
    Config.JOURNAL_DIR.mkdir(parents=True, exist_ok=True)


def _atomic_write(path: Path, content: str):
    """Write content to a file using atomic write (write-to-temp-then-rename)."""
    _ensure_dir()
    tmp = Path(tempfile.mktemp(dir=path.parent, suffix=".tmp"))
    try:
        # Explicit UTF-8 — the platform default (cp1252 on Windows) would
        # mojibake em dashes/accents when consolidation reads these files
        # back as UTF-8, and reject anything outside cp1252 entirely.
        tmp.write_text(content, encoding="utf-8")
        # ``replace`` (not ``rename``) — journal files are rewritten on every
        # append, and ``rename`` fails on Windows when the target exists.
        tmp.replace(path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def entry_to_markdown(entry: JournalEntry) -> str:
    """Convert a JournalEntry to structured Markdown."""
    lines = [f"# Journal — {entry.metadata.date}", ""]

    # Metadata
    lines.append("## Metadata")
    lines.append(f"- Date: {entry.metadata.date}")
    if entry.metadata.mode_cycles:
        cycles = ", ".join(f"{k}({v})" for k, v in entry.metadata.mode_cycles.items())
        lines.append(f"- Mode cycles: {cycles}")
    if entry.metadata.dominant_theme:
        lines.append(f"- Dominant theme: {entry.metadata.dominant_theme}")
    lines.extend(["", "---", ""])

    # Dreams
    lines.append("## Dreams")
    if entry.dreams:
        for i, dream in enumerate(entry.dreams, 1):
            lines.append(f"\n### Dream Cycle {i} ({dream.timestamp})")
            if dream.seed:
                lines.append(f"- Seed: {dream.seed}")
            if dream.branches:
                lines.append(f"- Branches: {dream.branches}")
            lines.append(f"- Depth reached: {dream.depth_reached}")
            if dream.breakthrough:
                lines.append(f"- **Breakthrough**: {dream.breakthrough}")
    else:
        lines.append("*No dreams recorded today.*")
    lines.extend(["", "---", ""])

    # Judgments
    lines.append("## Judgments")
    if entry.judgments:
        for j in entry.judgments:
            lines.append(f"\n### Decision: [{j.action}]")
            lines.append(f"- Action weight: {j.action_weight}/10")
            lines.append(f"- Verdict: {j.verdict}")
            if j.reasoning:
                lines.append(f"- Reasoning: {j.reasoning}")
            lines.append(f"- Time: {j.timestamp}")
    else:
        lines.append("*No judgments recorded today.*")
    lines.extend(["", "---", ""])

    # Executions
    lines.append("## Executions")
    if entry.executions:
        for e in entry.executions:
            lines.append(f"\n### Action: {e.action}")
            lines.append(f"- Status: {e.status}")
            lines.append(f"- Outcome: {e.outcome}")
            if e.artifacts:
                lines.append(f"- Artifacts: {e.artifacts}")
            lines.append(f"- Time: {e.timestamp}")
    else:
        lines.append("*No executions recorded today.*")
    lines.extend(["", "---", ""])

    # Learnings
    lines.append("## Learnings")
    if entry.learnings:
        for i, learning in enumerate(entry.learnings, 1):
            lines.append(f"{i}. {learning.content}")
    else:
        lines.append("*No learnings recorded today.*")
    lines.extend(["", "---", ""])

    # Judge Self-Mutations
    lines.append("## Judge Self-Mutations")
    if entry.belief_mutations:
        for m in entry.belief_mutations:
            lines.append(
                f'- Belief {m.mutation_type}: "{m.belief}" (strength: {m.strength})'
            )
            if m.reason:
                lines.append(f"  Reason: {m.reason}")
    else:
        lines.append("*No belief mutations today.*")
    lines.extend(["", "---", ""])

    # Open Questions
    lines.append("## Open Questions")
    if entry.open_questions:
        for q in entry.open_questions:
            lines.append(f"- [ ] {q}")
    else:
        lines.append("*No open questions today.*")
    lines.append("")

    return "\n".join(lines)


def load_entry(entry_date: str | None = None) -> JournalEntry | None:
    """Load a journal entry from its JSON backing file. Returns None if not found."""
    if entry_date is None:
        entry_date = date.today().isoformat()
    path = _json_path(entry_date)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return JournalEntry(**data)


def create_entry(entry_date: str | None = None) -> JournalEntry:
    """Create a new empty journal entry for the given date (defaults to today)."""
    if entry_date is None:
        entry_date = date.today().isoformat()
    return JournalEntry(metadata=JournalMetadata(date=entry_date))


def save_entry(entry: JournalEntry) -> Path:
    """Save a journal entry as both JSON (source of truth) and Markdown (human-readable)."""
    d = entry.metadata.date
    _atomic_write(_json_path(d), entry.model_dump_json(indent=2))
    _atomic_write(_journal_path(d), entry_to_markdown(entry))
    return _journal_path(d)


def append_to_section(
    section: str, content, entry_date: str | None = None
) -> Path:
    """Append content to a section of a journal entry. Creates entry if needed.

    Judgment appends additionally emit an OKF Decision document and feed the
    importance accumulator; Execution appends feed the accumulator at a
    default weight of 1. Both hooks are additive — journal output is
    unchanged, and hook failures are logged and never break the write.
    """
    if entry_date is None:
        entry_date = date.today().isoformat()
    entry = load_entry(entry_date) or create_entry(entry_date)

    appended = None
    section_list = getattr(entry, section, None)
    if section_list is not None and isinstance(section_list, list):
        model_cls = SECTION_MODELS.get(section)
        if model_cls and isinstance(content, dict):
            section_list.append(model_cls(**content))
        else:
            section_list.append(content)
        appended = section_list[-1]

    path = save_entry(entry)

    # Additive hooks — must never break the journal write path.
    if appended is not None:
        try:
            _record_importance(section, appended)
        except Exception as exc:
            logger.warning("Importance accumulator update failed: %s", exc)
        if section == "judgments":
            try:
                _emit_decision_doc(appended)
            except Exception as exc:
                logger.warning("OKF Decision doc emission failed: %s", exc)

    return path


# ---------------------------------------------------------------------------
# Importance accumulation — Stanford generative-agents reflection trigger
# ---------------------------------------------------------------------------


def _accumulator_path() -> Path:
    return Config.JOURNAL_DIR / ".importance-accumulator.json"


def _load_accumulator() -> dict:
    try:
        return json.loads(_accumulator_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"accumulated": 0}


def accumulated_importance() -> int:
    """The running sum of action weights since the last reflection."""
    return int(_load_accumulator().get("accumulated", 0))


def add_importance(weight: int) -> int:
    """Add weight to the persistent accumulator. Returns the new total."""
    state = _load_accumulator()
    state["accumulated"] = int(state.get("accumulated", 0)) + int(weight)
    state["updated"] = datetime.utcnow().isoformat()
    _atomic_write(_accumulator_path(), json.dumps(state, indent=2))
    return state["accumulated"]


def check_reflection_due() -> bool:
    """True when accumulated importance crossed the reflection threshold."""
    return accumulated_importance() >= Config.REFLECTION_IMPORTANCE_THRESHOLD


def reset_accumulator(consumed: int | None = None) -> None:
    """Reset the importance accumulator (call after a reflection pass runs).

    When ``consumed`` is given, only that much is subtracted (floored at 0)
    so importance accrued between the caller's check and this reset is
    preserved — avoiding a check-then-reset lost update. Without ``consumed``
    the accumulator is zeroed.
    """
    state = _load_accumulator()
    if consumed is None:
        remaining = 0
    else:
        remaining = max(0, int(state.get("accumulated", 0)) - int(consumed))
    state["accumulated"] = remaining
    state["updated"] = datetime.utcnow().isoformat()
    _atomic_write(_accumulator_path(), json.dumps(state, indent=2))


def _record_importance(section: str, item) -> None:
    """Feed the accumulator from a freshly appended journal item."""
    if section == "judgments":
        weight = getattr(item, "action_weight", _EXECUTION_DEFAULT_WEIGHT)
    elif section == "executions":
        weight = _EXECUTION_DEFAULT_WEIGHT
    else:
        return
    add_importance(weight)


# ---------------------------------------------------------------------------
# OKF Decision emission — additive audit trail for Judgment appends
# ---------------------------------------------------------------------------


def _emit_decision_doc(judgment) -> Path | None:
    """Persist a Judgment as an OKF Decision document.

    Links current (non-invalidated) Belief docs whose belief text appears in
    the judgment's reasoning. Lazy OKF import keeps the journal importable
    even if optional dependencies are missing.
    """
    from triforce.memory.okf import OKFBundle, OKFDocument

    bundle = OKFBundle()
    reasoning = getattr(judgment, "reasoning", "") or ""

    related: list[tuple[str, str]] = []
    if reasoning:
        for doc_path, doc in bundle.documents("beliefs"):
            if doc.extras.get("invalidated_at"):
                continue
            if doc.title and doc.title.lower() in reasoning.lower():
                related.append((doc.title, f"/beliefs/{doc_path.name}"))

    body_lines = ["# Reasoning", "", reasoning or "*No reasoning recorded.*", ""]
    if related:
        body_lines.extend(["## Related beliefs", ""])
        body_lines.extend(f"* [{title}]({link})" for title, link in related)
        body_lines.append("")

    doc = OKFDocument(
        type="Decision",
        title=judgment.action or "Judgment",
        description=(
            f"Verdict: {judgment.verdict} (weight {judgment.action_weight}/10)"
        ),
        tags=["judge", "decision"],
        timestamp=judgment.timestamp,
        extras={
            "verdict": judgment.verdict,
            "action_weight": judgment.action_weight,
        },
        body="\n".join(body_lines),
    )
    return bundle.write(doc, "decisions", action="Judgment")
