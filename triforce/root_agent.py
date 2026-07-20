"""Root dispatcher — routes to operating modes based on context.

Durability note: every mode below runs in-process via ADK. Durable execution is
NOT wired at this dispatcher — it is an opt-in escalation that happens one level
down, inside awake_pipeline's Executor. When Config.DANTE_DURABLE_AWAKE is on the
Executor gains the escalate_to_durable_workflow tool and can hand a high-weight
(action_weight >= 4) or long-running task to the durable Temporal AwakeWorkflow;
by default nothing here starts a workflow. See triforce/temporal/client.py and
TEMPORAL.md.
"""

from google.adk.agents import Agent

from triforce.config import Config
from triforce.modes.awake import awake_pipeline
from triforce.modes.sleep import dream_state
from triforce.modes.reflective import reflective_session

ROOT_INSTRUCTION = """You are JARVIS — the integration of Dreamer, Judge, and Executor.

OPERATING MODES:

AWAKE (default): User is present. Action is needed.
  -> Transfer to: awake_pipeline
  When: Any user message requiring action, response, or judgment.

REFLECTIVE: A significant event just occurred. Pause and process.
  -> Transfer to: reflective_session
  When: After execution with high action_weight (>= 6), or user says "let's reflect" or "what did we learn".

SLEEP: No active task. Time for deep exploration.
  -> Transfer to: dream_state
  When: User says "think deeply", "dream", "explore", or asks for free-form brainstorming.

ROUTING RULES:
- Default to awake_pipeline for most user messages.
- Use dream_state only when explicitly triggered or when creative deep exploration is requested.
- Use reflective_session when the user wants to process recent events or extract learnings.
- After dream_state completes, the 'breakthrough' state key contains the distilled insight.

Current mode context: { mode_context? }
"""

root_agent = Agent(
    name="jarvis",
    model=Config.ROOT_MODEL,
    description="JARVIS — the AGI Trinity. Routes to Awake, Sleep, or Reflective operating modes.",
    instruction=ROOT_INSTRUCTION,
    sub_agents=[awake_pipeline, dream_state, reflective_session],
)
