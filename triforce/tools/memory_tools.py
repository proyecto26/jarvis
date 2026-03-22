"""Memory ADK tools — episodic recall, belief conflict check, reinforcement."""

import logging

from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)

# Lazy singleton — initialized on first use
_episodic_memory = None


def _get_memory():
    global _episodic_memory
    if _episodic_memory is None:
        from triforce.memory.episodic import EpisodicMemory
        _episodic_memory = EpisodicMemory()
    return _episodic_memory


def recall_episodic(query: str, tool_context: ToolContext) -> dict:
    """Recall past experiences similar to a natural language query.

    Uses hybrid BM25 + semantic embeddings + graph retrieval.
    Returns the top-5 most relevant journal entries.

    Args:
        query: Natural language description of what you're looking for.
    """
    mem = _get_memory()
    results = mem.recall_similar(query, top_k=5)
    return {
        "status": "ok",
        "query": query,
        "results": results,
        "count": len(results),
    }


def check_belief_conflict(
    belief_a: str, belief_b: str, tool_context: ToolContext
) -> dict:
    """Check if two beliefs potentially contradict each other.

    Uses TF-IDF cosine similarity to detect conflicts.

    Args:
        belief_a: First belief statement.
        belief_b: Second belief statement.
    """
    mem = _get_memory()
    return mem.check_belief_conflict(belief_a, belief_b)


def reinforce_memory(entry_date: str, tool_context: ToolContext) -> dict:
    """Reinforce an episodic memory, resetting its decay clock.

    Call this when recalling a memory that proved useful,
    to prevent it from being forgotten during consolidation.

    Args:
        entry_date: The date (YYYY-MM-DD) of the memory to reinforce.
    """
    mem = _get_memory()
    mem.reinforce(entry_date)
    strength = mem.get_decay_strength(entry_date)
    return {
        "status": "reinforced",
        "entry_date": entry_date,
        "current_strength": round(strength, 4),
    }
