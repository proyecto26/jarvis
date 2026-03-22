"""Unified backend: PageIndex BM25/tree + Grafeo graph + sentence-transformer embeddings.

The best of all worlds:
- BM25 for sub-millisecond keyword matching (from pageindex-local)
- Grafeo graph for relational queries (topic/theme traversal)
- Sentence-transformer embeddings for semantic recall (synonym/paraphrase handling)
- 3-way RRF fusion for ranking
- TF-IDF cosine for contradiction detection (fast, accurate)

All local. Zero external APIs.
"""

import math
import os
import shutil
import tempfile

import numpy as np
from collections import defaultdict

from benchmarks.backends.base import MemoryBackend
from benchmarks.backends.pageindex_local import BM25, TfIdf, tokenize


class UnifiedBackend(MemoryBackend):
    """Unified graph+vector+BM25 memory backend."""

    def __init__(self):
        self._entries: list[dict] = []
        self._beliefs: list[dict] = []
        # BM25 components
        self._documents: list[list[str]] = []
        self._entry_map: list[str] = []
        self._bm25 = BM25()
        self._tfidf = TfIdf()
        # Embedding components
        self._model = None
        self._entry_texts: list[str] = []
        self._entry_embeddings: np.ndarray | None = None
        # Graph component
        self._db = None
        self._db_path: str = ""
        # State
        self._index_dirty: bool = True

    def name(self) -> str:
        return "unified"

    def setup(self, config: dict | None = None) -> None:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer("all-MiniLM-L6-v2")

        from grafeo import GrafeoDB
        self._db_path = os.path.join(tempfile.mkdtemp(prefix="unified_bench_"), "memory.db")
        self._db = GrafeoDB(self._db_path)

        self._entries = []
        self._beliefs = []
        self._documents = []
        self._entry_map = []
        self._entry_texts = []
        self._entry_embeddings = None
        self._index_dirty = True

    def teardown(self) -> None:
        self._db = None
        self._model = None
        self._entries = []
        self._beliefs = []
        self._documents = []
        self._entry_texts = []
        self._entry_embeddings = None
        if self._db_path:
            shutil.rmtree(os.path.dirname(self._db_path), ignore_errors=True)

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
        self._entry_map.append(entry_date)

        # BM25 tokens + bigrams
        tokens = tokenize(text)
        bigrams = [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
        self._documents.append(tokens + bigrams)

        # Grafeo graph node
        try:
            safe_theme = theme.replace('"', '\\"')
            self._db.execute_cypher(
                f'CREATE (n:Entry {{date: "{entry_date}", theme: "{safe_theme}"}})'
            )
        except Exception:
            pass

        self._index_dirty = True
        return entry_date

    def store_belief(self, belief: dict) -> str:
        self._beliefs.append(belief)
        self._index_dirty = True
        return belief.get("belief", "")[:32]

    def _rebuild_index(self) -> None:
        if not self._index_dirty:
            return

        # BM25 index
        if self._documents:
            self._bm25.fit(self._documents)
            self._tfidf.fit(self._documents)

        # Embedding index (batch encode all entries)
        if self._entry_texts and self._model:
            self._entry_embeddings = self._model.encode(
                self._entry_texts, batch_size=64, show_progress_bar=False,
                normalize_embeddings=True,
            )

        self._index_dirty = False

    def recall(self, query: str, top_k: int = 5) -> list[dict]:
        """3-way RRF: BM25 + graph theme + embeddings."""
        self._rebuild_index()

        query_tokens = tokenize(query)
        RRF_K = 60

        # System 1: BM25 keyword ranking
        bm25_by_date: dict[str, int] = {}
        if query_tokens:
            bm25_ranked = self._bm25.rank(query_tokens, top_k=top_k * 3)
            for rank, (doc_idx, _) in enumerate(bm25_ranked):
                date = self._entry_map[doc_idx]
                if date not in bm25_by_date:
                    bm25_by_date[date] = rank

        # System 2: Grafeo graph theme traversal
        graph_by_date: dict[str, int] = {}
        try:
            import re
            keywords = set(re.findall(r"[a-z]+", query.lower())) - {
                "what", "do", "know", "about", "tell", "me", "recall",
                "experiences", "related", "decisions", "made", "patterns",
                "work", "have", "learned",
            }
            for word in list(keywords)[:3]:
                result = self._db.execute_cypher(
                    f'MATCH (n:Entry) WHERE n.theme CONTAINS "{word}" RETURN n.date'
                )
                for rank_offset, row in enumerate(result):
                    date = row.get("n.date", "unknown")
                    if date not in graph_by_date:
                        graph_by_date[date] = len(graph_by_date)
        except Exception:
            pass

        # System 3: Embedding cosine similarity
        embed_by_date: dict[str, int] = {}
        if self._model and self._entry_embeddings is not None:
            query_embedding = self._model.encode(
                [query], show_progress_bar=False, normalize_embeddings=True
            )
            similarities = (self._entry_embeddings @ query_embedding.T).flatten()
            top_indices = np.argsort(similarities)[::-1][:top_k * 3]

            for rank, idx in enumerate(top_indices):
                date = self._entry_map[idx]
                if date not in embed_by_date:
                    embed_by_date[date] = rank

        # Weighted 3-way RRF: embeddings get 2x weight (best for semantic)
        all_dates = set(bm25_by_date.keys()) | set(graph_by_date.keys()) | set(embed_by_date.keys())
        rrf_scores: dict[str, float] = {}

        W_BM25 = 1.0    # keyword matching
        W_GRAPH = 0.3   # theme traversal (coarse, demoted)
        W_EMBED = 3.0   # semantic similarity (primary signal)

        for date in all_dates:
            score = 0.0
            if date in bm25_by_date:
                score += W_BM25 / (RRF_K + bm25_by_date[date])
            if date in graph_by_date:
                score += W_GRAPH / (RRF_K + graph_by_date[date])
            if date in embed_by_date:
                score += W_EMBED / (RRF_K + embed_by_date[date])
            rrf_scores[date] = score

        sorted_dates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        results = []
        for date, score in sorted_dates[:top_k]:
            max_possible = (W_BM25 + W_GRAPH + W_EMBED) / RRF_K
            normalized = score / max_possible
            results.append({
                "date": date,
                "score": round(min(normalized, 1.0), 4),
                "content": "",
                "source": "rrf-unified",
            })

        return results

    def check_contradiction(self, belief_a: str, belief_b: str) -> dict:
        """TF-IDF cosine for fast, accurate contradiction detection."""
        tokens_a = tokenize(belief_a)
        tokens_b = tokenize(belief_b)

        if self._tfidf.corpus_size == 0:
            self._tfidf.fit([tokens_a, tokens_b])

        vec_a = self._tfidf.vectorize(tokens_a)
        vec_b = self._tfidf.vectorize(tokens_b)
        similarity = TfIdf.cosine_similarity(vec_a, vec_b)

        has_conflict = similarity > 0.6
        if similarity > 0.85:
            recommendation = "merge"
        elif similarity > 0.75:
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
        topic_lower = topic.lower()
        return [
            b for b in self._beliefs
            if topic_lower in b.get("belief", "").lower()
        ]

    def get_memory_usage_mb(self) -> float:
        import sys
        total = sys.getsizeof(self._entries) + sys.getsizeof(self._documents)
        if self._entry_embeddings is not None:
            total += self._entry_embeddings.nbytes
        return total / (1024 * 1024)
