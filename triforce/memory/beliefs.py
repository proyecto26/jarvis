"""Judge beliefs persistence — read/write judge_beliefs.json."""

import json
from datetime import datetime

from triforce.config import Config


def load_beliefs() -> list[dict]:
    """Load beliefs from judge_beliefs.json."""
    try:
        data = json.loads(Config.BELIEFS_PATH.read_text())
        return data.get("beliefs", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_beliefs(beliefs: list[dict]):
    """Save beliefs to judge_beliefs.json."""
    Config.BELIEFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {"beliefs": beliefs}
    Config.BELIEFS_PATH.write_text(json.dumps(data, indent=2))


def add_belief(belief: str, strength: float = 0.5, reason: str = "") -> dict:
    """Add a new belief with strength score and timestamp."""
    beliefs = load_beliefs()
    entry = {
        "belief": belief,
        "strength": strength,
        "reason": reason,
        "created": datetime.utcnow().isoformat(),
        "updated": datetime.utcnow().isoformat(),
    }
    beliefs.append(entry)
    save_beliefs(beliefs)
    return entry


def update_belief(
    belief: str, strength: float | None = None, reason: str | None = None
) -> dict | None:
    """Update an existing belief by text match. Returns updated belief or None."""
    beliefs = load_beliefs()
    for b in beliefs:
        if b["belief"] == belief:
            if strength is not None:
                b["strength"] = strength
            if reason is not None:
                b["reason"] = reason
            b["updated"] = datetime.utcnow().isoformat()
            save_beliefs(beliefs)
            return b
    return None


def remove_belief(belief: str) -> bool:
    """Remove a belief by text match. Returns True if removed."""
    beliefs = load_beliefs()
    original_len = len(beliefs)
    beliefs = [b for b in beliefs if b["belief"] != belief]
    if len(beliefs) < original_len:
        save_beliefs(beliefs)
        return True
    return False
