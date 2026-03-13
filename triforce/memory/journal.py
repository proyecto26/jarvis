"""Journal file I/O — create, load, and append to daily Markdown files."""

import json
import tempfile
from datetime import date
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

SECTION_MODELS = {
    "dreams": DreamCycle,
    "judgments": Judgment,
    "executions": Execution,
    "learnings": Learning,
    "belief_mutations": BeliefMutation,
}


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
        tmp.write_text(content)
        tmp.rename(path)
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
    data = json.loads(path.read_text())
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
    """Append content to a section of a journal entry. Creates entry if needed."""
    if entry_date is None:
        entry_date = date.today().isoformat()
    entry = load_entry(entry_date) or create_entry(entry_date)

    section_list = getattr(entry, section, None)
    if section_list is not None and isinstance(section_list, list):
        model_cls = SECTION_MODELS.get(section)
        if model_cls and isinstance(content, dict):
            section_list.append(model_cls(**content))
        else:
            section_list.append(content)

    return save_entry(entry)
