"""Routing policy loader.

Loads YAML policy files into typed objects. Validates that referenced
capabilities exist and that the fallback chain is well-formed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from triforce.llm.errors import PolicyError
from triforce.llm.types import PrivacyClass

POLICIES_DIR = Path(__file__).parent

OnNoCandidate = Literal["error", "escalate", "use_default_gemini"]


@dataclass(frozen=True)
class FallbackStep:
    capability_match: frozenset[str] = field(default_factory=frozenset)
    privacy_class: Optional[PrivacyClass] = None
    prefer_local: bool = False
    max_latency_ms: Optional[int] = None


@dataclass(frozen=True)
class Policy:
    agent: str
    default_privacy_class: PrivacyClass = "cloud-ok"
    max_latency_ms: int = 5_000
    prefer: frozenset[str] = field(default_factory=frozenset)
    prefer_tags: frozenset[str] = field(default_factory=frozenset)
    must_have: frozenset[str] = field(default_factory=frozenset)
    fallback_chain: tuple[FallbackStep, ...] = field(default_factory=tuple)
    on_no_candidate: OnNoCandidate = "error"


_CACHE: dict[str, Policy] = {}


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:
        raise PolicyError(
            "pyyaml is required to load routing policies. "
            "Install with: pip install pyyaml"
        ) from exc
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _parse_step(raw: dict) -> FallbackStep:
    return FallbackStep(
        capability_match=frozenset(raw.get("capability_match", [])),
        privacy_class=raw.get("privacy_class"),
        prefer_local=bool(raw.get("prefer_local", False)),
        max_latency_ms=raw.get("max_latency_ms"),
    )


def load_policy(agent: str) -> Optional[Policy]:
    """Load (and cache) the policy for an agent.

    Returns None if no policy file exists — callers should fall back to a
    generic default.
    """
    if agent in _CACHE:
        return _CACHE[agent]

    path = POLICIES_DIR / f"{agent}.yaml"
    if not path.exists():
        return None

    raw = _load_yaml(path)
    if not raw:
        raise PolicyError(f"Empty policy file: {path}")

    if raw.get("agent") != agent:
        raise PolicyError(
            f"Policy file {path.name} declares agent={raw.get('agent')!r} but "
            f"was loaded for {agent!r}"
        )

    on_nc = raw.get("on_no_candidate", "error")
    if on_nc not in ("error", "escalate", "use_default_gemini"):
        raise PolicyError(
            f"{path}: on_no_candidate must be one of "
            f"'error' | 'escalate' | 'use_default_gemini', got {on_nc!r}"
        )

    policy = Policy(
        agent=agent,
        default_privacy_class=raw.get("default_privacy_class", "cloud-ok"),
        max_latency_ms=int(raw.get("max_latency_ms", 5_000)),
        prefer=frozenset(raw.get("prefer", [])),
        prefer_tags=frozenset(raw.get("prefer_tags", [])),
        must_have=frozenset(raw.get("must_have", [])),
        fallback_chain=tuple(_parse_step(s) for s in raw.get("fallback_chain", [])),
        on_no_candidate=on_nc,
    )
    _CACHE[agent] = policy
    return policy
