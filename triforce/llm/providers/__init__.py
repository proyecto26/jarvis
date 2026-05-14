"""Provider adapters for the LLM router.

Each provider implements the same minimal interface (generate, health,
capabilities). Importing this module loads the registry of providers but does
NOT load any heavy dependencies (those are lazy-imported inside each provider).
"""

from triforce.llm.providers.base import Provider, ProviderResponse
from triforce.llm.providers.registry import (
    all_providers,
    get_provider,
    register_provider,
)

__all__ = [
    "Provider",
    "ProviderResponse",
    "all_providers",
    "get_provider",
    "register_provider",
]
