"""Executor agent — fast-model frontline that acts on Judge-approved plans."""

import logging
import pathlib

from google.adk.agents import Agent

from triforce.config import Config
from triforce.tools.state_tools import append_to_state
from triforce.tools.journal_tools import write_journal_entry
from triforce.tools.memory_tools import recall_episodic, check_belief_conflict, reinforce_memory
from triforce.agents.executor.prompts import EXECUTOR_INSTRUCTION

logger = logging.getLogger(__name__)

EXECUTOR_SKILLS = pathlib.Path(__file__).parent / "skills"
SHARED_SKILLS = pathlib.Path(__file__).parent.parent.parent / "skills"

_skill_toolsets: list = []
try:
    from google.adk.skills import load_skill_from_dir
    from google.adk.tools.skill_toolset import SkillToolset

    _skill_dirs = [
        p
        for base in (EXECUTOR_SKILLS, SHARED_SKILLS)
        for p in base.iterdir()
        if p.is_dir() and not p.name.startswith("_") and (p / "SKILL.md").is_file()
    ]
    if _skill_dirs:
        _skill_toolsets = [
            SkillToolset(skills=[load_skill_from_dir(p) for p in _skill_dirs])
        ]
        logger.info("Executor: loaded %d skills", len(_skill_dirs))
except Exception as exc:  # noqa: BLE001 — skills are optional; never crash imports
    logger.warning("ADK skills unavailable or malformed — running without skills: %s", exc)

# Opt-in durable escalation seam. Off by default: the tool list is identical to
# before, so the in-process ADK chat path the UI depends on is unchanged. When
# DANTE_DURABLE_AWAKE is on, the Executor is offered escalate_to_durable_workflow
# so a high-weight (action_weight >= 4) or long-running task can be handed to the
# durable Temporal AwakeWorkflow. The tool degrades gracefully when Temporal is
# unreachable, so enabling the flag never crashes a turn. See TEMPORAL.md.
_durable_tools: list = []
if Config.durable_awake_enabled():
    from triforce.tools.temporal_tools import escalate_to_durable_workflow

    _durable_tools = [escalate_to_durable_workflow]
    logger.info("Executor: durable Awake escalation enabled (DANTE_DURABLE_AWAKE)")

executor_agent = Agent(
    name="executor",
    model=Config.model_for("executor", Config.EXECUTOR_MODEL),
    description="Executes approved plans. The only agent that speaks to the outside world.",
    instruction=EXECUTOR_INSTRUCTION,
    tools=[
        append_to_state, write_journal_entry,
        recall_episodic, check_belief_conflict, reinforce_memory,
    ] + _durable_tools + _skill_toolsets,
)
