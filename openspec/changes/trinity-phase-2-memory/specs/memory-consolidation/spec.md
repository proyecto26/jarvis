## ADDED Requirements

### Requirement: ConsolidationWorker class
The system SHALL implement a `ConsolidationWorker` class in `triforce/memory/consolidation.py` with a `run_nightly()` entry point.

#### Scenario: run_nightly() sequence
- **WHEN** `run_nightly()` is called
- **THEN** it executes in order: (1) `run_fade_decay()`, (2) `compress_old_episodes()`, (3) `run_ssgm_audit()`, (4) `consolidate_journal_tier()`

### Requirement: FadeMem decay
The system SHALL apply the Ebbinghaus forgetting curve to Mem0 episodic entries.

#### Scenario: Strength decay calculation
- **WHEN** `run_fade_decay()` runs
- **THEN** for each Mem0 entry, strength is updated as: `strength × e^(−0.02 × days_since_last_access)`

#### Scenario: Entry removal below threshold
- **WHEN** an episodic entry's computed strength drops below 0.05
- **THEN** it is removed from the Mem0 index (but the source `.md` journal file is NOT deleted)

#### Scenario: Reinforced entries preserve strength
- **WHEN** `reinforce(entry_id)` was called within the current day
- **THEN** `run_fade_decay()` resets that entry's strength to 1.0 (decay clock restart) instead of applying decay

### Requirement: Episode compression
The system SHALL compress journal episodes older than 30 days into learning summaries.

#### Scenario: Compression of old judgments
- **WHEN** `compress_old_episodes(threshold_days=30)` runs
- **THEN** all Judgment entries older than 30 days are grouped by week and compressed via LLM into a single `LearningEntry` per week
- **AND** the compressed entry replaces the originals in the Mem0 index
- **AND** the original `.md` journal files are unchanged

#### Scenario: High cognitive-load entries preserved verbatim
- **WHEN** a `JournalEntry` has `cognitive_load_score >= 0.8`
- **THEN** it is NOT compressed regardless of age — kept verbatim in the Mem0 index

### Requirement: SSGM nightly audit
The system SHALL run a nightly audit of recent belief mutations for conflicts.

#### Scenario: Nightly belief audit
- **WHEN** `run_ssgm_audit()` runs
- **THEN** it checks all beliefs written in the last 24h against the full belief graph for conflicts
- **AND** appends a `SystemAudit` section to the current day's journal with: total mutations, conflicts detected, flagged belief IDs

### Requirement: TiMem-style tier consolidation
The system SHALL produce weekly episode summaries from daily raw entries.

#### Scenario: Weekly tier consolidation
- **WHEN** `consolidate_journal_tier(date_range)` runs for a completed week
- **THEN** it uses an LLM to summarize the week's Dream, Judgment, and Execution entries into a single weekly summary `JournalEntry`
- **AND** writes the weekly summary as a new file: `journal/YYYY-Www-summary.md`

### Requirement: Callable from Temporal
The `run_nightly()` method SHALL be directly callable as a Temporal Activity (for `ConsolidationWorkflow`).

#### Scenario: Temporal activity wrapping
- **WHEN** `run_consolidation_activity` (a Temporal Activity) is invoked
- **THEN** it calls `ConsolidationWorker().run_nightly()` with periodic heartbeats every 30s
