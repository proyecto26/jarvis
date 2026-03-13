"""Awake mode — SequentialAgent pipeline: Judge evaluates, then Executor acts."""

from google.adk.agents import SequentialAgent

from triforce.agents.judge import judge_filter
from triforce.agents.executor import executor_agent

awake_pipeline = SequentialAgent(
    name="awake_pipeline",
    description="Awake mode: Judge evaluates the request, then Executor carries out the approved action.",
    sub_agents=[judge_filter, executor_agent],
)
