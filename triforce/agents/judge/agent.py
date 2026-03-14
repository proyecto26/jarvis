"""Judge agent — dual-mode: filter (awake) and collaborator (sleep)."""

import json
import logging
import pathlib

from google.adk.agents import Agent
from google.adk.tools import ToolContext

from triforce.config import Config
from triforce.tools.state_tools import append_to_state, exit_loop
from triforce.agents.judge.prompts import FILTER_PROMPT, COLLABORATOR_PROMPT

logger = logging.getLogger(__name__)

FILTER_SKILLS = pathlib.Path(__file__).parent / "skills-filter"
COLLABORATOR_SKILLS = pathlib.Path(__file__).parent / "skills-collaborator"
SHARED_SKILLS = pathlib.Path(__file__).parent.parent.parent / "skills"


def _load_skill_toolsets(*skill_dirs: pathlib.Path) -> list:
    """Load SkillToolset from one or more directories, with graceful fallback."""
    try:
        from google.adk.skills import load_skill_from_dir
        from google.adk.tools.skill_toolset import SkillToolset

        all_dirs = []
        for base in skill_dirs:
            if base.is_dir():
                all_dirs.extend(
                    p for p in base.iterdir() if p.is_dir() and not p.name.startswith("_")
                )
        if all_dirs:
            logger.info("Judge: loaded %d skills from %s", len(all_dirs), [d.name for d in skill_dirs])
            return [SkillToolset(skills=[load_skill_from_dir(p) for p in all_dirs])]
    except (ImportError, AttributeError) as exc:
        logger.warning("ADK SkillToolset not available — running without skills: %s", exc)
    return []


def recall_similar_decisions(situation: str, tool_context: ToolContext) -> dict:
    """Retrieve past beliefs and decisions relevant to the current situation.

    Searches the Judge's accumulated beliefs for entries matching the
    described situation. Phase 2 will add Mem0 episodic retrieval.

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
    tools=[append_to_state, recall_similar_decisions] + _load_skill_toolsets(FILTER_SKILLS, SHARED_SKILLS),
)

judge_collaborator = Agent(
    name="judge_collaborator",
    model=Config.JUDGE_MODEL,
    description="Connects Dreamer's ideas to past experience. Exits the dream loop when a breakthrough occurs.",
    instruction=COLLABORATOR_PROMPT,
    tools=[append_to_state, exit_loop, recall_similar_decisions] + _load_skill_toolsets(COLLABORATOR_SKILLS, SHARED_SKILLS),
)
