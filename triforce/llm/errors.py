"""Exceptions raised by the LLM router."""

from __future__ import annotations


class RouterError(Exception):
    """Base class for router errors."""


class NoCandidateError(RouterError):
    """No model in the registry satisfies the request constraints.

    Raised when the fallback chain is exhausted without finding any healthy
    candidate that meets the policy's must-have capabilities and privacy
    class.
    """


class ProviderUnhealthy(RouterError):
    """A provider failed its health check.

    The router demotes unhealthy providers and continues; this exception is
    raised only if every candidate provider is unhealthy and no fallback
    exists.
    """


class LocalOnlyRouteFailure(RouterError):
    """A ``local-only`` request found no local candidate.

    The router refuses to silently fall back to cloud in this case. The
    user-facing failure is the *point* of ``local-only`` — it makes data
    boundaries explicit rather than papering over them.
    """


class PolicyError(RouterError):
    """A routing policy file is malformed or contradictory."""
