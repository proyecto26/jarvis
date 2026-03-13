"""Pydantic models for the journal and beliefs system."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DreamCycle(BaseModel):
    """A single dream cycle from Sleep mode."""

    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    seed: str = ""
    branches: list[str] = Field(default_factory=list)
    depth_reached: int = 0
    breakthrough: Optional[str] = None


class Judgment(BaseModel):
    """A decision made by the Judge."""

    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    action: str = ""
    action_weight: int = 1
    verdict: str = "approved"
    reasoning: str = ""
    original: Optional[str] = None
    modified: Optional[str] = None


class Execution(BaseModel):
    """An action taken by the Executor."""

    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    action: str = ""
    status: str = "completed"
    outcome: str = ""
    artifacts: list[str] = Field(default_factory=list)


class Learning(BaseModel):
    """A learning extracted during reflection."""

    content: str
    source_mode: str = "reflective"


class BeliefMutation(BaseModel):
    """A change to the Judge's beliefs."""

    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    mutation_type: str = "updated"
    belief: str = ""
    strength: float = 0.5
    reason: str = ""


class JournalMetadata(BaseModel):
    """Metadata for a daily journal entry."""

    date: str
    mode_cycles: dict[str, int] = Field(default_factory=dict)
    active_skills: list[str] = Field(default_factory=list)
    dominant_theme: str = ""


class JournalEntry(BaseModel):
    """A complete daily journal entry."""

    metadata: JournalMetadata
    dreams: list[DreamCycle] = Field(default_factory=list)
    judgments: list[Judgment] = Field(default_factory=list)
    executions: list[Execution] = Field(default_factory=list)
    learnings: list[Learning] = Field(default_factory=list)
    belief_mutations: list[BeliefMutation] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    connections: list[str] = Field(default_factory=list)
