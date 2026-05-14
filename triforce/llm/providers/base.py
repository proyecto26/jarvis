"""Provider ABC + uniform response type."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderResponse:
    """Uniform response across providers.

    Each provider's `generate()` returns one of these. The router exposes this
    as the surface the agents see — they don't need to know which provider
    produced it.
    """

    text: str = ""
    function_calls: tuple[dict, ...] = field(default_factory=tuple)
    raw: dict = field(default_factory=dict)
    provider: str = ""
    model_id: str = ""


class Provider(ABC):
    """Base class for all router providers."""

    #: Stable identifier used by the registry (e.g. ``"gemini"``, ``"ollama"``).
    name: str = ""

    @abstractmethod
    def generate(
        self,
        model_base_id: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ProviderResponse:
        """Run a single completion against a specific base model.

        Args:
            model_base_id: Provider-specific model identifier.
            messages: ChatML-style list ``[{role, content}, ...]``.
            tools: Optional tool/function declarations.
            params: Provider-specific knobs (temperature, top_p, ...).
        """

    @abstractmethod
    def health(self, timeout_ms: int = 200) -> bool:
        """Lightweight probe — return True if the provider is responsive."""

    def capabilities(self) -> set[str]:
        """Optional capability hints (rarely used; models declare their own)."""
        return set()
