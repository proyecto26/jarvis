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

    # --- Temporal durability layer ---
    TEMPORAL_ADDRESS: str = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    TEMPORAL_NAMESPACE: str = os.getenv("TEMPORAL_NAMESPACE", "default")
    TEMPORAL_TASK_QUEUE: str = os.getenv("TEMPORAL_TASK_QUEUE", "jarvis-trinity")
    DREAM_INTERVAL_HOURS: int = int(os.getenv("DREAM_INTERVAL_HOURS", "6"))
    CONSOLIDATION_HOUR_UTC: int = int(os.getenv("CONSOLIDATION_HOUR_UTC", "3"))

    # --- Memory backend selection ---
    # Embedding backend used by triforce/memory/episodic.py.
    # Options: "sentence-transformers" (default — local, MiniLM-L6-v2),
    #          "ollama" (local nomic-embed-text via Ollama),
    #          "gemini" (cloud fallback).
    EMBEDDING_BACKEND: str = os.getenv("EMBEDDING_BACKEND", "sentence-transformers")
    EPISODIC_DB_PATH: Path = Path(
        os.getenv("EPISODIC_DB_PATH", str(PROJECT_ROOT / "memory" / "episodic.db"))
    )
