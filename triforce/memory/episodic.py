"""Episodic memory — Mem0 + ChromaDB hybrid retrieval (Phase 2 foundation).

This module provides the ``EpisodicMemory`` class that will back the
``recall_episodic`` tool once Mem0 and ChromaDB dependencies are installed.
Until then, all methods degrade gracefully — ``recall_similar`` returns an
empty list with a log message, and indexing stubs raise ``NotImplementedError``
with guidance on completing the Phase 2 setup.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from triforce.memory.schema import JournalEntry

logger = logging.getLogger(__name__)


class EpisodicMemory:
    """Hybrid semantic + BM25 episodic memory backed by Mem0 + ChromaDB.

    Phase 2 will provide full implementation. This foundation class
    establishes the interface and degrades gracefully without dependencies.
    """

    def __init__(self) -> None:
        self._client = None
        try:
            import mem0  # noqa: F401 — presence check only
            # Phase 2: initialise Mem0 client with ChromaDB config here
            raise NotImplementedError(
                "EpisodicMemory Phase 2 not yet wired. "
                "Install mem0ai and chromadb, then implement the client "
                "initialisation in triforce/memory/episodic.py.__init__."
            )
        except ImportError:
            logger.info(
                "mem0ai not installed — EpisodicMemory running in stub mode. "
                "Install with: pip install jarvis-triforce[memory]"
            )

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_journal_entry(self, entry: "JournalEntry") -> None:
        """Index a journal entry into episodic memory for later retrieval.

        Phase 2 implementation will:
        1. Extract each DreamCycle idea, Judgment, and Execution
        2. Generate embeddings (Ollama nomic-embed-text or Gemini fallback)
        3. Store in ChromaDB with metadata (date, section, cognitive_load_score)

        Args:
            entry: The journal entry to index.

        Raises:
            NotImplementedError: Always, until Phase 2 is complete.
        """
        raise NotImplementedError(
            "index_journal_entry requires Phase 2 Mem0 integration. "
            "See openspec/changes/trinity-phase-2-memory/specs/episodic-memory/spec.md"
        )

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def recall_similar(self, query: str, top_k: int = 5) -> list[dict]:
        """Find past experiences similar to the given query.

        Phase 2 implementation will perform hybrid semantic + BM25 retrieval
        via Mem0 and return results as ActMem-style reasoning chains.

        In stub mode, returns an empty list and logs a message.

        Args:
            query: Natural language description of the situation.
            top_k: Maximum number of results to return.

        Returns:
            List of matching episodes (empty in stub mode).
        """
        if self._client is None:
            logger.info(
                "EpisodicMemory.recall_similar called in stub mode — "
                "returning empty results. Use recall_similar_decisions "
                "as fallback until Phase 2."
            )
            return []

        # Phase 2: Mem0 hybrid retrieval here
        raise NotImplementedError("recall_similar not yet implemented")

    # ------------------------------------------------------------------
    # Reinforcement
    # ------------------------------------------------------------------

    def reinforce(self, entry_id: str) -> None:
        """Reinforce an episodic memory, resetting its FadeMem decay clock.

        Phase 2 implementation will set the memory's last_access timestamp
        to now, effectively resetting the Ebbinghaus decay curve to strength 1.0.

        Args:
            entry_id: The ID of the episodic memory entry to reinforce.

        Raises:
            NotImplementedError: Always, until Phase 2 is complete.
        """
        raise NotImplementedError(
            "reinforce requires Phase 2 Mem0 integration. "
            "See openspec/changes/trinity-phase-2-memory/specs/episodic-memory/spec.md"
        )
