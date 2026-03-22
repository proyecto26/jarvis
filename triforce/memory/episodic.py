"""Episodic memory — hybrid BM25 + embeddings + Grafeo graph retrieval.

Local-first implementation using:
- BM25 (Okapi BM25) for fast keyword matching
- sentence-transformers (all-MiniLM-L6-v2) for semantic similarity
- Grafeo embedded graph for relational topic/theme queries
- Weighted Reciprocal Rank Fusion (RRF) for combining rankings
- TF-IDF cosine similarity for conflict detection

All components run locally — zero external API dependencies.
Degrades gracefully if optional dependencies aren't installed.
"""

from __future__ import annotations

import logging
import math
import os
import re
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from triforce.memory.schema import JournalEntry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BM25 retrieval engine
# ---------------------------------------------------------------------------

class _BM25:
    """Okapi BM25 ranking function."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avgdl = 0.0
        self.doc_freqs: dict[str, int] = defaultdict(int)
        self.doc_lens: list[int] = []
        self.doc_term_freqs: list[dict[str, int]] = []
        self.idf_cache: dict[str, float] = {}

    def fit(self, documents: list[list[str]]) -> None:
        self.corpus_size = len(documents)
        self.doc_lens = []
        self.doc_term_freqs = []
        self.doc_freqs = defaultdict(int)

        for doc in documents:
            self.doc_lens.append(len(doc))
            term_freqs = Counter(doc)
            self.doc_term_freqs.append(term_freqs)
            for term in set(doc):
                self.doc_freqs[term] += 1

        self.avgdl = sum(self.doc_lens) / max(self.corpus_size, 1)
        self.idf_cache = {}
        for term, df in self.doc_freqs.items():
            self.idf_cache[term] = math.log(
                (self.corpus_size - df + 0.5) / (df + 0.5) + 1.0
            )

    def rank(self, query_tokens: list[str], top_k: int = 5) -> list[tuple[int, float]]:
        scores = []
        for i in range(self.corpus_size):
            score = 0.0
            doc_len = self.doc_lens[i]
            tfs = self.doc_term_freqs[i]
            for qt in query_tokens:
                idf = self.idf_cache.get(qt)
                if idf is None:
                    continue
                tf = tfs.get(qt, 0)
                num = tf * (self.k1 + 1)
                den = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self.avgdl, 1))
                score += idf * num / max(den, 1e-6)
            if score > 0:
                scores.append((i, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# ---------------------------------------------------------------------------
# TF-IDF for contradiction detection
# ---------------------------------------------------------------------------

class _TfIdf:
    """TF-IDF vectorizer for cosine similarity."""

    def __init__(self):
        self.doc_freqs: dict[str, int] = defaultdict(int)
        self.corpus_size: int = 0

    def fit(self, documents: list[list[str]]) -> None:
        self.corpus_size = len(documents)
        self.doc_freqs = defaultdict(int)
        for doc in documents:
            for term in set(doc):
                self.doc_freqs[term] += 1

    def vectorize(self, tokens: list[str]) -> dict[str, float]:
        tf = Counter(tokens)
        vector = {}
        for term, count in tf.items():
            idf = math.log(
                (self.corpus_size + 1) / (self.doc_freqs.get(term, 0) + 1)
            ) + 1.0
            vector[term] = (count / max(len(tokens), 1)) * idf
        return vector

    @staticmethod
    def cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
        common = set(a.keys()) & set(b.keys())
        if not common:
            return 0.0
        dot = sum(a[t] * b[t] for t in common)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "and", "but", "or",
    "not", "no", "nor", "so", "yet", "both", "either", "neither", "each",
    "every", "all", "any", "few", "more", "most", "other", "some", "such",
    "than", "too", "very", "just", "about", "that", "this", "these", "those",
    "it", "its", "i", "me", "my", "we", "our", "you", "your", "he", "him",
    "his", "she", "her", "they", "them", "their", "what", "which", "who",
    "whom", "when", "where", "why", "how",
})


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


# ---------------------------------------------------------------------------
# EpisodicMemory
# ---------------------------------------------------------------------------

class EpisodicMemory:
    """Hybrid BM25 + embeddings + graph episodic memory.

    Works in three tiers depending on installed dependencies:
    - **Tier 0 (always available):** BM25 keyword recall + TF-IDF contradiction detection
    - **Tier 1 (+ sentence-transformers):** Adds semantic embedding recall via weighted RRF
    - **Tier 2 (+ grafeo):** Adds Grafeo graph for relational topic queries

    All tiers are local-first with no external API calls.
    """

    def __init__(self, db_path: str | None = None) -> None:
        # Core state
        self._entries: list[dict] = []
        self._entry_texts: list[str] = []
        self._entry_dates: list[str] = []
        self._documents: list[list[str]] = []
        self._bm25 = _BM25()
        self._tfidf = _TfIdf()
        self._index_dirty = True
        self._last_access: dict[str, datetime] = {}  # for FadeMem decay

        # Tier 1: Embeddings (optional)
        self._model = None
        self._entry_embeddings = None
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("EpisodicMemory: sentence-transformers loaded (Tier 1 — semantic recall)")
        except ImportError:
            logger.info(
                "sentence-transformers not installed — running BM25-only mode. "
                "Install with: pip install sentence-transformers"
            )

        # Tier 2: Graph (optional)
        self._db = None
        try:
            from grafeo import GrafeoDB
            if db_path is None:
                db_path = os.path.join(
                    tempfile.gettempdir(), "jarvis_episodic", "memory.db"
                )
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self._db = GrafeoDB(db_path)
            logger.info("EpisodicMemory: Grafeo loaded (Tier 2 — graph queries)")
        except ImportError:
            logger.info(
                "grafeo not installed — running without graph queries. "
                "Install with: pip install grafeo"
            )

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def _entry_to_text(self, entry_dict: dict) -> str:
        """Flatten a journal entry dict to searchable text."""
        parts = []
        parts.append(entry_dict.get("metadata", {}).get("dominant_theme", ""))
        for j in entry_dict.get("judgments", []):
            parts.append(j.get("action", ""))
            parts.append(j.get("reasoning", ""))
        for e in entry_dict.get("executions", []):
            parts.append(e.get("action", ""))
            parts.append(e.get("outcome", ""))
        for l in entry_dict.get("learnings", []):
            parts.append(l.get("content", ""))
        for d in entry_dict.get("dreams", []):
            parts.append(d.get("seed", ""))
            if d.get("breakthrough"):
                parts.append(d["breakthrough"])
        for bm in entry_dict.get("belief_mutations", []):
            parts.append(bm.get("belief", ""))
        return " ".join(parts)

    def index_journal_entry(self, entry: "JournalEntry") -> None:
        """Index a journal entry into episodic memory for later retrieval.

        Extracts text from all sections, tokenizes for BM25, and stores
        in the graph (if available). Embeddings are batch-computed on rebuild.

        Args:
            entry: The journal entry to index (Pydantic model or dict).
        """
        entry_dict = entry.model_dump() if hasattr(entry, "model_dump") else entry
        entry_date = entry_dict.get("metadata", {}).get("date", "unknown")
        text = self._entry_to_text(entry_dict)
        theme = entry_dict.get("metadata", {}).get("dominant_theme", "")

        self._entries.append(entry_dict)
        self._entry_texts.append(text)
        self._entry_dates.append(entry_date)

        # BM25: tokenize with bigrams
        tokens = _tokenize(text)
        bigrams = [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
        self._documents.append(tokens + bigrams)

        # Graph: create entry node
        if self._db is not None:
            try:
                safe_theme = theme.replace('"', '\\"')
                self._db.execute_cypher(
                    f'CREATE (n:Entry {{date: "{entry_date}", theme: "{safe_theme}"}})'
                )
            except Exception:
                pass

        self._index_dirty = True
        logger.debug("Indexed journal entry for %s", entry_date)

    def _rebuild_index(self) -> None:
        """Rebuild BM25 and embedding indexes when dirty."""
        if not self._index_dirty:
            return

        if self._documents:
            self._bm25.fit(self._documents)
            self._tfidf.fit(self._documents)

        if self._entry_texts and self._model is not None:
            self._entry_embeddings = self._model.encode(
                self._entry_texts, batch_size=64, show_progress_bar=False,
                normalize_embeddings=True,
            )

        self._index_dirty = False

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def recall_similar(self, query: str, top_k: int = 5) -> list[dict]:
        """Find past experiences similar to the given query.

        Uses weighted Reciprocal Rank Fusion (RRF) to combine:
        1. BM25 keyword ranking (weight=1.0)
        2. Embedding cosine similarity (weight=3.0)
        3. Graph theme traversal (weight=0.3)

        Args:
            query: Natural language description of the situation.
            top_k: Maximum number of results to return.

        Returns:
            List of matching episodes with date, score, and content.
        """
        self._rebuild_index()

        query_tokens = _tokenize(query)
        RRF_K = 60

        # System 1: BM25 keyword ranking
        bm25_by_date: dict[str, int] = {}
        if query_tokens:
            for rank, (doc_idx, _) in enumerate(
                self._bm25.rank(query_tokens, top_k=top_k * 3)
            ):
                date = self._entry_dates[doc_idx]
                if date not in bm25_by_date:
                    bm25_by_date[date] = rank

        # System 2: Embedding cosine similarity (Tier 1)
        embed_by_date: dict[str, int] = {}
        if self._model is not None and self._entry_embeddings is not None:
            import numpy as np
            query_emb = self._model.encode(
                [query], show_progress_bar=False, normalize_embeddings=True
            )
            sims = (self._entry_embeddings @ query_emb.T).flatten()
            for rank, idx in enumerate(np.argsort(sims)[::-1][:top_k * 3]):
                date = self._entry_dates[idx]
                if date not in embed_by_date:
                    embed_by_date[date] = rank

        # System 3: Graph theme traversal (Tier 2)
        graph_by_date: dict[str, int] = {}
        if self._db is not None:
            try:
                keywords = set(re.findall(r"[a-z]+", query.lower())) - {
                    "what", "do", "know", "about", "tell", "me", "recall",
                    "experiences", "related", "decisions", "made", "patterns",
                    "work", "have", "learned",
                }
                for word in list(keywords)[:3]:
                    result = self._db.execute_cypher(
                        f'MATCH (n:Entry) WHERE n.theme CONTAINS "{word}" RETURN n.date'
                    )
                    for row in result:
                        date = row.get("n.date", "unknown")
                        if date not in graph_by_date:
                            graph_by_date[date] = len(graph_by_date)
            except Exception:
                pass

        # Weighted RRF fusion
        W_BM25 = 1.0
        W_GRAPH = 0.3
        W_EMBED = 3.0

        all_dates = set(bm25_by_date) | set(graph_by_date) | set(embed_by_date)
        rrf_scores: dict[str, float] = {}

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
        max_possible = (W_BM25 + W_GRAPH + W_EMBED) / RRF_K

        results = []
        for date, score in sorted_dates[:top_k]:
            normalized = score / max_possible
            results.append({
                "date": date,
                "score": round(min(normalized, 1.0), 4),
                "content": self._entry_texts[self._entry_dates.index(date)][:300]
                if date in self._entry_dates else "",
            })
            # Track access for FadeMem
            self._last_access[date] = datetime.utcnow()

        return results

    # ------------------------------------------------------------------
    # Contradiction detection
    # ------------------------------------------------------------------

    def check_belief_conflict(self, belief_a: str, belief_b: str) -> dict:
        """Check if two beliefs contradict using TF-IDF cosine similarity.

        Args:
            belief_a: First belief text.
            belief_b: Second belief text.

        Returns:
            Dict with has_conflict, similarity_score, recommendation.
        """
        tokens_a = _tokenize(belief_a)
        tokens_b = _tokenize(belief_b)

        if self._tfidf.corpus_size == 0:
            self._tfidf.fit([tokens_a, tokens_b])

        vec_a = self._tfidf.vectorize(tokens_a)
        vec_b = self._tfidf.vectorize(tokens_b)
        sim = _TfIdf.cosine_similarity(vec_a, vec_b)

        has_conflict = sim > 0.6
        if sim > 0.85:
            rec = "merge"
        elif sim > 0.75:
            rec = "supersede"
        elif has_conflict:
            rec = "review"
        else:
            rec = "coexist"

        return {
            "has_conflict": has_conflict,
            "similarity_score": round(sim, 4),
            "recommendation": rec,
        }

    # ------------------------------------------------------------------
    # Reinforcement
    # ------------------------------------------------------------------

    def reinforce(self, entry_id: str) -> None:
        """Reinforce an episodic memory, resetting its FadeMem decay clock.

        Sets the memory's last_access timestamp to now, effectively
        resetting the Ebbinghaus decay curve to strength 1.0.

        Args:
            entry_id: The date (or ID) of the episodic memory to reinforce.
        """
        self._last_access[entry_id] = datetime.utcnow()
        logger.debug("Reinforced memory %s", entry_id)

    def get_decay_strength(self, entry_id: str, decay_rate: float = 0.02) -> float:
        """Get the current FadeMem strength for a memory.

        strength = e^(-decay_rate * days_since_last_access)

        Args:
            entry_id: The date (or ID) of the episodic memory.
            decay_rate: Decay constant (default 0.02 from Ebbinghaus curve).

        Returns:
            Strength value between 0 and 1.
        """
        last = self._last_access.get(entry_id)
        if last is None:
            return 1.0  # never accessed = full strength (just indexed)
        days = (datetime.utcnow() - last).total_seconds() / 86400
        return math.exp(-decay_rate * days)
