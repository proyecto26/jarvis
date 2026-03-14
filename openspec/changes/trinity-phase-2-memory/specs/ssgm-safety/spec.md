## ADDED Requirements

### Requirement: SSGMGuard conflict detection
The system SHALL implement an `SSGMGuard` class in `triforce/memory/ssgm.py` that detects belief conflicts before writes.

#### Scenario: No conflict detected
- **WHEN** `check_conflict(new_belief, existing_beliefs)` is called and no existing belief has cosine similarity > 0.7 with strength > 0.7
- **THEN** `ConflictReport(has_conflict=False)` is returned and the belief write proceeds

#### Scenario: Conflict detected
- **WHEN** a new belief has cosine similarity > 0.7 with an existing belief that has strength > 0.7
- **THEN** `ConflictReport(has_conflict=True, conflicting_belief_id=..., similarity_score=..., recommendation=...)` is returned and the write is paused pending Judge resolution

#### Scenario: ConflictReport model fields
- **WHEN** a `ConflictReport` is returned
- **THEN** it SHALL include: `has_conflict: bool`, `conflicting_belief_id: str | None`, `similarity_score: float | None`, `recommendation: "merge" | "supersede" | "coexist" | "review"`

### Requirement: SSGM wired into belief update flow
The `update_beliefs` ADK tool SHALL run SSGM check before writing to Graphiti.

#### Scenario: Conflict included in tool output
- **WHEN** `check_conflict()` returns `has_conflict=True`
- **THEN** the `update_beliefs` tool output includes the full `ConflictReport` for the Judge to resolve, and the belief is NOT written until resolution is explicit

#### Scenario: Conflict-free belief write proceeds
- **WHEN** `check_conflict()` returns `has_conflict=False`
- **THEN** the belief is written to Graphiti immediately without additional Judge prompt

### Requirement: Stability monitor
The system SHALL track belief mutation rate and emit warnings when drift is detected.

#### Scenario: High mutation rate warning
- **WHEN** more than 5 belief mutations occur in a rolling 7-day window
- **THEN** a warning entry is appended to the current day's journal under a `SystemAlert` section with message "Belief drift detected: N mutations in 7 days"

#### Scenario: Normal mutation rate — no warning
- **WHEN** 5 or fewer belief mutations occur in a rolling 7-day window
- **THEN** no stability warning is emitted
