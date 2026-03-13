"""Journal ADK tools — write and read journal entries."""

import json as _json
from datetime import date

from google.adk.tools import ToolContext

from triforce.memory.journal import (
    append_to_section,
    create_entry,
    entry_to_markdown,
    load_entry,
    save_entry,
)


def write_journal_entry(
    section: str, content: str, tool_context: ToolContext
) -> dict:
    """Append an entry to a section of today's journal.

    Args:
        section: Section to write to (dreams, judgments, executions, learnings, belief_mutations, open_questions, connections).
        content: JSON string for structured sections or plain text for simple list sections.
    """
    try:
        parsed = _json.loads(content)
    except (ValueError, TypeError):
        parsed = content

    path = append_to_section(section, parsed)
    return {"status": "written", "file": str(path), "section": section}


def read_journal(entry_date: str, tool_context: ToolContext) -> dict:
    """Read a journal entry for a given date.

    Args:
        entry_date: Date in YYYY-MM-DD format.
    """
    if not entry_date:
        entry_date = date.today().isoformat()

    entry = load_entry(entry_date)
    if entry is None:
        return {"status": "not_found", "date": entry_date}

    return {
        "status": "found",
        "date": entry_date,
        "content": entry_to_markdown(entry),
    }
