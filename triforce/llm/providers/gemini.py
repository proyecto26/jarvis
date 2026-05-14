"""Gemini provider — wraps google-genai for the router.

This is the cloud fallback. It is intentionally minimal: the router uses it
only when the policy permits cloud and no healthy local candidate exists.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from triforce.llm.providers.base import Provider, ProviderResponse

logger = logging.getLogger(__name__)


class GeminiProvider(Provider):
    """Google Gemini cloud provider."""

    name = "gemini"

    def __init__(self) -> None:
        self._client = None
        self._last_health_check: float = 0.0
        self._last_health_result: bool = False

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from google import genai  # google-genai package
        except ImportError as exc:
            raise RuntimeError(
                "google-genai is required for the Gemini provider. "
                "Install with: pip install google-genai"
            ) from exc
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set")
        self._client = genai.Client(api_key=api_key)
        return self._client

    def health(self, timeout_ms: int = 200) -> bool:
        """Cheap health probe — checks for API key + 30s cached result.

        We do not make a real network call here because that would defeat the
        purpose of a 200ms timeout. The router degrades gracefully if a real
        call later fails.
        """
        now = time.time()
        if now - self._last_health_check < 30:
            return self._last_health_result
        self._last_health_check = now
        # Presence of API key is the cheap proxy
        self._last_health_result = bool(os.getenv("GOOGLE_API_KEY"))
        return self._last_health_result

    def generate(
        self,
        model_base_id: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ProviderResponse:
        client = self._get_client()
        params = params or {}

        # Convert ChatML messages to Gemini contents format
        contents = []
        system_instruction = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_instruction += content + "\n"
                continue
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": content}]})

        config: dict[str, Any] = {}
        if system_instruction:
            config["system_instruction"] = system_instruction.strip()
        if tools:
            config["tools"] = tools
        # Router owns retries — disable SDK-level retries
        config["automatic_function_calling"] = {"disable": True}

        response = client.models.generate_content(
            model=model_base_id,
            contents=contents,
            config=config,
        )

        text = getattr(response, "text", "") or ""
        function_calls: list[dict] = []
        for cand in getattr(response, "candidates", []) or []:
            for part in getattr(getattr(cand, "content", None), "parts", []) or []:
                fc = getattr(part, "function_call", None)
                if fc is not None:
                    function_calls.append(
                        {
                            "name": getattr(fc, "name", ""),
                            "args": dict(getattr(fc, "args", {}) or {}),
                        }
                    )

        return ProviderResponse(
            text=text,
            function_calls=tuple(function_calls),
            raw={},
            provider=self.name,
            model_id=model_base_id,
        )
