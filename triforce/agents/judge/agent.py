"""Judge agent — dual-mode: filter (awake) and collaborator (sleep)."""

import json

from google.adk.agents import Agent
from google.adk.tools import ToolContext

from triforce.config import Config
from triforce.tools.state_tools import append_to_state, exit_loop
from triforce.agents.judge.prompts import FILTER_PROMPT, COLLABORATOR_PROMPT


def recall_similar_decisions(situation: str, tool_context: ToolContext) -> dict:
    """Retrieve past beliefs and decisions relevant to the current situation.

    Searches the Judge's accumulated beliefs for entries matching the
    described situation. Phase 2 will add PageIndex journal retrieval.

    Args:
        situation: Description of the current situation to find relevant past decisions for.
    """
    try:
        data = json.loads(Config.BELIEFS_PATH.read_text())
        beliefs = data.get("beliefs", [])
    except (FileNotFoundError, json.JSONDecodeError):
        beliefs = []
    formatted = json.dumps(beliefs, indent=2) if beliefs else "No beliefs recorded yet."
    tool_context.state["judge_beliefs"] = formatted
    return {"relevant_beliefs": beliefs}


judge_filter = Agent(
    name="judge_filter",
    model=Config.JUDGE_MODEL,
    description="Evaluates proposed actions against ethics, alignment, reversibility, and weight. Gates execution.",
    instruction=FILTER_PROMPT,
    tools=[append_to_state, recall_similar_decisions],
)

judge_collaborator = Agent(
    name="judge_collaborator",
    model=Config.JUDGE_MODEL,
    description="Connects Dreamer's ideas to past experience. Exits the dream loop when a breakthrough occurs.",
    instruction=COLLABORATOR_PROMPT,
    tools=[append_to_state, exit_loop],
)
