## ADDED Requirements

### Requirement: TemporalBeliefStore class

The system SHALL implement a `TemporalBeliefStore` class in `triforce/memory/temporal_beliefs.py` backed by Grafeo (embedded Rust graph database) with graceful degradation when Grafeo is not installed.

#### Scenario: TemporalBeliefStore initialization with Grafeo

- **WHEN** `TemporalBeliefStore()` is instantiated AND `grafeo` is importable
- **THEN** an embedded Grafeo database is created at `EPISODIC_DB_PATH` (shared with episodic memory by default)
- **AND** belief edges are stored as `(:Belief)-[:VALID_DURING]->(:TimeWindow)` patterns

#### Scenario: Stub mode without Grafeo

- **WHEN** `grafeo` is not importable
- **THEN** the instance initializes in stub mode and logs a warning
- **AND** `migrate_from_json(dry_run=True)` still works (read-only inspection of the legacy JSON)
- **AND** all write operations raise `NotImplementedError` with a clear install hint

### Requirement: Temporal belief edges

Each belief mutation SHALL be stored as a graph node with a validity window.

#### Scenario: Writing a new belief

- **WHEN** `write_belief(belief, strength, reason, source_episode_id, tags=None)` is called
- **THEN** a new belief node is created with `valid_from=datetime.utcnow()`, `valid_until=None`, plus the supplied fields
- **AND** the new belief's ID is returned

#### Scenario: Superseding an existing belief

- **WHEN** `write_belief(...)` is called with `supersedes_id=<existing_id>`
- **THEN** the prior belief's `valid_until` is set to `datetime.utcnow()`
- **AND** the new belief is written with `valid_from=datetime.utcnow()` and `supersedes_id` set

### Requirement: Current belief query

The system SHALL support `query_current(topic)` returning beliefs where `valid_until IS NULL`.

#### Scenario: Query current beliefs

- **WHEN** `query_current(topic)` is called
- **THEN** it returns all open-validity belief nodes whose content is semantically related to `topic`
- **AND** results are ordered by `strength` descending

### Requirement: Point-in-time belief query

The system SHALL support `query_at(topic, at: datetime)` for historical recall.

#### Scenario: Point-in-time query before supersession

- **GIVEN** a belief was written on 2026-01-10 and superseded on 2026-02-15
- **WHEN** `query_at(topic, at=datetime(2026, 1, 20))` is called
- **THEN** the original belief is returned

#### Scenario: Point-in-time query after supersession

- **GIVEN** the same belief, superseded on 2026-02-15
- **WHEN** `query_at(topic, at=datetime(2026, 3, 1))` is called
- **THEN** only the superseding belief is returned

### Requirement: Belief history lineage

The system SHALL support `get_belief_history(belief_id)` returning the full mutation chain.

#### Scenario: Belief lineage query

- **WHEN** `get_belief_history(belief_id)` is called
- **THEN** it returns the chronological chain from origin through all mutations
- **AND** each step in the chain records who/what triggered the change (`source_episode_id`)

### Requirement: JSON migration

The system SHALL provide a `migrate_from_json(dry_run: bool = True)` method that reads `memory/judge_beliefs.json` and either reports or executes the migration.

#### Scenario: Dry-run reports without modifying

- **WHEN** `migrate_from_json(dry_run=True)` is called and `judge_beliefs.json` exists
- **THEN** it returns a list of dicts describing each belief that would be migrated
- **AND** logs a human-readable summary
- **AND** does not write to the graph

#### Scenario: Live migration imports beliefs

- **WHEN** `migrate_from_json(dry_run=False)` is called AND Grafeo is loaded
- **THEN** each belief in the JSON is imported as a belief node with `valid_from` set to the JSON entry's `created` timestamp and `valid_until=None`
- **AND** the migration is idempotent (re-running does not create duplicates)

### Requirement: ADK tool upgrade for belief writes

The Judge's belief-write path SHALL go through `TemporalBeliefStore.write_belief()` once `[memory]` is installed; until then, the existing `triforce/memory/beliefs.py` flat-JSON path remains the default.

#### Scenario: Belief update with SSGM pre-check

- **WHEN** the Judge proposes a new belief via the `update_beliefs` ADK tool
- **THEN** `SSGMGuard.check_conflict()` is called first
- **AND** if a conflict is detected, the `ConflictReport` is surfaced to the Judge before any write occurs

### Requirement: Point-in-time ADK tool

The system SHALL expose a `query_beliefs_at(topic, at_date)` ADK tool when `TemporalBeliefStore` is available.

#### Scenario: Historical belief query tool

- **WHEN** the Judge or Executor calls `query_beliefs_at(topic, at_date_str)`
- **THEN** it calls `TemporalBeliefStore.query_at(topic, at=parse(at_date_str))`
- **AND** returns formatted results
