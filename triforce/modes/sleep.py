"""Sleep mode — LoopAgent dream cycle: Dreamer generates, Judge connects, until breakthrough."""

from google.adk.agents import LoopAgent

from triforce.agents.dreamer import dreamer_agent
from triforce.agents.judge import judge_collaborator

dream_state = LoopAgent(
    name="dream_state",
    description="Sleep cycle. Dreamer and Judge-as-collaborator iterate until breakthrough or max cycles reached.",
    sub_agents=[dreamer_agent, judge_collaborator],
    max_iterations=8,
)
