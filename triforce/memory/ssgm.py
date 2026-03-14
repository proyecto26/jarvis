"""SSGM conflict detection for belief mutations.

Provides ``SSGMGuard`` with a ``check_conflict()`` method that works on the
existing flat JSON beliefs using simple string similarity as a placeholder
for Phase 2's embedding-based cosine similarity.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from triforce.memory.beliefs import load_beliefs

logger = logging.getLogger(__name__)

# Thresholds from SSGM spec
SIMILARITY_THRESHOLD = 0.7
STRENGTH_THRESHOLD = 0.7


@dataclass
class ConflictReport:
    """Result of an SSGM conflict check."""

    has_conflict: bool = False
    conflicting_belief_id: int | None = None
    conflicting_belief_text: str = ""
    similarity_score: float = 0.0
    recommendation: str = ""  # merge | supersede | coexist | review

    def to_dict(self) -> dict:
        return {
            "has_conflict": self.has_conflict,
            "conflicting_belief_id": self.conflicting_belief_id,
            "conflicting_belief_text": self.conflicting_belief_text,
            "similarity_score": round(self.similarity_score, 3),
            "recommendation": self.recommendation,
        }


@dataclass
class StabilityReport:
    """Result of a belief stability check."""

    mutations_last_7_days: int = 0
    drift_warning: bool = False
    oscillation_detected: bool = False
    details: list[str] = field(default_factory=list)


class SSGMGuard:
    """Self-Supervised Goal Mutation conflict detection.

    Uses simple string similarity (SequenceMatcher) as a placeholder for
    Phase 2's embedding-based cosine similarity. The interface is stable —
    only the similarity computation changes in Phase 2.
    """

    def check_conflict(self, new_belief: str) -> ConflictReport:
        """Check whether a new belief conflicts with existing beliefs.

        A conflict is detected when an existing belief has:
        - similarity > SIMILARITY_THRESHOLD (0.7) with the new belief
        - strength > STRENGTH_THRESHOLD (0.7)

        Args:
            new_belief: The text of the proposed new belief.

        Returns:
            ConflictReport with conflict details and recommendation.
        """
        beliefs = load_beliefs()
        if not beliefs:
            return ConflictReport()

        new_lower = new_belief.lower().strip()
        best_match_idx: int | None = None
        best_similarity = 0.0
        best_belief: dict = {}

        for i, b in enumerate(beliefs):
            existing_text = b.get("belief", "").lower().strip()
            if not existing_text:
                continue

            similarity = SequenceMatcher(None, new_lower, existing_text).ratio()
            if similarity > best_similarity:
                best_similarity = similarity
                best_match_idx = i
                best_belief = b

        if (
            best_match_idx is not None
            and best_similarity > SIMILARITY_THRESHOLD
            and best_belief.get("strength", 0) > STRENGTH_THRESHOLD
        ):
            # Determine recommendation based on relationship
            recommendation = self._recommend_resolution(
                new_belief, best_belief.get("belief", ""), best_similarity
            )
            return ConflictReport(
                has_conflict=True,
                conflicting_belief_id=best_match_idx,
                conflicting_belief_text=best_belief.get("belief", ""),
                similarity_score=best_similarity,
                recommendation=recommendation,
            )

        return ConflictReport()

    def _recommend_resolution(
        self, new_text: str, existing_text: str, similarity: float
    ) -> str:
        """Determine resolution recommendation for a conflict.

        Simple heuristic until Phase 2 provides semantic analysis:
        - Very high similarity (>0.9): likely a merge (refinement)
        - High similarity (>0.8): could be supersede or coexist
        - Moderate similarity (>0.7): review needed

        Args:
            new_text: The proposed new belief.
            existing_text: The conflicting existing belief.
            similarity: The similarity score between them.

        Returns:
            One of: "merge", "supersede", "coexist", "review"
        """
        if similarity > 0.9:
            # Very similar — likely a refinement
            if len(new_text) > len(existing_text):
                return "merge"  # New is more specific
            return "supersede"  # Same thing restated
        elif similarity > 0.8:
            return "supersede"
        else:
            return "review"

    def check_stability(self, mutations: list[dict], window_days: int = 7) -> StabilityReport:
        """Check belief mutation rate over a rolling window.

        Args:
            mutations: List of recent BeliefMutation dicts with 'timestamp' fields.
            window_days: Number of days for the rolling window (default 7).

        Returns:
            StabilityReport with drift warning if rate exceeds threshold.
        """
        from datetime import datetime, timedelta

        report = StabilityReport()
        cutoff = datetime.utcnow() - timedelta(days=window_days)

        recent = []
        for m in mutations:
            try:
                ts = datetime.fromisoformat(m.get("timestamp", ""))
                if ts >= cutoff:
                    recent.append(m)
            except (ValueError, TypeError):
                continue

        report.mutations_last_7_days = len(recent)

        if len(recent) > 5:
            report.drift_warning = True
            report.details.append(
                f"High mutation rate: {len(recent)} mutations in {window_days} days "
                f"(threshold: 5). Possible belief drift."
            )

        # Check for oscillation (A→B→A pattern)
        belief_texts = [m.get("belief", "") for m in recent]
        seen: dict[str, int] = {}
        for text in belief_texts:
            normalized = text.lower().strip()
            seen[normalized] = seen.get(normalized, 0) + 1
            if seen[normalized] >= 3:
                report.oscillation_detected = True
                report.details.append(
                    f"Oscillation detected: belief '{text[:60]}...' "
                    f"appeared {seen[normalized]} times in {window_days} days."
                )

        return report
