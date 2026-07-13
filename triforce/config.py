"""Environment-based configuration for the Trinity agents.

Loaded once at import time. Per-component sub-modules (e.g. the Temporal
worker) re-read these values from os.getenv so they pick up runtime overrides.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent


class Config:
    """Central configuration — model, path, Temporal, and memory settings."""

    # --- Trinity model selection (LLM router will replace these) ---
    DREAMER_MODEL: str = os.getenv("DREAMER_MODEL", "gemini-2.0-pro-exp")
    JUDGE_MODEL: str = os.getenv("JUDGE_MODEL", "gemini-1.5-pro")
    EXECUTOR_MODEL: str = os.getenv("EXECUTOR_MODEL", "gemini-2.0-flash")
    ROOT_MODEL: str = os.getenv("ROOT_MODEL", "gemini-2.0-flash")

    # --- Paths ---
    JOURNAL_DIR: Path = PROJECT_ROOT / "journal"
    BELIEFS_PATH: Path = PROJECT_ROOT / "memory" / "judge_beliefs.json"
    KNOWLEDGE_DIR: Path = PROJECT_ROOT / "knowledge"

    # --- Temporal durability layer ---
    TEMPORAL_ADDRESS: str = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    TEMPORAL_NAMESPACE: str = os.getenv("TEMPORAL_NAMESPACE", "default")
    TEMPORAL_TASK_QUEUE: str = os.getenv("TEMPORAL_TASK_QUEUE", "jarvis-trinity")
    DREAM_INTERVAL_HOURS: int = int(os.getenv("DREAM_INTERVAL_HOURS", "6"))
    CONSOLIDATION_HOUR_UTC: int = int(os.getenv("CONSOLIDATION_HOUR_UTC", "3"))
    # Accumulated judgment importance (sum of action_weights) that triggers a
    # reflection pass ahead of the nightly schedule (Stanford generative-agents
    # pattern).
    REFLECTION_IMPORTANCE_THRESHOLD: int = int(
        os.getenv("REFLECTION_IMPORTANCE_THRESHOLD", "15")
    )

    # --- Memory backend selection ---
    # Embedding backend used by triforce/memory/episodic.py.
    # Options: "sentence-transformers" (default — local, MiniLM-L6-v2),
    #          "ollama" (local nomic-embed-text via Ollama),
    #          "gemini" (cloud fallback).
    EMBEDDING_BACKEND: str = os.getenv("EMBEDDING_BACKEND", "sentence-transformers")
    EPISODIC_DB_PATH: Path = Path(
        os.getenv("EPISODIC_DB_PATH", str(PROJECT_ROOT / "memory" / "episodic.db"))
    )

    # --- LLM Router ---
    # When "off", agents resolve model strings from the legacy DREAMER_MODEL /
    # JUDGE_MODEL / EXECUTOR_MODEL env vars (byte-identical to pre-router
    # behavior). Any other value enables the router.
    DANTE_ROUTER: str = os.getenv("DANTE_ROUTER", "off")

    @classmethod
    def router_enabled(cls) -> bool:
        return cls.DANTE_ROUTER.lower() not in ("off", "0", "false", "no", "")

    @classmethod
    def model_for(cls, agent: str, fallback: str) -> str:
        """Resolve the model string for an agent, honoring the router toggle.

        When ``DANTE_ROUTER=off`` (default), returns ``fallback``. Otherwise
        calls the router and returns ``RouteDecision.model.base_id``. The
        fallback is also returned if the router fails for any reason — agents
        must remain runnable.
        """
        if not cls.router_enabled():
            return fallback
        try:
            from triforce.llm.router import get_router
            from triforce.llm import RouteRequest

            decision = get_router().route(RouteRequest(agent=agent))
            return decision.model.base_id
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "Router failed for agent=%s, using fallback %s: %s",
                agent,
                fallback,
                exc,
            )
            return fallback
