## ADDED Requirements

### Requirement: TemporalBeliefStore class
The system SHALL implement a `TemporalBeliefStore` class in `triforce/memory/temporal_beliefs.py` backed by Graphiti with KuzuDB as the embedded graph database.

#### Scenario: TemporalBeliefStore initialization
- **WHEN** `TemporalBeliefStore()` is instantiated
- **THEN** it creates a Graphiti client with KuzuDB persisted to `KUZU_PATH`

### Requirement: Temporal belief edges
Each belief mutation SHALL be stored as a graph edge with validity window metadata.

#### Scenario: Writing a new belief
- **WHEN** `write_belief(belief: BeliefMutation)` is called
- **THEN** a new `BeliefEdge` is created in KuzuDB with: `valid_from=datetime.now()`, `valid_until=None`, and all fields from `BeliefMutation` (`content`, `strength`, `reasoning`, `tags`, `source_episode_id`)

#### Scenario: Superseding an existing belief
- **WHEN** `write_belief()` is called for a belief that supersedes a prior one (`supersedes_id` set)
- **THEN** the prior belief's `valid_until` is set to `datetime.now()` AND the new belief is written with `valid_from=datetime.now()`

#### Scenario: BeliefEdge model fields
- **WHEN** a `BeliefEdge` is returned by any query
- **THEN** it SHALL contain: `id`, `content`, `strength`, `valid_from`, `valid_until`, `supersedes_id`, `source_episode_id`, `reasoning`, `tags`

### Requirement: Current belief query
The system SHALL support querying the currently valid beliefs for a topic.

#### Scenario: Query current beliefs
- **WHEN** `query_current(topic)` is called
- **THEN** it returns all beliefs where `valid_until IS NULL` and content is semantically similar to `topic`, ordered by `strength` descending

### Requirement: Point-in-time belief query
The system SHALL support querying what beliefs were valid at a specific past datetime.

#### Scenario: Point-in-time query before supersession
- **GIVEN** a belief was written on 2026-01-10 and superseded on 2026-02-15
- **WHEN** `query_at(topic, at=datetime(2026, 1, 20))` is called
- **THEN** the original belief is returned (it was valid at that date)

#### Scenario: Point-in-time query after supersession
- **GIVEN** the same belief, superseded on 2026-02-15
- **WHEN** `query_at(topic, at=datetime(2026, 3, 1))` is called
- **THEN** the superseding belief is returned (the old one is expired)

### Requirement: Belief history lineage
The system SHALL support retrieving the full mutation history of a belief.

#### Scenario: Belief lineage query
- **WHEN** `get_belief_history(belief_id)` is called
- **THEN** it returns the complete chain: original belief → all subsequent mutations → current state, in chronological order

### Requirement: JSON migration
The system SHALL provide a one-time migration from `memory/judge_beliefs.json` to KuzuDB.

#### Scenario: Migration preserves existing beliefs
- **WHEN** `migrate_from_json()` is called with `judge_beliefs.json` present
- **THEN** each belief in the JSON is imported as a `BeliefEdge` with `valid_from` set to the JSON file's modification date and `valid_until=None`

#### Scenario: Migration is idempotent
- **WHEN** `migrate_from_json()` is called a second time
- **THEN** no duplicate entries are created (check by `id` or content hash before inserting)

### Requirement: ADK tool upgrade
The `update_beliefs` ADK tool SHALL write to `TemporalBeliefStore` instead of mutating `judge_beliefs.json`.

#### Scenario: Belief update creates temporal edge
- **WHEN** the Judge calls `update_beliefs(belief_content, strength, reasoning)`
- **THEN** a new temporal edge is written to KuzuDB via `write_belief()`, passing through SSGM check first

### Requirement: Point-in-time ADK tool
The system SHALL add a `query_beliefs_at` ADK tool.

#### Scenario: Historical belief query tool
- **WHEN** the Judge or Executor calls `query_beliefs_at(topic, at_date_str)`
- **THEN** it calls `TemporalBeliefStore.query_at(topic, at=parse(at_date_str))` and returns formatted results
