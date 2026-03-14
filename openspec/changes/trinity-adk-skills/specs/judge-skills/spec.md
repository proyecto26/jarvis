## ADDED Requirements

### Requirement: ethics-evaluation skill (filter mode)
The Judge filter agent SHALL have an `ethics-evaluation` skill that provides a systematic, auditable evaluation rubric for assessing proposed actions.

#### Scenario: Skill activates in filter mode
- **WHEN** `judge_filter` receives a request to evaluate an action
- **THEN** it activates `ethics-evaluation` and evaluates the action across all four dimensions

#### Scenario: Four-dimension evaluation
- **WHEN** `ethics-evaluation` runs
- **THEN** the Judge evaluates: (1) harm — direct, indirect, and systemic; (2) alignment — with stated objectives and values; (3) reversibility — scored 1-5 with documented anchors; (4) action weight — derived from the first three dimensions

#### Scenario: Auditable rubric output
- **WHEN** evaluation completes
- **THEN** the Judge outputs a structured verdict with each dimension scored explicitly (not just a verdict string) and stores it via `append_to_state` to `judge_reasoning`

#### Scenario: Hard stop identification
- **WHEN** `ethics-evaluation` runs and the action matches a hard-stop category
- **THEN** `action_weight` is set to 10 automatically and verdict is `rejected` without further deliberation — hard stops are listed in `references/ethics-rubric.md` and include: actions that modify Jarvis's own architecture without human review, irreversible external commitments, and actions that deceive J.D.

### Requirement: belief-mutation skill (filter + collaborator)
Both `judge_filter` and `judge_collaborator` SHALL have a `belief-mutation` skill that provides an SSGM-aware protocol for safely updating the Judge's beliefs.

#### Scenario: Pre-write conflict check
- **WHEN** the Judge proposes to mutate a belief
- **THEN** it first checks: does the new belief have semantic similarity >0.7 with an existing belief of strength >0.7? If yes, pause and apply conflict resolution before writing.

#### Scenario: Conflict resolution decision tree
- **WHEN** a conflict is detected
- **THEN** the Judge applies the decision tree from `references/ssgm-protocol.md`: merge (beliefs are compatible), supersede (new belief replaces old, mark valid_until), coexist (beliefs are orthogonal despite surface similarity), or review (flag for J.D. input)

#### Scenario: Required mutation fields
- **WHEN** `belief-mutation` writes a belief
- **THEN** it always includes: `belief` (present tense declarative), `strength` (0.0-1.0), `reason` (what triggered this change), `source_event` (which interaction or journal entry prompted it)

#### Scenario: Stability monitor
- **WHEN** `belief-mutation` runs
- **THEN** it checks whether >5 mutations occurred in the rolling 7-day window; if yes, it appends a drift warning to `judge_reasoning` before writing

#### Scenario: When NOT to mutate
- **WHEN** an interaction merely confirms an existing belief
- **THEN** the Judge bumps `strength` by a small increment (reinforcement) instead of creating a new mutation entry — "reinforced" is not the same as "mutated"

### Requirement: dream-deepening skill (collaborator mode)
The `judge_collaborator` agent SHALL have a `dream-deepening` skill that provides a structured method for connecting Dreamer seeds to past experience and detecting genuine breakthroughs.

#### Scenario: Seed lineage tracing
- **WHEN** `dream-deepening` activates
- **THEN** the Judge reads `[INVERTED]` and `[SYNTHESIS: X→Y]` tags in `dream_seeds` to understand each seed's origin before attempting to deepen it

#### Scenario: Connecting to past experience
- **WHEN** deepening seeds
- **THEN** the Judge calls `recall_similar_decisions` to find relevant past decisions or experiences, then adds connections to `dream_deepening` state via `append_to_state`

#### Scenario: Breakthrough detection criteria
- **WHEN** evaluating whether to call `exit_loop`
- **THEN** the Judge applies the strict criteria: a breakthrough is a REFRAME — when something seen before suddenly looks structurally different, NOT merely a good idea or useful insight. Requires `dream_depth >= 3`.

#### Scenario: exit_loop with breakthrough stored
- **WHEN** a genuine breakthrough is detected and `dream_depth >= 3`
- **THEN** the Judge: (1) stores the insight to `breakthrough` state key via `append_to_state`, (2) calls `exit_loop`. Never calls `exit_loop` without first storing the breakthrough.

#### Scenario: Patience requirement
- **WHEN** no breakthrough is detected
- **THEN** the Judge allows the loop to continue — it does NOT call `exit_loop` just because an idea is good or the dream has gone deep enough. Only reframes trigger exit.
