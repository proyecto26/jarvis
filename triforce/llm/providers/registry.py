"""Provider registry — name -> Provider instance (lazy)."""

from __future__ import annotations

import logging
from typing import Optional

from triforce.llm.providers.base import Provider

logger = logging.getLogger(__name__)

_PROVIDERS: dict[str, Provider] = {}
_INITIALIZED = False


def register_provider(provider: Provider) -> None:
    """Register a provider instance."""
    if not provider.name:
        raise ValueError(f"Provider {type(provider).__name__} has no `name`")
    _PROVIDERS[provider.name] = provider
    logger.debug("Registered provider: %s", provider.name)


def _initialize_default_providers() -> None:
    """Register the built-in providers. Idempotent.

    Each provider is constructed lazily (no heavy imports at import-time).
    """
    global _INITIALIZED
    if _INITIALIZED:
        return

    try:
        from triforce.llm.providers.gemini import GeminiProvider

        register_provider(GeminiProvider())
    except Exception as exc:
        logger.debug("Gemini provider unavailable: %s", exc)

    try:
        from triforce.llm.providers.ollama import OllamaProvider

        register_provider(OllamaProvider())
    except Exception as exc:
        logger.debug("Ollama provider unavailable: %s", exc)

    _INITIALIZED = True


def get_provider(name: str) -> Optional[Provider]:
    """Return the registered provider by name, or None if not available."""
    _initialize_default_providers()
    return _PROVIDERS.get(name)


def all_providers() -> dict[str, Provider]:
    """Return all registered providers."""
    _initialize_default_providers()
    return dict(_PROVIDERS)
