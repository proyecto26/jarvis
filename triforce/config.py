"""Environment-based model configuration for the Trinity agents."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent


class Config:
    """Central configuration — all model and path settings."""

    DREAMER_MODEL: str = os.getenv("DREAMER_MODEL", "gemini-2.0-pro-exp")
    JUDGE_MODEL: str = os.getenv("JUDGE_MODEL", "gemini-1.5-pro")
    EXECUTOR_MODEL: str = os.getenv("EXECUTOR_MODEL", "gemini-2.0-flash")
    ROOT_MODEL: str = os.getenv("ROOT_MODEL", "gemini-2.0-flash")

    JOURNAL_DIR: Path = PROJECT_ROOT / "journal"
    BELIEFS_PATH: Path = PROJECT_ROOT / "memory" / "judge_beliefs.json"
