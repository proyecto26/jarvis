"""Data types for the LLM router.

Pure dataclasses — no provider imports. Safe to import from anywhere in the
package without pulling in heavy dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional


PrivacyClass = Literal["cloud-ok", "local-preferred", "local-only"]
"""Privacy constraint on a request.

- ``cloud-ok``: any provider may be selected.
- ``local-preferred``: prefer local providers; cloud allowed if no local
  candidate meets the latency/capability budget.
- ``local-only``: refuse to route to a cloud provider even if no local
  candidate is available — raise ``LocalOnlyRouteFailure`` instead.
"""


class Capability(str, Enum):
    """Capabilities a model may declare in the registry."""

    REASONING = "reasoning"
    TOOLS = "tools"
    FUNCTION_CALLING = "function_calling"
    VISION = "vision"
    LONG_CONTEXT = "long_context"
    LOW_LATENCY = "low_latency"
    LOW_COST = "low_cost"


@dataclass(frozen=True)
class Model:
    """A model registry entry.

    Models are declared in ``triforce/llm/models.yaml`` and loaded by
    ``Registry``. Each entry describes how to invoke the model and what it can
    do — the router scores candidates by matching capabilities to the request.
    """

    id: str
    provider: str  # matches a Provider implementation name (e.g. "gemini", "ollama")
    base_id: str  # provider-specific model identifier (e.g. "gemini-3.5-flash")
    capabilities: frozenset[str] = field(default_factory=frozenset)
    context_window: int = 8_000
    p95_latency_ms: int = 1_000
    cost_per_1k_tokens_usd: float = 0.0
    is_local: bool = False
    supports_tools: bool = True
    supports_vision: bool = False
    tags: frozenset[str] = field(default_factory=frozenset)

    def has(self, capability: str) -> bool:
        return capability in self.capabilities


@dataclass(frozen=True)
class Adapter:
    """A LoRA / fine-tuning adapter that specializes a base model for a task.

    Adapters live in ``triforce/llm/adapters/`` with a manifest describing
    their base model and task tags. The router pairs an adapter with its base
    model when both are available.
    """

    id: str
    base_model_id: str
    task_tags: frozenset[str]
    path: str = ""  # filesystem path to the .safetensors file
    eval_score: Optional[float] = None
    description: str = ""


@dataclass
class RouteRequest:
    """Input to ``Router.route()``.

    Describes one LLM call: who is calling, what task it is, what constraints
    must hold, and how long the caller is willing to wait.
    """

    agent: str  # "dreamer" | "judge_filter" | "judge_collaborator" | "executor" | ...
    task_type: str = "general"  # matches adapter tags (e.g. "ethics-evaluation")
    privacy_class: PrivacyClass = "cloud-ok"
    max_latency_ms: int = 5_000
    requires_vision: bool = False
    requires_tools: bool = True
    requires_long_context: bool = False
    max_input_tokens: int = 8_000
    # Optional override — if set, bypasses normal routing logic
    forced_model_id: Optional[str] = None
    # Caller-supplied context that gets stamped into the decision log
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RouteDecision:
    """Output of ``Router.route()``.

    Contains the selected model + provider, optional adapter pairing, and the
    full reasoning trace. The decision is logged to
    ``journal/llm-routing/YYYY-MM-DD.jsonl`` for later audit.
    """

    request_signature: str
    model: Model
    adapter: Optional[Adapter] = None
    provider_name: str = ""
    reasoning: tuple[str, ...] = field(default_factory=tuple)
    candidates_considered: tuple[str, ...] = field(default_factory=tuple)
    fallback_depth: int = 0  # how deep into the policy's fallback_chain we went

    @property
    def model_id(self) -> str:
        return self.model.id

    @property
    def is_local(self) -> bool:
        return self.model.is_local

    @property
    def decision_id(self) -> str:
        """Stable identifier for this decision — used by Temporal replay."""
        import hashlib

        payload = f"{self.request_signature}|{self.model.id}|{(self.adapter.id if self.adapter else '')}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]
