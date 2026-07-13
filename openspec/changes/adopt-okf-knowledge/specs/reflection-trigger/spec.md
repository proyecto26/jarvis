# Reflection Trigger Spec

## ADDED Requirements

### Requirement: Importance Accumulation on Journal Appends

The journal SHALL accumulate importance at its single append choke point, `journal.append_to_section()`: each `Judgment` append adds its `action_weight` to a running sum, and each `Execution` append adds a flat weight of 1 (no weight field is added to `Execution`). The running sum SHALL be persisted atomically in `journal/.importance-accumulator.json`.

#### Scenario: Judgment weight accumulates

- **WHEN** a `Judgment` with `action_weight: 3` is appended
- **THEN** the persisted accumulator increases by 3

#### Scenario: Execution counts as one

- **WHEN** an `Execution` is appended
- **THEN** the persisted accumulator increases by exactly 1
- **AND** the `Execution` schema is unchanged (no new field)

#### Scenario: Accumulator survives restart

- **WHEN** the process restarts after appends totaling 7
- **THEN** the next append resumes from 7, read from the state file

### Requirement: Threshold Flag for the Temporal Layer

When the running sum crosses `Config.REFLECTION_IMPORTANCE_THRESHOLD` (default ~15), a `reflection_due` flag SHALL be set. The system SHALL expose `check_reflection_due()` and `reset_accumulator()` for the Temporal layer; the trigger raises a flag only — scheduling the reflection remains Temporal's decision, and the existing nightly schedule remains the fallback trigger.

#### Scenario: Crossing the threshold raises the flag

- **WHEN** the accumulator moves from below to at-or-above the threshold
- **THEN** `check_reflection_due()` returns true
- **AND** journal appends continue to succeed normally (the flag never blocks writes)

#### Scenario: Reset clears the flag and the sum

- **WHEN** `reset_accumulator()` is called after a reflection completes
- **THEN** the persisted sum returns to zero
- **AND** `check_reflection_due()` returns false

#### Scenario: Quiet period still reflects on schedule

- **WHEN** the threshold is never crossed during a period
- **THEN** the nightly scheduled reflection path in `triforce/temporal/workflows.py` still runs as today

### Requirement: Reflection Output as OKF Documents

Reflective mode's agent SHALL gain a `write_reflection(...)` tool (alongside the existing `append_to_state`) that persists an OKF `Reflection` document containing bundle-absolute links to the `Decision` documents it evaluates.

#### Scenario: Reflection links its decisions

- **WHEN** the reflective agent calls `write_reflection` over two recent decisions
- **THEN** a `Reflection` document is written to `knowledge/reflections/`
- **AND** its body contains bundle-absolute links to both `Decision` documents

#### Scenario: Existing tool is unaffected

- **WHEN** the reflective agent uses `append_to_state`
- **THEN** its behavior is identical to before this change
