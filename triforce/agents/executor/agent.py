"""Executor agent — fast-model frontline that acts on Judge-approved plans."""

import logging
import pathlib

from google.adk.agents import Agent

from triforce.config import Config
from triforce.tools.state_tools import append_to_state
from triforce.tools.journal_tools import write_journal_entry
from triforce.agents.executor.prompts import EXECUTOR_INSTRUCTION

logger = logging.getLogger(__name__)

EXECUTOR_SKILLS = pathlib.Path(__file__).parent / "skills"
SHARED_SKILLS = pathlib.Path(__file__).parent.parent.parent / "skills"

_skill_toolsets: list = []
try:
    from google.adk.skills import load_skill_from_dir
    from google.adk.tools.skill_toolset import SkillToolset

    _skill_dirs = [
        p for p in EXECUTOR_SKILLS.iterdir() if p.is_dir() and not p.name.startswith("_")
    ] + [
        p for p in SHARED_SKILLS.iterdir() if p.is_dir() and not p.name.startswith("_")
    ]
    if _skill_dirs:
        _skill_toolsets = [
            SkillToolset(skills=[load_skill_from_dir(p) for p in _skill_dirs])
        ]
        logger.info("Executor: loaded %d skills", len(_skill_dirs))
except (ImportError, AttributeError) as exc:
    logger.warning("ADK SkillToolset not available — running without skills: %s", exc)

executor_agent = Agent(
    name="executor",
    model=Config.EXECUTOR_MODEL,
    description="Executes approved plans. The only agent that speaks to the outside world.",
    instruction=EXECUTOR_INSTRUCTION,
    tools=[append_to_state, write_journal_entry] + _skill_toolsets,
)
