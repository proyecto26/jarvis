"""Executor agent — fast-model frontline that acts on Judge-approved plans."""

from google.adk.agents import Agent

from triforce.config import Config
from triforce.tools.state_tools import append_to_state
from triforce.agents.executor.prompts import EXECUTOR_INSTRUCTION

executor_agent = Agent(
    name="executor",
    model=Config.EXECUTOR_MODEL,
    description="Executes approved plans. The only agent that speaks to the outside world.",
    instruction=EXECUTOR_INSTRUCTION,
    tools=[append_to_state],
)
