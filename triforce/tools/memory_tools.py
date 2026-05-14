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


def update_beliefs(
    belief: str,
    strength: float,
    reason: str,
    tool_context: ToolContext,
) -> dict:
    """Propose a new or updated belief, with SSGM conflict check before writing.

    Runs the Self-Supervised Goal Mutation conflict check against existing
    high-strength beliefs first. If a conflict is detected, the write is
    paused and the conflict report is returned to the caller for resolution.

    Args:
        belief: The belief statement.
        strength: Belief strength, 0.0 to 1.0.
        reason: Why this belief is held; required for auditability.
    """
    from triforce.memory.beliefs import add_belief, update_belief
    from triforce.memory.ssgm import SSGMGuard

    guard = SSGMGuard()
    conflict = guard.check_conflict(belief)

    if conflict.has_conflict:
        return {
            "status": "conflict_detected",
            "conflict": conflict.to_dict(),
            "action_required": "Resolve via merge, supersede, coexist, or review before writing.",
        }

    # No conflict — write the belief
    existing = update_belief(belief, strength=strength, reason=reason)
    if existing is not None:
        return {
            "status": "updated",
            "belief": belief,
            "strength": strength,
        }

    new_belief = add_belief(belief, strength=strength, reason=reason)
    return {
        "status": "created",
        "belief": new_belief["belief"],
        "strength": new_belief["strength"],
    }


def recall_similar_decisions(situation: str, tool_context: ToolContext) -> dict:
    """Retrieve past decisions relevant to the current situation.

    Uses the episodic memory (BM25 + embeddings + graph hybrid retrieval) when
    available; falls back to the flat JSON belief store when the episodic index
    has no entries yet.

    Args:
        situation: Description of the current situation.
    """
    mem = _get_memory()
    results = mem.recall_similar(situation, top_k=5)

    if results:
        tool_context.state["relevant_episodes"] = results
        return {
            "status": "ok",
            "source": "episodic",
            "situation": situation,
            "results": results,
        }

    # Fallback: flat beliefs JSON
    from triforce.memory.beliefs import load_beliefs

    beliefs = load_beliefs()
    tool_context.state["relevant_beliefs"] = beliefs
    return {
        "status": "ok",
        "source": "beliefs_json_fallback",
        "situation": situation,
        "relevant_beliefs": beliefs,
    }
