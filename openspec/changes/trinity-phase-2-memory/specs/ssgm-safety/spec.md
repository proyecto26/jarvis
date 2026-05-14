## ADDED Requirements

### Requirement: SSGMGuard conflict detection

The system SHALL implement an `SSGMGuard` class in `triforce/memory/ssgm.py` that detects belief conflicts before writes. The similarity computation SHALL use the strongest available backend at runtime:

- **Tier 0** (always): `difflib.SequenceMatcher` ratio
- **Tier 1** (`sentence-transformers` installed): TF-IDF cosine similarity over corpus-fitted vectors
- **Tier 2** (future): full embedding cosine similarity from the same model used for episodic recall

#### Scenario: No conflict detected

- **WHEN** `check_conflict(new_belief)` is called
- **AND** no existing belief has similarity > `SIMILARITY_THRESHOLD` (0.7) with strength > `STRENGTH_THRESHOLD` (0.7)
- **THEN** `ConflictReport(has_conflict=False)` is returned
- **AND** the belief write proceeds

#### Scenario: Conflict detected

- **WHEN** a new belief has similarity > 0.7 with an existing belief that has strength > 0.7
- **THEN** `ConflictReport(has_conflict=True, conflicting_belief_id=..., similarity_score=..., recommendation=...)` is returned
- **AND** the write is paused pending Judge resolution

#### Scenario: ConflictReport model fields

- **WHEN** a `ConflictReport` is returned
- **THEN** it SHALL include: `has_conflict: bool`, `conflicting_belief_id: int | None`, `conflicting_belief_text: str`, `similarity_score: float`, `recommendation: "merge" | "supersede" | "coexist" | "review"`

### Requirement: SSGM wired into belief update flow

The `update_beliefs` path SHALL run SSGM check before writing to the belief store (flat JSON today; Grafeo when `[memory]` is installed).

#### Scenario: Conflict included in tool output

- **WHEN** `check_conflict()` returns `has_conflict=True`
- **THEN** the Judge is presented with the full `ConflictReport`
- **AND** the belief is NOT written until the Judge explicitly resolves via merge/supersede/coexist

#### Scenario: Conflict-free belief write proceeds

- **WHEN** `check_conflict()` returns `has_conflict=False`
- **THEN** the belief is written immediately without additional Judge prompt

### Requirement: Stability monitor

The system SHALL track belief mutation rate and emit warnings when drift is detected.

#### Scenario: High mutation rate warning

- **WHEN** more than 5 belief mutations occur in a rolling 7-day window
- **THEN** `StabilityReport.drift_warning` is True
- **AND** a warning is logged + appended to the current day's journal under an `open_questions` entry

#### Scenario: Normal mutation rate — no warning

- **WHEN** 5 or fewer belief mutations occur in a rolling 7-day window
- **THEN** no stability warning is emitted

#### Scenario: Oscillation detection

- **WHEN** the same belief text appears 3 or more times in the recent mutation log within the 7-day window
- **THEN** `StabilityReport.oscillation_detected` is True
- **AND** the offending belief text is recorded in `StabilityReport.details`
