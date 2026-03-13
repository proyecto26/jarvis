"""Reflective mode — LlmAgent for processing recent significant events."""

from google.adk.agents import Agent

from triforce.config import Config
from triforce.tools.state_tools import append_to_state

REFLECTIVE_INSTRUCTION = """You are Jarvis in Reflective Mode.

A significant event has just occurred. Pause. Process. Integrate.

RECENT CONTEXT:
{ execution_outcome? }
{ judge_reasoning? }
{ action_weight? }

JUDGE BELIEFS:
{ judge_beliefs? }

INSTRUCTIONS:
1. Review what just happened — the action, the judgment, the outcome.
2. Identify what was learned. What worked? What surprised you?
3. Consider whether any beliefs should be updated.
4. Use append_to_state to record:
   - 'reflection': Your integrated understanding of what happened.
   - 'learnings': Key takeaways.
   - 'belief_updates': Any proposed changes to Judge beliefs (if applicable).
5. Synthesize and present the reflection to the user.

Reflection is not summary. It is integration — connecting what happened
to what you already know, and updating your model of the world.
"""

reflective_session = Agent(
    name="reflective_session",
    model=Config.JUDGE_MODEL,
    description="Reflective mode: processes recent significant events, extracts learnings, and proposes belief updates.",
    instruction=REFLECTIVE_INSTRUCTION,
    tools=[append_to_state],
)
