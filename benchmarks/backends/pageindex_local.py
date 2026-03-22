"""PageIndex-inspired hierarchical tree indexing with local BM25/TF-IDF.

Implements the PageIndex concept of tree-structured document navigation
without external LLM API calls. Uses:
- TF-IDF for document/node scoring
- BM25 (Okapi BM25) for retrieval ranking
- Hierarchical tree construction from journal entries
- Beam search for tree navigation with local similarity scoring
- Cosine similarity on TF-IDF vectors for contradiction detection

Mathematical foundations:
- BM25 scoring: score(D,Q) = Σ IDF(qi) · (f(qi,D) · (k1+1)) / (f(qi,D) + k1 · (1 - b + b · |D|/avgdl))
- TF-IDF: tf(t,d) · log(N/df(t))
- Cosine similarity: cos(θ) = (A·B) / (||A||·||B||)
"""

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field


@dataclass
class TreeNode:
    """A node in the hierarchical memory tree."""
    node_id: str
    title: str
    summary: str
    children: list["TreeNode"] = field(default_factory=list)
    entries: list[dict] = field(default_factory=list)  # leaf data
    level: int = 0
    tf_idf_vector: dict[str, float] = field(default_factory=dict)


class BM25:
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
        """Build BM25 index from tokenized documents."""
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
        self._compute_idf()

    def _compute_idf(self) -> None:
        """Compute IDF scores for all terms."""
        self.idf_cache = {}
        for term, df in self.doc_freqs.items():
            # Standard BM25 IDF formula
            self.idf_cache[term] = math.log(
                (self.corpus_size - df + 0.5) / (df + 0.5) + 1.0
            )

    def score(self, query_tokens: list[str], doc_idx: int) -> float:
        """Score a single document against a query."""
        if doc_idx >= len(self.doc_term_freqs):
            return 0.0

        score = 0.0
        doc_len = self.doc_lens[doc_idx]
        term_freqs = self.doc_term_freqs[doc_idx]

        for qt in query_tokens:
            if qt not in self.idf_cache:
                continue
            idf = self.idf_cache[qt]
            tf = term_freqs.get(qt, 0)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self.avgdl, 1))
            score += idf * numerator / max(denominator, 1e-6)

        return score

    def rank(self, query_tokens: list[str], top_k: int = 5) -> list[tuple[int, float]]:
        """Rank all documents for a query. Returns (doc_idx, score) pairs."""
        scores = []
        for i in range(self.corpus_size):
            s = self.score(query_tokens, i)
            if s > 0:
                scores.append((i, s))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class TfIdf:
    """TF-IDF vectorizer for cosine similarity comparisons."""

    def __init__(self):
        self.doc_freqs: dict[str, int] = defaultdict(int)
        self.corpus_size: int = 0

    def fit(self, documents: list[list[str]]) -> None:
        """Build IDF from corpus."""
        self.corpus_size = len(documents)
        self.doc_freqs = defaultdict(int)
        for doc in documents:
            for term in set(doc):
                self.doc_freqs[term] += 1

    def vectorize(self, tokens: list[str]) -> dict[str, float]:
        """Convert a token list to a TF-IDF vector."""
        tf = Counter(tokens)
        vector = {}
        for term, count in tf.items():
            idf = math.log(
                (self.corpus_size + 1) / (self.doc_freqs.get(term, 0) + 1)
            ) + 1.0
            vector[term] = (count / max(len(tokens), 1)) * idf
        return vector

    @staticmethod
    def cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
        """Cosine similarity between two sparse vectors."""
        common_terms = set(vec_a.keys()) & set(vec_b.keys())
        if not common_terms:
            return 0.0

        dot_product = sum(vec_a[t] * vec_b[t] for t in common_terms)
        norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
        norm_b = math.sqrt(sum(v * v for v in vec_b.values()))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


def tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric, remove stopwords."""
    STOPWORDS = {
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
    }
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


# ---- Backend implementation ----

from benchmarks.backends.base import MemoryBackend


class PageIndexLocalBackend(MemoryBackend):
    """Hierarchical tree memory with BM25/TF-IDF local scoring."""

    def __init__(self):
        self._entries: list[dict] = []
        self._beliefs: list[dict] = []
        self._documents: list[list[str]] = []  # tokenized entry texts
        self._entry_map: list[str] = []  # date for each doc index
        self._bm25 = BM25()
        self._tfidf = TfIdf()
        self._tree: TreeNode | None = None
        self._belief_vectors: list[dict[str, float]] = []
        self._belief_tokens: list[list[str]] = []

    def name(self) -> str:
        return "pageindex-local"

    def setup(self, config: dict | None = None) -> None:
        self._entries = []
        self._beliefs = []
        self._documents = []
        self._entry_map = []
        self._belief_vectors = []
        self._belief_tokens = []

    def teardown(self) -> None:
        self._entries = []
        self._beliefs = []
        self._documents = []
        self._entry_map = []
        self._tree = None
        self._belief_vectors = []
        self._belief_tokens = []

    def _entry_to_text(self, entry: dict) -> str:
        """Flatten a journal entry to searchable text."""
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
        tokens = tokenize(text)
        self._documents.append(tokens)
        self._entry_map.append(entry_date)

        return entry_date

    def _rebuild_index(self) -> None:
        """Rebuild BM25 and TF-IDF indexes after all entries are stored."""
        if self._documents:
            self._bm25.fit(self._documents)
            self._tfidf.fit(self._documents)
        if self._belief_tokens:
            self._tfidf.fit(self._documents + self._belief_tokens)
            self._belief_vectors = [
                self._tfidf.vectorize(tokens) for tokens in self._belief_tokens
            ]
        self._build_tree()

    def store_belief(self, belief: dict) -> str:
        self._beliefs.append(belief)
        tokens = tokenize(belief.get("belief", "") + " " + belief.get("reason", ""))
        self._belief_tokens.append(tokens)
        return belief.get("belief", "")[:32]

    def _build_tree(self) -> None:
        """Build hierarchical tree from entries grouped by topic."""
        root = TreeNode(node_id="root", title="Memory", summary="All memories", level=0)

        # Group entries by dominant theme
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

            # Sub-group by month
            by_month: dict[str, list[dict]] = defaultdict(list)
            for entry in entries:
                month = entry.get("metadata", {}).get("date", "")[:7]
                by_month[month].append(entry)

            for month, month_entries in by_month.items():
                month_node = TreeNode(
                    node_id=f"month_{theme.replace(' ', '_')}_{month}",
                    title=f"{theme} — {month}",
                    summary=f"{len(month_entries)} entries",
                    entries=month_entries,
                    level=2,
                )
                # Compute TF-IDF vector for the month node
                combined_text = " ".join(
                    self._entry_to_text(e) for e in month_entries
                )
                month_node.tf_idf_vector = self._tfidf.vectorize(tokenize(combined_text))
                theme_node.children.append(month_node)

            # Compute TF-IDF vector for theme node
            combined_text = " ".join(
                self._entry_to_text(e) for e in entries
            )
            theme_node.tf_idf_vector = self._tfidf.vectorize(tokenize(combined_text))
            root.children.append(theme_node)

        self._tree = root

    def recall(self, query: str, top_k: int = 5) -> list[dict]:
        """Two-phase recall: BM25 flat search + tree-guided refinement."""
        self._rebuild_index()

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        # Phase 1: BM25 flat search
        bm25_results = self._bm25.rank(query_tokens, top_k=top_k * 2)

        # Phase 2: Tree-guided beam search for additional candidates
        tree_results = self._tree_search(query_tokens, beam_width=3, top_k=top_k)

        # Merge and deduplicate
        seen_dates = set()
        merged = []

        # Combine BM25 + tree results, normalize scores
        max_bm25 = max((s for _, s in bm25_results), default=1.0)

        for doc_idx, score in bm25_results:
            date = self._entry_map[doc_idx]
            if date not in seen_dates:
                seen_dates.add(date)
                normalized = score / max(max_bm25, 1e-6)
                merged.append({
                    "date": date,
                    "score": round(min(normalized, 1.0), 4),
                    "content": " ".join(self._documents[doc_idx][:50]),
                    "source": "bm25",
                })

        for result in tree_results:
            date = result["date"]
            if date not in seen_dates:
                seen_dates.add(date)
                merged.append(result)

        merged.sort(key=lambda x: x["score"], reverse=True)
        return merged[:top_k]

    def _tree_search(
        self, query_tokens: list[str], beam_width: int = 3, top_k: int = 5
    ) -> list[dict]:
        """Beam search through the hierarchical tree using TF-IDF similarity."""
        if not self._tree or not self._tree.children:
            return []

        query_vector = self._tfidf.vectorize(query_tokens)
        results = []

        # Score top-level theme nodes
        theme_scores = []
        for child in self._tree.children:
            if child.tf_idf_vector:
                sim = TfIdf.cosine_similarity(query_vector, child.tf_idf_vector)
                theme_scores.append((child, sim))
        theme_scores.sort(key=lambda x: x[1], reverse=True)

        # Beam search: explore top-k themes
        for theme_node, theme_sim in theme_scores[:beam_width]:
            # Score month nodes within the theme
            for month_node in theme_node.children:
                if month_node.tf_idf_vector:
                    sim = TfIdf.cosine_similarity(query_vector, month_node.tf_idf_vector)
                    for entry in month_node.entries:
                        date = entry.get("metadata", {}).get("date", "unknown")
                        results.append({
                            "date": date,
                            "score": round(sim * 0.9, 4),  # slight penalty for tree path
                            "content": self._entry_to_text(entry)[:200],
                            "source": "tree",
                        })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def check_contradiction(self, belief_a: str, belief_b: str) -> dict:
        """TF-IDF cosine similarity-based contradiction detection."""
        tokens_a = tokenize(belief_a)
        tokens_b = tokenize(belief_b)

        # Use the corpus-trained TF-IDF if available, otherwise fit on these two
        if self._tfidf.corpus_size == 0:
            self._tfidf.fit([tokens_a, tokens_b])

        vec_a = self._tfidf.vectorize(tokens_a)
        vec_b = self._tfidf.vectorize(tokens_b)
        similarity = TfIdf.cosine_similarity(vec_a, vec_b)

        # High similarity on belief text suggests they're about the same topic
        # but different conclusions → potential contradiction
        has_conflict = similarity > 0.6  # lower threshold since TF-IDF is more discriminating

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
        """Query beliefs using TF-IDF similarity scoring."""
        self._rebuild_index()

        topic_tokens = tokenize(topic)
        if not topic_tokens:
            return list(self._beliefs)

        topic_vector = self._tfidf.vectorize(topic_tokens)
        scored = []

        for i, belief in enumerate(self._beliefs):
            if i < len(self._belief_vectors):
                sim = TfIdf.cosine_similarity(topic_vector, self._belief_vectors[i])
                if sim > 0.1:
                    scored.append((belief, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [b for b, _ in scored]

    def get_memory_usage_mb(self) -> float:
        import sys
        total = 0
        total += sys.getsizeof(self._entries)
        total += sys.getsizeof(self._documents)
        total += sys.getsizeof(self._beliefs)
        total += sys.getsizeof(self._belief_vectors)
        # Estimate BM25 index size
        total += sys.getsizeof(self._bm25.doc_term_freqs)
        total += sys.getsizeof(self._bm25.doc_freqs)
        return total / (1024 * 1024)
