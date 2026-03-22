"""Hybrid backend: PageIndex BM25/tree + local sentence-transformer embeddings.

Combines the best of both worlds:
- BM25 for fast keyword matching (handles exact term queries)
- TF-IDF tree for hierarchical navigation
- sentence-transformers for semantic similarity (handles paraphrases/synonyms)
- 3-way RRF fusion for final ranking

Uses all-MiniLM-L6-v2 (22M params, ~80MB) running fully locally.
No external APIs required.
"""

import math
import numpy as np
from collections import defaultdict

from benchmarks.backends.base import MemoryBackend
from benchmarks.backends.pageindex_local import (
    BM25, TfIdf, TreeNode, tokenize,
)


class HybridEmbeddingsBackend(MemoryBackend):
    """PageIndex BM25/tree + local embeddings for semantic recall."""

    def __init__(self):
        self._entries: list[dict] = []
        self._beliefs: list[dict] = []
        self._documents: list[list[str]] = []
        self._entry_texts: list[str] = []  # raw text for embedding
        self._entry_map: list[str] = []
        self._bm25 = BM25()
        self._tfidf = TfIdf()
        self._tree: TreeNode | None = None
        self._belief_tokens: list[list[str]] = []
        self._belief_texts: list[str] = []
        self._belief_vectors: list[dict[str, float]] = []
        self._index_dirty: bool = True
        self._model = None
        self._entry_embeddings: np.ndarray | None = None
        self._belief_embeddings: np.ndarray | None = None

    def name(self) -> str:
        return "hybrid-embeddings"

    def setup(self, config: dict | None = None) -> None:
        from sentence_transformers import SentenceTransformer
        # Small, fast model — runs on CPU in <1ms per sentence
        self._model = SentenceTransformer("all-MiniLM-L6-v2")
        self._entries = []
        self._beliefs = []
        self._documents = []
        self._entry_texts = []
        self._entry_map = []
        self._belief_tokens = []
        self._belief_texts = []
        self._belief_vectors = []
        self._entry_embeddings = None
        self._belief_embeddings = None
        self._index_dirty = True

    def teardown(self) -> None:
        self._entries = []
        self._beliefs = []
        self._documents = []
        self._entry_texts = []
        self._entry_map = []
        self._tree = None
        self._entry_embeddings = None
        self._belief_embeddings = None
        self._model = None

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
        self._entries.append(entry)

        text = self._entry_to_text(entry)
        self._entry_texts.append(text)
        tokens = tokenize(text)
        bigrams = [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
        self._documents.append(tokens + bigrams)
        self._entry_map.append(entry_date)
        self._index_dirty = True
        return entry_date

    def store_belief(self, belief: dict) -> str:
        self._beliefs.append(belief)
        belief_text = belief.get("belief", "") + " " + belief.get("reason", "")
        self._belief_texts.append(belief_text)
        tokens = tokenize(belief_text)
        self._belief_tokens.append(tokens)
        self._index_dirty = True
        return belief.get("belief", "")[:32]

    def _rebuild_index(self) -> None:
        if not self._index_dirty:
            return
        if self._documents:
            self._bm25.fit(self._documents)
            self._tfidf.fit(self._documents)
        if self._belief_tokens:
            self._tfidf.fit(self._documents + self._belief_tokens)
            self._belief_vectors = [
                self._tfidf.vectorize(tokens) for tokens in self._belief_tokens
            ]

        # Batch-encode all entries and beliefs (pre-normalized for fast cosine via dot product)
        if self._entry_texts and self._model:
            self._entry_embeddings = self._model.encode(
                self._entry_texts, batch_size=64, show_progress_bar=False,
                normalize_embeddings=True,
            )
        if self._belief_texts and self._model:
            self._belief_embeddings = self._model.encode(
                self._belief_texts, batch_size=64, show_progress_bar=False,
                normalize_embeddings=True,
            )

        self._build_tree()
        self._index_dirty = False

    def _build_tree(self) -> None:
        root = TreeNode(node_id="root", title="Memory", summary="All memories", level=0)
        by_theme: dict[str, list[dict]] = defaultdict(list)
        for entry in self._entries:
            theme = entry.get("metadata", {}).get("dominant_theme", "uncategorized")
            by_theme[theme].append(entry)

        for theme, entries in by_theme.items():
            theme_node = TreeNode(
                node_id=f"theme_{theme.replace(' ', '_')}",
                title=theme,
                summary=f"{len(entries)} entries about {theme}",
                level=1,
            )
            combined = " ".join(self._entry_to_text(e) for e in entries)
            theme_node.tf_idf_vector = self._tfidf.vectorize(tokenize(combined))
            root.children.append(theme_node)

        self._tree = root

    def recall(self, query: str, top_k: int = 5) -> list[dict]:
        """3-way RRF: BM25 + tree TF-IDF + embedding cosine similarity."""
        self._rebuild_index()

        query_tokens = tokenize(query)
        if not query_tokens and not self._model:
            return []

        RRF_K = 60

        # System 1: BM25 flat ranking
        bm25_by_date: dict[str, int] = {}
        if query_tokens:
            bm25_ranked = self._bm25.rank(query_tokens, top_k=top_k * 3)
            for rank, (doc_idx, _) in enumerate(bm25_ranked):
                date = self._entry_map[doc_idx]
                if date not in bm25_by_date:
                    bm25_by_date[date] = rank

        # System 2: Tree-guided TF-IDF cosine
        tree_by_date: dict[str, int] = {}
        if self._tree and self._tree.children and query_tokens:
            query_vec = self._tfidf.vectorize(query_tokens)
            theme_scores = []
            for child in self._tree.children:
                if child.tf_idf_vector:
                    sim = TfIdf.cosine_similarity(query_vec, child.tf_idf_vector)
                    theme_scores.append((child, sim))
            theme_scores.sort(key=lambda x: x[1], reverse=True)

            tree_entries = []
            for theme_node, _ in theme_scores[:3]:
                for entry in self._entries:
                    if entry.get("metadata", {}).get("dominant_theme") == theme_node.title:
                        tree_entries.append(entry)

            for rank, entry in enumerate(tree_entries):
                date = entry.get("metadata", {}).get("date", "unknown")
                if date not in tree_by_date:
                    tree_by_date[date] = rank

        # System 3: Embedding cosine similarity (semantic)
        embed_by_date: dict[str, int] = {}
        if self._model is not None and self._entry_embeddings is not None:
            query_embedding = self._model.encode(
                [query], show_progress_bar=False, normalize_embeddings=True
            )
            # Normalized embeddings → dot product = cosine similarity
            similarities = self._entry_embeddings @ query_embedding.T
            similarities = similarities.flatten()
            # Use partial sort for top-k (faster than full argsort)
            k = min(top_k * 3, len(similarities))
            top_indices = np.argpartition(similarities, -k)[-k:]
            top_indices = top_indices[np.argsort(similarities[top_indices])[::-1]]

            for rank, idx in enumerate(top_indices):
                date = self._entry_map[idx]
                if date not in embed_by_date:
                    embed_by_date[date] = rank

        # 3-way RRF
        all_dates = set(bm25_by_date.keys()) | set(tree_by_date.keys()) | set(embed_by_date.keys())
        rrf_scores: dict[str, float] = {}

        for date in all_dates:
            score = 0.0
            if date in bm25_by_date:
                score += 1.0 / (RRF_K + bm25_by_date[date])
            if date in tree_by_date:
                score += 1.0 / (RRF_K + tree_by_date[date])
            if date in embed_by_date:
                score += 1.0 / (RRF_K + embed_by_date[date])
            rrf_scores[date] = score

        sorted_dates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        results = []
        for date, score in sorted_dates[:top_k]:
            max_possible = 3.0 / RRF_K
            normalized = score / max_possible
            results.append({
                "date": date,
                "score": round(min(normalized, 1.0), 4),
                "content": "",
                "source": "rrf+embed",
            })

        return results

    def check_contradiction(self, belief_a: str, belief_b: str) -> dict:
        """Embedding-based contradiction detection."""
        if self._model is None:
            return {"has_conflict": False, "similarity_score": 0.0, "recommendation": "coexist"}

        embeddings = self._model.encode([belief_a, belief_b], show_progress_bar=False)
        similarity = float(np.dot(embeddings[0], embeddings[1]) / (
            np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
        ))

        # Embedding similarity captures semantic closeness:
        # High similarity (>0.45) on belief statements means they address the
        # same topic — if the wording differs, that signals a potential conflict
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
        self._rebuild_index()

        if self._model is None or self._belief_embeddings is None:
            return list(self._beliefs)

        query_embedding = self._model.encode([topic], show_progress_bar=False)
        similarities = np.dot(self._belief_embeddings, query_embedding.T).flatten()
        ranked_indices = np.argsort(similarities)[::-1]

        results = []
        for idx in ranked_indices:
            if similarities[idx] > 0.2:
                results.append(self._beliefs[idx])
        return results

    def get_memory_usage_mb(self) -> float:
        import sys
        total = sys.getsizeof(self._entries) + sys.getsizeof(self._documents)
        if self._entry_embeddings is not None:
            total += self._entry_embeddings.nbytes
        if self._belief_embeddings is not None:
            total += self._belief_embeddings.nbytes
        return total / (1024 * 1024)
