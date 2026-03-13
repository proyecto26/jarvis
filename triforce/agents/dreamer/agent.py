"""Dreamer agent — unconstrained idea generation using a high-reasoning model."""

from google.adk.agents import Agent

from triforce.config import Config
from triforce.tools.state_tools import append_to_state
from triforce.agents.dreamer.prompts import DREAMER_INSTRUCTION

dreamer_agent = Agent(
    name="dreamer",
    model=Config.DREAMER_MODEL,
    description="Generates unconstrained ideas, visions, and connections. The subconscious.",
    instruction=DREAMER_INSTRUCTION,
    tools=[append_to_state],
)
