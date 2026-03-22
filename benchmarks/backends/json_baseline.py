"""Baseline backend: current JSON-based memory system (beliefs.py + journal.py).

Uses exact string matching and SequenceMatcher for similarity — no semantic
understanding. This establishes the floor for recall quality metrics.
"""

import json
import os
import tempfile
from difflib import SequenceMatcher
from pathlib import Path

from benchmarks.backends.base import MemoryBackend


class JsonBaselineBackend(MemoryBackend):
    """Current Jarvis memory: flat JSON files + string matching."""

    def __init__(self):
        self._entries: list[dict] = []
        self._beliefs: list[dict] = []
        self._data_dir: Path | None = None

    def name(self) -> str:
        return "json-baseline"

    def setup(self, config: dict | None = None) -> None:
        self._data_dir = Path(tempfile.mkdtemp(prefix="jarvis_bench_json_"))
        self._entries = []
        self._beliefs = []

    def teardown(self) -> None:
        self._entries = []
        self._beliefs = []
        if self._data_dir and self._data_dir.exists():
            import shutil
            shutil.rmtree(self._data_dir, ignore_errors=True)

    def store_entry(self, entry: dict) -> str:
        entry_date = entry.get("metadata", {}).get("date", "unknown")
        self._entries.append(entry)
        # Also write to disk (mimic journal.py behavior)
        path = self._data_dir / f"{entry_date}.json"
        path.write_text(json.dumps(entry, indent=2))
        return entry_date

    def store_belief(self, belief: dict) -> str:
        self._beliefs.append(belief)
        # Persist to disk
        beliefs_path = self._data_dir / "judge_beliefs.json"
        beliefs_path.write_text(json.dumps({"beliefs": self._beliefs}, indent=2))
        return belief.get("belief", "")[:32]

    def recall(self, query: str, top_k: int = 5) -> list[dict]:
        """String-matching recall — searches all entry text for query terms."""
        query_lower = query.lower()
        query_words = set(query_lower.split())
        scored = []

        for entry in self._entries:
            # Flatten entry text
            text_parts = []
            text_parts.append(entry.get("metadata", {}).get("dominant_theme", ""))
            for j in entry.get("judgments", []):
                text_parts.append(j.get("action", ""))
                text_parts.append(j.get("reasoning", ""))
            for e in entry.get("executions", []):
                text_parts.append(e.get("action", ""))
                text_parts.append(e.get("outcome", ""))
            for l in entry.get("learnings", []):
                text_parts.append(l.get("content", ""))
            for d in entry.get("dreams", []):
                text_parts.append(d.get("seed", ""))
                if d.get("breakthrough"):
                    text_parts.append(d["breakthrough"])

            full_text = " ".join(text_parts).lower()

            # Score by word overlap ratio
            if not full_text:
                continue
            matched_words = sum(1 for w in query_words if w in full_text)
            word_score = matched_words / max(len(query_words), 1)

            # Also check SequenceMatcher for fuzzy match
            seq_score = SequenceMatcher(None, query_lower, full_text[:500]).ratio()

            score = max(word_score, seq_score)
            if score > 0.05:
                scored.append({
                    "date": entry.get("metadata", {}).get("date", "unknown"),
                    "score": round(score, 4),
                    "content": full_text[:200],
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def check_contradiction(self, belief_a: str, belief_b: str) -> dict:
        """String similarity-based contradiction check (mirrors SSGM)."""
        similarity = SequenceMatcher(
            None, belief_a.lower().strip(), belief_b.lower().strip()
        ).ratio()

        has_conflict = similarity > 0.7
        if similarity > 0.9:
            recommendation = "merge"
        elif similarity > 0.8:
            recommendation = "supersede"
        elif has_conflict:
            recommendation = "review"
        else:
            recommendation = "coexist"

        return {
            "has_conflict": has_conflict,
            "similarity_score": round(similarity, 4),
            "recommendation": recommendation,
        }

    def query_beliefs_at(self, topic: str, at_date: str | None = None) -> list[dict]:
        """Filter beliefs by text match on topic."""
        topic_lower = topic.lower()
        results = []
        for b in self._beliefs:
            belief_text = b.get("belief", "").lower()
            if topic_lower in belief_text:
                results.append(b)
        return sorted(results, key=lambda x: x.get("strength", 0), reverse=True)

    def get_memory_usage_mb(self) -> float:
        """Estimate memory from data size."""
        import sys
        total = sys.getsizeof(self._entries) + sys.getsizeof(self._beliefs)
        for e in self._entries:
            total += sys.getsizeof(json.dumps(e))
        for b in self._beliefs:
            total += sys.getsizeof(json.dumps(b))
        return total / (1024 * 1024)
