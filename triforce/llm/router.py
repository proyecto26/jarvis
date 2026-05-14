"""Router engine — selects (model, adapter, provider) for each RouteRequest.

The router is a pure function of (request, registry, policy, provider_health).
It walks the policy's fallback chain top-to-bottom, picking the first
candidate that satisfies the step's constraints. Every decision is logged via
the observability module.

Privacy contract:
- ``local-only`` requests NEVER fall back to cloud. They raise
  ``LocalOnlyRouteFailure`` if no local candidate is available.
- ``local-preferred`` prefers local but allows cloud when the policy permits.
- ``cloud-ok`` allows any candidate.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

from triforce.llm.errors import (
    LocalOnlyRouteFailure,
    NoCandidateError,
)
from triforce.llm.observability import log_decision
from triforce.llm.policies.loader import FallbackStep, Policy, load_policy
from triforce.llm.providers import all_providers, get_provider
from triforce.llm.registry import Registry, get_registry
from triforce.llm.types import (
    Adapter,
    Model,
    PrivacyClass,
    RouteDecision,
    RouteRequest,
)

logger = logging.getLogger(__name__)

DEFAULT_FALLBACK_MODEL_ID = "gemini-1.5-pro"


def _signature(request: RouteRequest) -> str:
    """Stable short hash that identifies a request shape (not the content)."""
    payload = json.dumps(
        {
            "agent": request.agent,
            "task_type": request.task_type,
            "privacy_class": request.privacy_class,
            "max_latency_ms": request.max_latency_ms,
            "requires_vision": request.requires_vision,
            "requires_tools": request.requires_tools,
            "requires_long_context": request.requires_long_context,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def _privacy_allows_cloud(pc: PrivacyClass) -> bool:
    return pc in ("cloud-ok", "local-preferred")


def _privacy_forbids_cloud(pc: PrivacyClass) -> bool:
    return pc == "local-only"


# Privacy classes ordered from strictest to most permissive. The router uses
# the strictest of (request, step) — a policy step cannot relax the user's
# constraint.
_PRIVACY_STRICTNESS = {"local-only": 2, "local-preferred": 1, "cloud-ok": 0}


def _effective_privacy(
    request_pc: PrivacyClass, step_pc: Optional[PrivacyClass]
) -> PrivacyClass:
    if step_pc is None:
        return request_pc
    if _PRIVACY_STRICTNESS[step_pc] >= _PRIVACY_STRICTNESS[request_pc]:
        return step_pc
    return request_pc


def _score(model: Model, step: FallbackStep, policy: Policy) -> float:
    """Score a candidate against a step. Higher is better.

    Scoring components (all additive):
      +10 per matched "prefer" capability
      +5  per matched "prefer_tags" tag
      +3  if model is local and step.prefer_local
      -1  per millisecond of P95 latency / 100 (penalty for slow models)
    """
    score = 0.0
    score += 10 * sum(1 for cap in policy.prefer if cap in model.capabilities)
    score += 5 * sum(1 for tag in policy.prefer_tags if tag in model.tags)
    if step.prefer_local and model.is_local:
        score += 3
    score -= model.p95_latency_ms / 100.0
    return score


def _meets_must_have(
    model: Model, must_have: frozenset[str], step_caps: frozenset[str]
) -> bool:
    required = must_have | step_caps
    return all(cap in model.capabilities for cap in required)


def _within_latency(
    model: Model, policy: Policy, step: FallbackStep, request: RouteRequest
) -> bool:
    # The tightest of (step override, request budget, policy default) wins
    candidates = [
        step.max_latency_ms,
        request.max_latency_ms,
        policy.max_latency_ms,
    ]
    budget = min(c for c in candidates if c is not None)
    return model.p95_latency_ms <= budget


def _within_privacy(model: Model, request: RouteRequest, step: FallbackStep) -> bool:
    pc = _effective_privacy(request.privacy_class, step.privacy_class)
    if _privacy_forbids_cloud(pc) and not model.is_local:
        return False
    return True


def _provider_healthy(model: Model) -> bool:
    provider = get_provider(model.provider)
    if provider is None:
        return False
    return provider.health(timeout_ms=200)


class Router:
    """Selects (model, adapter, provider) for each RouteRequest."""

    def __init__(self, registry: Optional[Registry] = None) -> None:
        self._registry = registry or get_registry()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(self, request: RouteRequest) -> RouteDecision:
        """Resolve a single routing decision."""
        signature = _signature(request)

        # Forced overrides bypass policy walking
        if request.forced_model_id:
            model = self._registry.get(request.forced_model_id)
            if model is None:
                raise NoCandidateError(
                    f"forced_model_id={request.forced_model_id!r} not in registry"
                )
            decision = RouteDecision(
                request_signature=signature,
                model=model,
                provider_name=model.provider,
                reasoning=(f"forced_model_id={request.forced_model_id} bypasses policy",),
                candidates_considered=(model.id,),
                fallback_depth=0,
            )
            log_decision(request, decision, reason="forced_override")
            return decision

        # Look up policy for this agent
        policy = load_policy(request.agent)
        reasoning: list[str] = []
        candidates_log: list[str] = []

        if policy is None:
            reasoning.append(f"no policy for agent={request.agent!r}; using default")
            policy = Policy(
                agent=request.agent,
                default_privacy_class=request.privacy_class,
                max_latency_ms=request.max_latency_ms,
                fallback_chain=(FallbackStep(),),
                on_no_candidate="use_default_gemini",
            )

        # Walk the fallback chain
        for depth, step in enumerate(policy.fallback_chain):
            reasoning.append(f"step {depth}: caps={sorted(step.capability_match)}")
            picked = self._try_step(request, policy, step, candidates_log, reasoning)
            if picked is not None:
                model, adapter = picked
                decision = RouteDecision(
                    request_signature=signature,
                    model=model,
                    adapter=adapter,
                    provider_name=model.provider,
                    reasoning=tuple(reasoning),
                    candidates_considered=tuple(candidates_log),
                    fallback_depth=depth,
                )
                log_decision(request, decision, reason="matched_in_fallback_chain")
                return decision

        # Exhausted the chain
        pc = request.privacy_class
        if _privacy_forbids_cloud(pc):
            log_decision(
                request,
                None,
                reason="refused_cloud_fallback",
                level="warning",
                reasoning=reasoning,
                candidates_considered=candidates_log,
            )
            raise LocalOnlyRouteFailure(
                f"No local candidate satisfies request agent={request.agent}; "
                "privacy_class=local-only forbids cloud fallback"
            )

        # on_no_candidate handling
        if policy.on_no_candidate == "use_default_gemini":
            fallback = self._registry.get(DEFAULT_FALLBACK_MODEL_ID)
            if fallback is None:
                raise NoCandidateError(
                    f"Default fallback {DEFAULT_FALLBACK_MODEL_ID!r} missing from registry"
                )
            reasoning.append(f"exhausted chain; using default {DEFAULT_FALLBACK_MODEL_ID}")
            decision = RouteDecision(
                request_signature=signature,
                model=fallback,
                provider_name=fallback.provider,
                reasoning=tuple(reasoning),
                candidates_considered=tuple(candidates_log),
                fallback_depth=len(policy.fallback_chain),
            )
            log_decision(request, decision, reason="default_fallback_after_exhaustion")
            return decision

        if policy.on_no_candidate == "escalate":
            log_decision(
                request,
                None,
                reason="no_candidate_escalate",
                level="warning",
                reasoning=reasoning,
                candidates_considered=candidates_log,
            )
            raise NoCandidateError(
                f"No candidate for agent={request.agent}; policy says escalate"
            )

        # on_no_candidate == "error"
        log_decision(
            request,
            None,
            reason="no_candidate_error",
            level="error",
            reasoning=reasoning,
            candidates_considered=candidates_log,
        )
        raise NoCandidateError(
            f"No candidate for agent={request.agent}; fallback chain exhausted"
        )

    def for_agent(self, agent: str, **kwargs) -> str:
        """Convenience: resolve and return the model.base_id for an agent.

        Used by agent.py modules that need a stringly-typed model for the ADK
        ``Agent(model=...)`` constructor.
        """
        request = RouteRequest(agent=agent, **kwargs)
        decision = self.route(request)
        return decision.model.base_id

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _try_step(
        self,
        request: RouteRequest,
        policy: Policy,
        step: FallbackStep,
        candidates_log: list[str],
        reasoning: list[str],
    ) -> Optional[tuple[Model, Optional[Adapter]]]:
        """Score every registry model against the step; return the best match."""
        privacy = _effective_privacy(request.privacy_class, step.privacy_class)
        is_local_allowed = True  # local always allowed
        is_cloud_allowed = _privacy_allows_cloud(privacy)

        candidates = self._registry.candidates(
            is_local_allowed=is_local_allowed,
            is_cloud_allowed=is_cloud_allowed,
            requires_tools=request.requires_tools,
            requires_vision=request.requires_vision,
        )

        scored: list[tuple[Model, float]] = []
        for m in candidates:
            candidates_log.append(m.id)

            if not _meets_must_have(m, policy.must_have, step.capability_match):
                continue
            if not _within_latency(m, policy, step, request):
                continue
            if not _within_privacy(m, request, step):
                continue
            if not _provider_healthy(m):
                reasoning.append(f"  skip {m.id}: provider {m.provider} unhealthy")
                continue

            score = _score(m, step, policy)
            scored.append((m, score))

        if not scored:
            return None

        scored.sort(key=lambda x: x[1], reverse=True)
        best, best_score = scored[0]
        reasoning.append(f"  picked {best.id} (score={best_score:.1f})")

        # Match adapter if one specializes for this task_type
        adapters = self._registry.find_adapters_for(best.id, request.task_type)
        adapter = adapters[0] if adapters else None
        if adapter:
            reasoning.append(f"  + adapter {adapter.id} for task={request.task_type}")

        return best, adapter


# Module-level singleton for cheap access
_ROUTER: Optional[Router] = None


def get_router() -> Router:
    global _ROUTER
    if _ROUTER is None:
        _ROUTER = Router()
    return _ROUTER
