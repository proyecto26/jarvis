# Schema Reference — Human-Readable Pydantic Models

These models are defined in `triforce/memory/schema.py`. This reference mirrors
them in plain language for use by the journal-entry-writer skill.

---

## DreamCycle

Represents a single dream cycle from Sleep mode.

| Field | Type | Default | Description |
|---|---|---|---|
| `timestamp` | string (ISO 8601) | current UTC time | When this dream occurred |
| `seed` | string | `""` | The initial idea or prompt that started the dream |
| `branches` | list of strings | `[]` | Alternative directions explored from the seed |
| `depth_reached` | integer | `0` | How many transformation layers deep (inversions, syntheses) |
| `breakthrough` | string or null | `null` | The breakthrough insight, if one was achieved |

**Rules:**
- `seed` should never be empty when writing a real entry
- `depth_reached` should reflect actual transformation count, not estimated difficulty
- `breakthrough` should only be set if the dream-deepening criteria were ALL met

---

## Judgment

Represents a decision made by the Judge.

| Field | Type | Default | Description |
|---|---|---|---|
| `timestamp` | string (ISO 8601) | current UTC time | When the judgment was made |
| `action` | string | `""` | What action was being evaluated |
| `action_weight` | integer (1-10) | `1` | Weight/severity of the action |
| `verdict` | string | `"approved"` | One of: `approved`, `modified`, `rejected` |
| `reasoning` | string | `""` | Why this verdict was given |
| `original` | string or null | `null` | The original action if it was modified |
| `modified` | string or null | `null` | The modified version of the action |

**Rules:**
- `action` must describe what was evaluated, not just the topic
- `action_weight` must be 1-10 integer; see escalation-handler for matrix
- `verdict` must be exactly one of the three allowed values
- `original` and `modified` must both be set if verdict is `"modified"`
- `reasoning` must reference specific concerns, not vague statements

---

## Execution

Represents an action taken by the Executor.

| Field | Type | Default | Description |
|---|---|---|---|
| `timestamp` | string (ISO 8601) | current UTC time | When the action was executed |
| `action` | string | `""` | What was done |
| `status` | string | `"completed"` | One of: `completed`, `failed`, `partial`, `hard_stop` |
| `outcome` | string | `""` | What actually happened as a result |
| `artifacts` | list of strings | `[]` | File paths, URLs, or identifiers of outputs |

**Rules:**
- `action` should be specific enough to replay the action
- `status` of `hard_stop` means the escalation handler blocked it
- `outcome` should describe observable results, not intentions
- `artifacts` should be real paths/identifiers, not descriptions

---

## Learning

Represents a learning extracted during reflection.

| Field | Type | Required | Description |
|---|---|---|---|
| `content` | string | YES | The specific, actionable learning |
| `source_mode` | string | no (default: `"reflective"`) | Which mode produced this: `awake`, `sleep`, `reflective` |

**Rules:**
- `content` must be specific enough to change future behavior
- Not "error handling is important" but "Stripe 429 includes retry-after header"

---

## BeliefMutation

Represents a change to the Judge's beliefs.

| Field | Type | Default | Description |
|---|---|---|---|
| `timestamp` | string (ISO 8601) | current UTC time | When the mutation occurred |
| `mutation_type` | string | `"updated"` | One of: `new`, `updated`, `superseded`, `merged`, `coexisting` |
| `belief` | string | `""` | The belief statement (must be falsifiable) |
| `strength` | float (0.0-1.0) | `0.5` | Confidence level |
| `reason` | string | `""` | Evidence-linked reason for the mutation |

**Rules:**
- `belief` must be a complete, falsifiable sentence
- `strength` for new beliefs: 0.3-0.5; only reaches 0.9+ after multiple confirmations
- `reason` must reference specific evidence, not "it seems right"

---

## JournalMetadata

Metadata for a daily journal entry.

| Field | Type | Default | Description |
|---|---|---|---|
| `date` | string (YYYY-MM-DD) | required | The date of this journal entry |
| `mode_cycles` | dict | `{}` | Count of cycles per mode, e.g. `{"awake": 5, "sleep": 1}` |
| `active_skills` | list of strings | `[]` | Skills that were activated during this day |
| `dominant_theme` | string | `""` | The overall theme of the day's activity |

---

## JournalEntry

A complete daily journal entry combining all sections.

| Field | Type | Default | Description |
|---|---|---|---|
| `metadata` | JournalMetadata | required | Day-level metadata |
| `dreams` | list of DreamCycle | `[]` | Dream cycle records |
| `judgments` | list of Judgment | `[]` | Judge decision records |
| `executions` | list of Execution | `[]` | Executor action records |
| `learnings` | list of Learning | `[]` | Extracted learnings |
| `belief_mutations` | list of BeliefMutation | `[]` | Belief changes |
| `open_questions` | list of strings | `[]` | Unanswered questions for future investigation |
| `connections` | list of strings | `[]` | Connections to past entries or dream seeds |
