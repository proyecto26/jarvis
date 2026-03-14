"""Temporal belief store — Graphiti + KuzuDB backend (Phase 2 foundation).

Provides ``TemporalBeliefStore`` with point-in-time belief queries, lineage
tracking, and a working ``migrate_from_json()`` that reads the existing flat
``judge_beliefs.json`` and reports what would be migrated.

All graph-dependent methods degrade gracefully without Graphiti/KuzuDB installed.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from triforce.config import Config

logger = logging.getLogger(__name__)


class TemporalBeliefStore:
    """Temporal belief graph backed by Graphiti + KuzuDB.

    Phase 2 will provide full graph implementation. This foundation class
    establishes the interface, implements ``migrate_from_json()``, and
    degrades gracefully without graph dependencies.
    """

    def __init__(self) -> None:
        self._graph = None
        try:
            import graphiti_core  # noqa: F401
            import kuzu  # noqa: F401
            raise NotImplementedError(
                "TemporalBeliefStore Phase 2 not yet wired. "
                "Implement Graphiti+KuzuDB initialisation here."
            )
        except ImportError:
            logger.info(
                "graphiti-core/kuzu not installed — TemporalBeliefStore running "
                "in stub mode. Install with: pip install jarvis-triforce[memory]"
            )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write_belief(
        self,
        belief: str,
        strength: float,
        reason: str,
        source_episode_id: str,
        supersedes_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> str:
        """Write a belief edge to the temporal graph.

        Phase 2 implementation will:
        1. Create a BeliefEdge with valid_from=now
        2. If supersedes_id, set valid_until=now on the superseded edge
        3. Store in KuzuDB with temporal validity window

        Returns:
            The ID of the new belief edge.

        Raises:
            NotImplementedError: Always, until Phase 2 is complete.
        """
        raise NotImplementedError(
            "write_belief requires Phase 2 Graphiti+KuzuDB integration."
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query_current(self, topic: str) -> list[dict]:
        """Return beliefs where valid_until IS NULL, ordered by strength.

        Raises:
            NotImplementedError: Always, until Phase 2 is complete.
        """
        raise NotImplementedError(
            "query_current requires Phase 2 Graphiti+KuzuDB integration."
        )

    def query_at(self, topic: str, at: datetime) -> list[dict]:
        """Point-in-time query: return beliefs valid at a specific past date.

        Raises:
            NotImplementedError: Always, until Phase 2 is complete.
        """
        raise NotImplementedError(
            "query_at requires Phase 2 Graphiti+KuzuDB integration."
        )

    def get_belief_history(self, belief_id: str) -> list[dict]:
        """Return the full lineage chain for a belief from origin through all mutations.

        Raises:
            NotImplementedError: Always, until Phase 2 is complete.
        """
        raise NotImplementedError(
            "get_belief_history requires Phase 2 Graphiti+KuzuDB integration."
        )

    # ------------------------------------------------------------------
    # Migration
    # ------------------------------------------------------------------

    def migrate_from_json(self, *, dry_run: bool = True) -> list[dict]:
        """Migrate beliefs from judge_beliefs.json to the temporal graph.

        Reads the existing flat JSON beliefs file and either prints what
        would be migrated (dry_run=True) or performs the migration (dry_run=False).

        This method works without Graphiti/KuzuDB in dry-run mode.

        Args:
            dry_run: If True (default), only report what would be migrated.
                     If False, actually write to the graph (requires Phase 2).

        Returns:
            List of belief dicts that would be / were migrated.
        """
        beliefs_path = Config.BELIEFS_PATH
        try:
            data = json.loads(beliefs_path.read_text())
            beliefs = data.get("beliefs", [])
        except FileNotFoundError:
            logger.info("No judge_beliefs.json found at %s — nothing to migrate.", beliefs_path)
            return []
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse judge_beliefs.json: %s", exc)
            return []

        if not beliefs:
            logger.info("judge_beliefs.json exists but contains no beliefs.")
            return []

        migration_plan: list[dict] = []
        for i, b in enumerate(beliefs):
            entry = {
                "index": i,
                "belief": b.get("belief", ""),
                "strength": b.get("strength", 0.5),
                "reason": b.get("reason", ""),
                "created": b.get("created", "unknown"),
                "updated": b.get("updated", "unknown"),
                "action": "would_create_edge" if dry_run else "create_edge",
            }
            migration_plan.append(entry)

        if dry_run:
            logger.info(
                "DRY RUN — %d beliefs would be migrated from %s:",
                len(migration_plan),
                beliefs_path,
            )
            for entry in migration_plan:
                logger.info(
                    "  [%d] %s (strength=%.2f, created=%s)",
                    entry["index"],
                    entry["belief"][:80],
                    entry["strength"],
                    entry["created"],
                )
        else:
            if self._graph is None:
                raise NotImplementedError(
                    "Live migration requires Phase 2 Graphiti+KuzuDB. "
                    "Run with dry_run=True to preview, or install dependencies."
                )
            # Phase 2: iterate migration_plan and call self.write_belief() for each

        return migration_plan
