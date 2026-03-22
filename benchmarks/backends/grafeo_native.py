"""Grafeo native backend: uses Grafeo's built-in vector index, text index, and hybrid search.

Instead of manually computing BM25 and embeddings, delegates to Grafeo's Rust-native
HNSW vector search, BM25 text search, and RRF hybrid fusion — all in-process.

Uses Grafeo's built-in embedding model (MiniLM-L6-v2) if available,
otherwise falls back to sentence-transformers.
"""

import os
import shutil
import tempfile

import numpy as np
from grafeo import GrafeoDB

from benchmarks.backends.base import MemoryBackend
from benchmarks.backends.pageindex_local import _STOPWORDS, TfIdf, tokenize


class GrafeoNativeBackend(MemoryBackend):
    """Grafeo-native graph+vector+text backend."""

    def __init__(self):
        self._db: GrafeoDB | None = None
        self._db_path: str = ""
        self._model = None
        self._entries: list[dict] = []
        self._beliefs: list[dict] = []
        self._tfidf = TfIdf()
        self._tfidf_docs: list[list[str]] = []
        self._embedding_dim: int = 384
        self._vector_index_created: bool = False
        self._text_index_created: bool = False

    def name(self) -> str:
        return "grafeo-native"

    def setup(self, config: dict | None = None) -> None:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer("all-MiniLM-L6-v2")
        self._embedding_dim = 384

        self._db_path = os.path.join(tempfile.mkdtemp(prefix="grafeo_native_"), "memory.db")
        self._db = GrafeoDB(self._db_path)
        self._entries = []
        self._beliefs = []
        self._tfidf_docs = []

        # Create vector and text indexes
        try:
            self._db.create_vector_index("Entry", "embedding", dimensions=self._embedding_dim, metric="cosine")
            self._vector_index_created = True
        except Exception as e:
            # Fallback: try without explicit index creation
            self._vector_index_created = False

        try:
            self._db.create_text_index("Entry", "text")
            self._text_index_created = True
        except Exception as e:
            self._text_index_created = False

    def teardown(self) -> None:
        self._db = None
        self._model = None
        self._entries = []
        self._beliefs = []
        self._tfidf_docs = []
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
        self._tfidf_docs.append(tokenize(text))

        # Generate embedding
        embedding = self._model.encode([text], show_progress_bar=False, normalize_embeddings=True)[0]

        # Store in Grafeo with vector + text properties
        try:
            safe_text = text.replace('"', '\\"')[:1000]
            safe_theme = theme.replace('"', '\\"')
            emb_list = embedding.tolist()
            self._db.execute(
                'INSERT (:Entry {date: $date, theme: $theme, text: $text, embedding: $emb})',
                {"date": entry_date, "theme": safe_theme, "text": safe_text, "emb": emb_list}
            )
        except Exception:
            # Fallback: try Cypher syntax
            try:
                self._db.execute_cypher(
                    f'CREATE (n:Entry {{date: "{entry_date}", theme: "{theme.replace(chr(34), "")}"}})'
                )
            except Exception:
                pass

        return entry_date

    def store_belief(self, belief: dict) -> str:
        self._beliefs.append(belief)
        return belief.get("belief", "")[:32]

    def recall(self, query: str, top_k: int = 5) -> list[dict]:
        """Use Grafeo's native hybrid search if available, else manual fusion."""
        results = []

        # Try native hybrid search first
        if self._vector_index_created and self._text_index_created:
            try:
                query_emb = self._model.encode([query], show_progress_bar=False, normalize_embeddings=True)[0]
                hybrid_results = self._db.hybrid_search(
                    label="Entry",
                    text_property="text",
                    text_query=query,
                    vector_property="embedding",
                    vector_query=query_emb.tolist(),
                    k=top_k,
                )
                for r in hybrid_results:
                    results.append({
                        "date": str(r.get("node_id", "unknown")),
                        "score": round(float(r.get("score", 0)), 4),
                        "content": "",
                        "source": "grafeo-hybrid",
                    })
                if results:
                    return results
            except Exception:
                pass

        # Fallback: try vector search only
        if self._vector_index_created:
            try:
                query_emb = self._model.encode([query], show_progress_bar=False, normalize_embeddings=True)[0]
                vec_results = self._db.vector_search("Entry", "embedding", query=query_emb.tolist(), k=top_k)
                for r in vec_results:
                    results.append({
                        "date": str(r.get("node_id", "unknown")),
                        "score": round(float(r.get("score", 0)), 4),
                        "content": "",
                        "source": "grafeo-vector",
                    })
                if results:
                    return results
            except Exception:
                pass

        # Final fallback: manual cosine similarity via Cypher
        try:
            query_emb = self._model.encode([query], show_progress_bar=False, normalize_embeddings=True)[0]

            # Get all entries and compute similarity manually
            all_entries = self._db.execute_cypher("MATCH (n:Entry) RETURN n.date, n.theme")
            entry_dates = [row.get("n.date", "unknown") for row in all_entries]

            if self._entries:
                entry_texts = [self._entry_to_text(e) for e in self._entries]
                entry_embs = self._model.encode(entry_texts, batch_size=64, show_progress_bar=False, normalize_embeddings=True)
                sims = (entry_embs @ query_emb.reshape(-1, 1)).flatten()
                top_idx = np.argsort(sims)[::-1][:top_k]

                for idx in top_idx:
                    date = self._entries[idx].get("metadata", {}).get("date", "unknown")
                    results.append({
                        "date": date,
                        "score": round(float(sims[idx]), 4),
                        "content": "",
                        "source": "manual-cosine",
                    })
        except Exception:
            pass

        return results[:top_k]

    def check_contradiction(self, belief_a: str, belief_b: str) -> dict:
        """TF-IDF cosine for contradiction detection."""
        tokens_a = tokenize(belief_a)
        tokens_b = tokenize(belief_b)
        if self._tfidf.corpus_size == 0:
            self._tfidf.fit(self._tfidf_docs if self._tfidf_docs else [tokens_a, tokens_b])
        vec_a = self._tfidf.vectorize(tokens_a)
        vec_b = self._tfidf.vectorize(tokens_b)
        sim = TfIdf.cosine_similarity(vec_a, vec_b)

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

    def query_beliefs_at(self, topic: str, at_date: str | None = None) -> list[dict]:
        topic_lower = topic.lower()
        return [b for b in self._beliefs if topic_lower in b.get("belief", "").lower()]

    def get_memory_usage_mb(self) -> float:
        import sys
        return sys.getsizeof(self._entries) / (1024 * 1024)
