"""Dreamer agent — unconstrained idea generation using a high-reasoning model."""

import logging
import pathlib

from google.adk.agents import Agent

from triforce.config import Config
from triforce.tools.state_tools import append_to_state
from triforce.agents.dreamer.prompts import DREAMER_INSTRUCTION

logger = logging.getLogger(__name__)

DREAMER_SKILLS = pathlib.Path(__file__).parent / "skills"
SHARED_SKILLS = pathlib.Path(__file__).parent.parent.parent / "skills"

_skill_toolsets: list = []
try:
    from google.adk.skills import load_skill_from_dir
    from google.adk.tools.skill_toolset import SkillToolset

    _skill_dirs = [
        p
        for base in (DREAMER_SKILLS, SHARED_SKILLS)
        for p in base.iterdir()
        if p.is_dir() and not p.name.startswith("_") and (p / "SKILL.md").is_file()
    ]
    if _skill_dirs:
        _skill_toolsets = [
            SkillToolset(skills=[load_skill_from_dir(p) for p in _skill_dirs])
        ]
        logger.info("Dreamer: loaded %d skills", len(_skill_dirs))
except Exception as exc:  # noqa: BLE001 — skills are optional; never crash imports
    logger.warning("ADK skills unavailable or malformed — running without skills: %s", exc)

dreamer_agent = Agent(
    name="dreamer",
    model=Config.model_for("dreamer", Config.DREAMER_MODEL),
    description="Generates unconstrained ideas, visions, and connections. The subconscious.",
    instruction=DREAMER_INSTRUCTION,
    tools=[append_to_state] + _skill_toolsets,
)
