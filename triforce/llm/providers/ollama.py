"""Ollama provider — serves Nemotron and Gemma 4 locally.

Uses Ollama's HTTP API (default http://localhost:11434). The health probe is
a lightweight HEAD request to `/api/tags`; if the daemon isn't running the
router demotes this provider in the candidate ranking.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from triforce.llm.providers.base import Provider, ProviderResponse

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


class OllamaProvider(Provider):
    """Local Ollama provider (Nemotron + Gemma 4 + any pulled model)."""

    name = "ollama"

    def __init__(self, host: str | None = None) -> None:
        self._host = host or DEFAULT_OLLAMA_HOST
        self._last_health_check: float = 0.0
        self._last_health_result: bool = False

    def health(self, timeout_ms: int = 200) -> bool:
        """Probe `/api/tags` — fast, no model load required."""
        now = time.time()
        # Cache health for 30s to avoid hammering the daemon
        if now - self._last_health_check < 30:
            return self._last_health_result
        self._last_health_check = now

        try:
            import httpx
        except ImportError:
            # httpx is a transitive dep of google-adk so this should always succeed
            self._last_health_result = False
            return False

        try:
            r = httpx.get(
                f"{self._host}/api/tags",
                timeout=timeout_ms / 1000.0,
            )
            self._last_health_result = r.status_code == 200
        except Exception as exc:
            logger.debug("Ollama health check failed: %s", exc)
            self._last_health_result = False
        return self._last_health_result

    def generate(
        self,
        model_base_id: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ProviderResponse:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("httpx is required for the Ollama provider") from exc

        params = params or {}
        body = {
            "model": model_base_id,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": params.get("temperature", 0.7),
                "top_p": params.get("top_p", 0.95),
            },
        }
        if tools:
            body["tools"] = tools

        r = httpx.post(
            f"{self._host}/api/chat",
            json=body,
            timeout=params.get("timeout_seconds", 60),
        )
        r.raise_for_status()
        data = r.json()

        message = data.get("message", {}) or {}
        text = message.get("content", "") or ""

        function_calls: list[dict] = []
        for tc in message.get("tool_calls", []) or []:
            function_calls.append(
                {
                    "name": tc.get("function", {}).get("name", ""),
                    "args": tc.get("function", {}).get("arguments", {}),
                }
            )

        return ProviderResponse(
            text=text,
            function_calls=tuple(function_calls),
            raw={"ollama_done_reason": data.get("done_reason", "")},
            provider=self.name,
            model_id=model_base_id,
        )
