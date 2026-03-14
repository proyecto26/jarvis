## ADDED Requirements

### Requirement: DreamWorkflow scheduled execution
The system SHALL implement `DreamWorkflow` as a Temporal Workflow that runs the Dreamer's background cycles without user prompting.

#### Scenario: Workflow triggered by Temporal Schedule
- **WHEN** the configured `DREAM_INTERVAL_HOURS` interval elapses (default: 6 hours)
- **THEN** Temporal Schedule fires a new `DreamWorkflow` run automatically

#### Scenario: Dream context seeding
- **WHEN** `DreamWorkflow` starts
- **THEN** it calls `seed_dream_context_activity` to retrieve the top-5 relevant episodic memories from Mem0 as `dream_seeds`

#### Scenario: Dreamer LLM call as durable activity
- **WHEN** the dream loop runs a Dreamer iteration
- **THEN** it calls `generate_content` Activity with the Dreamer system prompt and `DREAMER_MODEL` (high-reasoning model)
- **AND** `dream_seeds` and prior iterations are included in the `contents`

#### Scenario: Judge-as-collaborator LLM call
- **WHEN** the Dreamer returns output
- **THEN** `DreamWorkflow` calls `generate_content` Activity with the Judge collaborator prompt (not the filter prompt) to evaluate for breakthrough

#### Scenario: Breakthrough detection
- **WHEN** the Judge collaborator response contains `"breakthrough": true` in its structured output
- **THEN** the dream loop exits early (before `max_iterations`)

#### Scenario: Max iterations safety bound
- **WHEN** 8 dream iterations complete without a breakthrough
- **THEN** the loop exits with the best idea generated so far

#### Scenario: Dream output written to journal
- **WHEN** the dream loop exits (breakthrough or max iterations)
- **THEN** `write_journal_entry_activity` is called with a `DreamCycle` section containing all ideas generated, the breakthrough (if any), and the number of iterations
- **AND** the entry is indexed to Mem0 as part of the activity

#### Scenario: No duplicate concurrent runs
- **WHEN** a `DreamWorkflow` is already running at schedule trigger time
- **THEN** Temporal skips the new run (SKIP overlap policy)

### Requirement: Dream schedule configuration
The system SHALL create a Temporal Schedule for `DreamWorkflow` via `create_dream_schedule()`.

#### Scenario: Schedule creation
- **WHEN** `python -m triforce.temporal.schedules` is run
- **THEN** a Temporal Schedule is created with `every=timedelta(hours=DREAM_INTERVAL_HOURS)` if it doesn't already exist

#### Scenario: Schedule is idempotent
- **WHEN** `create_dream_schedule()` is called and the schedule already exists
- **THEN** no error is raised and no duplicate schedule is created
