"""Abstract base class for memory backends."""

from abc import ABC, abstractmethod


class MemoryBackend(ABC):
    """Interface that all memory backends must implement."""

    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this backend."""

    @abstractmethod
    def setup(self, config: dict | None = None) -> None:
        """Initialize the backend (create tables, indexes, etc.)."""

    @abstractmethod
    def teardown(self) -> None:
        """Clean up resources."""

    @abstractmethod
    def store_entry(self, entry: dict) -> str:
        """Store a journal entry. Returns an entry ID."""

    @abstractmethod
    def store_belief(self, belief: dict) -> str:
        """Store a belief. Returns a belief ID."""

    @abstractmethod
    def recall(self, query: str, top_k: int = 5) -> list[dict]:
        """Recall entries relevant to the query.

        Returns list of dicts with at minimum:
        - date: the journal entry date
        - score: relevance score (0-1)
        - content: the matched content text
        """

    @abstractmethod
    def check_contradiction(self, belief_a: str, belief_b: str) -> dict:
        """Check if two beliefs contradict each other.

        Returns dict with:
        - has_conflict: bool
        - similarity_score: float (0-1)
        - recommendation: str
        """

    @abstractmethod
    def query_beliefs_at(self, topic: str, at_date: str | None = None) -> list[dict]:
        """Query beliefs about a topic, optionally at a point in time."""

    def get_memory_usage_mb(self) -> float:
        """Return approximate memory usage in MB."""
        import psutil
        import os
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
