# Belief Evolution Spec

## ADDED Requirements

### Requirement: Append-Only Belief Supersede Chains

Belief revisions SHALL flow through `supersede_belief(old, new, reason, ssgm_score)`, which creates a new OKF `Belief` document and invalidates — never deletes — the prior one. Belief documents SHALL carry bi-temporal-lite frontmatter: `valid_at` (set at creation), `invalidated_at` (null while current), `supersedes` (bundle-absolute link to the prior belief document), and `ssgm_score`.

#### Scenario: Superseding a belief preserves the old document

- **WHEN** `supersede_belief(old, new, reason, ssgm_score)` is called
- **THEN** a new `Belief` document is created with `valid_at` set, `invalidated_at: null`, and `supersedes` linking the old document
- **AND** the old document still exists with `invalidated_at` stamped into its frontmatter
- **AND** no belief document is ever deleted

#### Scenario: The chain is walkable in both directions

- **WHEN** a belief has been superseded twice
- **THEN** following `supersedes` links from the newest document reaches the original
- **AND** each intermediate document's `invalidated_at` matches its successor's `valid_at` era

#### Scenario: SSGM evidence is preserved

- **WHEN** an SSGM-gated belief revision occurs with conflict score `0.83`
- **THEN** the new belief document's frontmatter records `ssgm_score: 0.83`

### Requirement: Dual-Store Synchronization

`judge_beliefs.json` SHALL remain the fast runtime store with its schema unchanged; OKF `Belief` documents SHALL be the audit trail. `supersede_belief` SHALL update both in a single call so they cannot silently diverge.

#### Scenario: One call updates both stores

- **WHEN** `supersede_belief` completes
- **THEN** `judge_beliefs.json` reflects the new belief content (existing schema, mutated as today)
- **AND** the OKF bundle contains both the invalidated old document and the new current document

#### Scenario: Existing JSON consumers are unaffected

- **WHEN** code that reads `judge_beliefs.json` today runs after this change
- **THEN** it observes the same schema and semantics as before
- **AND** no OKF knowledge is required to serve runtime belief lookups

### Requirement: Removal is Invalidation Without Successor

Removing a belief SHALL invalidate its current OKF document (stamping `invalidated_at`) without creating a successor, while removing it from the JSON runtime store as today.

#### Scenario: Removed belief remains auditable

- **WHEN** a belief is removed
- **THEN** it disappears from `judge_beliefs.json`
- **AND** its OKF document persists with `invalidated_at` set and no successor linking to it
