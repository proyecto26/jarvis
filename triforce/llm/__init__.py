"""LLM Router — declarative model selection for the Trinity agents.

The router picks the best (model, adapter, provider) for each LLM call based
on a structured RouteRequest and a YAML policy file. Designed for local-first
operation with cloud fallback (Gemini) only when allowed by the request's
privacy class.

Public API:
    Router          — the routing engine
    RouteRequest    — input describing the task and constraints
    RouteDecision   — output describing which model was selected and why
"""

from triforce.llm.types import (
    RouteRequest,
    RouteDecision,
    Model,
    Adapter,
    PrivacyClass,
)
from triforce.llm.errors import (
    LocalOnlyRouteFailure,
    NoCandidateError,
    ProviderUnhealthy,
)

__all__ = [
    "RouteRequest",
    "RouteDecision",
    "Model",
    "Adapter",
    "PrivacyClass",
    "LocalOnlyRouteFailure",
    "NoCandidateError",
    "ProviderUnhealthy",
]
