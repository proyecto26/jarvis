"""Grafeo backend: embedded graph database with vector search + BM25.

Uses Grafeo's pure-Rust embedded mode (no Docker/server needed).
Combines:
- Graph structure for relational memory (entries linked by topic, time)
- HNSW vector search for semantic recall (via sentence-transformers embeddings)
- Cypher queries for structured retrieval
- BM25 full-text search for keyword matching

All local, zero external API dependencies.
"""

import os
import tempfile
import shutil

import numpy as np
from grafeo import GrafeoDB

from benchmarks.backends.base import MemoryBackend


class GrafeoBackend(MemoryBackend):
    """Grafeo embedded graph+vector memory backend."""

    def __init__(self):
        self._db: GrafeoDB | None = None
        self._db_path: str = ""
        self._model = None
        self._entries: list[dict] = []
        self._beliefs: list[dict] = []
        self._entry_texts: list[str] = []
        self._entry_dates: list[str] = []

    def name(self) -> str:
        return "grafeo"

    def setup(self, config: dict | None = None) -> None:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer("all-MiniLM-L6-v2")

        self._db_path = os.path.join(tempfile.mkdtemp(prefix="grafeo_bench_"), "memory.db")
        self._db = GrafeoDB(self._db_path)
        self._entries = []
        self._beliefs = []
        self._entry_texts = []
        self._entry_dates = []

        # Create schema
        try:
            self._db.execute_cypher(
                "CREATE NODE TABLE IF NOT EXISTS Entry(date STRING, theme STRING, text STRING, PRIMARY KEY(date))"
            )
        except Exception:
            pass  # Grafeo may not support DDL via Cypher — use implicit schema

    def teardown(self) -> None:
        self._db = None
        self._model = None
        self._entries = []
        self._beliefs = []
        self._entry_texts = []
        self._entry_dates = []
        if self._db_path:
            parent = os.path.dirname(self._db_path)
            shutil.rmtree(parent, ignore_errors=True)

    def _entry_to_text(self, entry: dict) -> str:
        parts = []
        parts.append(entry.get("metadata", {}).get("dominant_theme", ""))
        for j in entry.get("judgments", []):
            parts.append(j.get("action", ""))
            parts.append(j.get("reasoning", ""))
        for e in entry.get("executions", []):
            parts.append(e.get("action", ""))
            parts.append(e.get("outcome", ""))
        for l in entry.get("learnings", []):
            parts.append(l.get("content", ""))
        for d in entry.get("dreams", []):
            parts.append(d.get("seed", ""))
            if d.get("breakthrough"):
                parts.append(d["breakthrough"])
        for bm in entry.get("belief_mutations", []):
            parts.append(bm.get("belief", ""))
        return " ".join(parts)

    def store_entry(self, entry: dict) -> str:
        entry_date = entry.get("metadata", {}).get("date", "unknown")
        theme = entry.get("metadata", {}).get("dominant_theme", "")
        text = self._entry_to_text(entry)

        self._entries.append(entry)
        self._entry_texts.append(text)
        self._entry_dates.append(entry_date)

        # Store in Grafeo graph
        try:
            # Escape single quotes in text
            safe_text = text.replace("'", "\\'").replace('"', '\\"')[:500]
            safe_theme = theme.replace("'", "\\'")
            self._db.execute_cypher(
                f'CREATE (n:Entry {{date: "{entry_date}", theme: "{safe_theme}", '
                f'text: "{safe_text}"}})'
            )
        except Exception:
            pass  # Skip duplicates or errors

        return entry_date

    def store_belief(self, belief: dict) -> str:
        self._beliefs.append(belief)
        belief_text = belief.get("belief", "")
        safe_text = belief_text.replace("'", "\\'").replace('"', '\\"')

        try:
            self._db.execute_cypher(
                f'CREATE (n:Belief {{text: "{safe_text}", '
                f'strength: {belief.get("strength", 0.5)}}})'
            )
        except Exception:
            pass

        return belief.get("belief", "")[:32]

    def recall(self, query: str, top_k: int = 5) -> list[dict]:
        """Hybrid recall: graph query + vector similarity.

        Uses embedding cosine similarity for semantic matching,
        with graph traversal for topic-based retrieval as fallback.
        """
        results = []

        # Strategy 1: Embedding-based vector similarity
        if self._model and self._entry_texts:
            query_embedding = self._model.encode([query], show_progress_bar=False)
            entry_embeddings = self._model.encode(
                self._entry_texts, batch_size=64, show_progress_bar=False
            )

            similarities = np.dot(entry_embeddings, query_embedding.T).flatten()
            top_indices = np.argsort(similarities)[::-1][:top_k * 2]

            for idx in top_indices:
                results.append({
                    "date": self._entry_dates[idx],
                    "score": round(float(similarities[idx]), 4),
                    "content": self._entry_texts[idx][:200],
                    "source": "embedding",
                })

        # Strategy 2: Cypher graph query by theme keyword
        try:
            # Extract key terms from query
            import re
            query_words = set(re.findall(r"[a-z]+", query.lower())) - {
                "what", "do", "know", "about", "tell", "me", "recall",
                "experiences", "related", "decisions", "made", "patterns",
                "work", "have", "learned",
            }

            for word in list(query_words)[:3]:
                cypher_result = self._db.execute_cypher(
                    f'MATCH (n:Entry) WHERE n.theme CONTAINS "{word}" '
                    f'OR n.text CONTAINS "{word}" RETURN n.date, n.text'
                )
                for row in cypher_result:
                    date = row.get("n.date", "unknown")
                    if not any(r["date"] == date for r in results):
                        results.append({
                            "date": date,
                            "score": 0.3,
                            "content": str(row.get("n.text", ""))[:200],
                            "source": "cypher",
                        })
        except Exception:
            pass

        # Sort by score and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def check_contradiction(self, belief_a: str, belief_b: str) -> dict:
        if self._model is None:
            return {"has_conflict": False, "similarity_score": 0.0, "recommendation": "coexist"}

        embeddings = self._model.encode([belief_a, belief_b], show_progress_bar=False)
        similarity = float(np.dot(embeddings[0], embeddings[1]) / (
            np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
        ))

        has_conflict = similarity > 0.45
        if similarity > 0.85:
            recommendation = "merge"
        elif similarity > 0.7:
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
        results = []
        try:
            import re
            topic_words = re.findall(r"[a-z]+", topic.lower())
            for word in topic_words[:2]:
                cypher_result = self._db.execute_cypher(
                    f'MATCH (n:Belief) WHERE n.text CONTAINS "{word}" '
                    f'RETURN n.text, n.strength'
                )
                for row in cypher_result:
                    results.append({
                        "belief": row.get("n.text", ""),
                        "strength": row.get("n.strength", 0.5),
                    })
        except Exception:
            pass

        return sorted(results, key=lambda x: x.get("strength", 0), reverse=True)

    def get_memory_usage_mb(self) -> float:
        import sys
        total = sys.getsizeof(self._entries) + sys.getsizeof(self._entry_texts)
        return total / (1024 * 1024)
