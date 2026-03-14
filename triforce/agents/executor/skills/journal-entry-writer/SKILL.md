---
name: journal-entry-writer
description: >
  Schema-aware workflow for writing structured journal entries. Ensures all entries
  conform to the Pydantic models in memory/schema.py. Use when the Executor needs
  to record an action, outcome, learning, or any other journal section. Activates
  after task execution, belief changes, or reflective processes.
compatibility:
  - google-adk
metadata:
  scope: executor
  triggers:
    - after executing an approved action
    - after receiving Judge verdict
    - after dream cycle completes
    - during reflective mode
    - when learnings or connections are identified
  requires_tools:
    - append_to_state
    - write_journal_entry
---

# Journal Entry Writer

You are activating the **Journal Entry Writer** skill. This ensures all journal entries
are structured, schema-compliant, and complete.

## Required Workflow

**Steps 1-2 are ALWAYS mandatory. Steps 3-7 are conditional.**

### Step 1: Record in State (ALWAYS)

Use `append_to_state` to record the action/event in session state before writing
to the journal. This ensures the state is available for other agents in the same session.

Key mappings:
- Action executed → key `execution_log`
- Judge verdict received → key `judge_verdict`
- Dream cycle completed → key `dream_output`
- Learning identified → key `learnings`

### Step 2: Write Journal Entry (ALWAYS)

Use `write_journal_entry` tool with the appropriate section and structured content.

**Available sections:** `dreams`, `judgments`, `executions`, `learnings`,
`belief_mutations`, `open_questions`, `connections`

### Step 3: Record Learnings (if applicable)

If the execution produced a learning — something that changes how Jarvis should
approach similar situations in the future — record it.

```json
{
  "content": "<specific, actionable learning>",
  "source_mode": "awake|sleep|reflective"
}
```

**Quality rule:** A learning must be specific enough to change future behavior.
- Bad: "Error handling is important"
- Good: "The Stripe API returns 429 with retry-after header — always check it before retrying"

### Step 4: Record Belief Mutations (if applicable)

If the Judge issued a belief mutation during this cycle, record it in the journal.

```json
{
  "timestamp": "<ISO 8601>",
  "mutation_type": "new|updated|superseded|merged|coexisting",
  "belief": "<the belief statement>",
  "strength": 0.5,
  "reason": "<evidence-linked reason>"
}
```

### Step 5: Record Open Questions (if applicable)

If the interaction raised questions that weren't answered, record them for future
investigation.

Format: Plain text strings. Each question should be specific and investigable.
- Bad: "How does memory work?"
- Good: "Does Mem0's hybrid retrieval handle multi-language content for J.D.'s Spanish/English mix?"

### Step 6: Record Connections (if applicable)

If this interaction connects to previous entries, past decisions, or dream seeds,
record the connection.

Format: Plain text strings describing the connection.
- "This error pattern is the same one from 2026-03-10 — the retry logic fix applies here too"
- "The Dreamer's [INVERTED] seed about self-indexing memory is exactly what we implemented today"

### Step 7: Validate Completeness

Before finishing, verify:
- [ ] Section name is valid (one of the 7 allowed sections)
- [ ] Content matches the JSON schema for structured sections
- [ ] Timestamps are ISO 8601 format
- [ ] No empty required fields
- [ ] Learnings are specific and actionable (if present)
- [ ] Belief mutations have all required fields (if present)

## JSON Schemas by Section

### dreams (DreamCycle)
```json
{
  "timestamp": "2026-03-13T10:00:00",
  "seed": "the initial dream seed",
  "branches": ["branch 1", "branch 2"],
  "depth_reached": 3,
  "breakthrough": "the breakthrough insight or null"
}
```

### judgments (Judgment)
```json
{
  "timestamp": "2026-03-13T10:00:00",
  "action": "what was being judged",
  "action_weight": 5,
  "verdict": "approved|modified|rejected",
  "reasoning": "why this verdict",
  "original": "original action if modified",
  "modified": "modified action if applicable"
}
```

### executions (Execution)
```json
{
  "timestamp": "2026-03-13T10:00:00",
  "action": "what was executed",
  "status": "completed|failed|partial",
  "outcome": "what happened",
  "artifacts": ["file.py", "output.log"]
}
```

### learnings (Learning)
```json
{
  "content": "specific actionable learning",
  "source_mode": "awake|sleep|reflective"
}
```

### belief_mutations (BeliefMutation)
```json
{
  "timestamp": "2026-03-13T10:00:00",
  "mutation_type": "new|updated|superseded|merged|coexisting",
  "belief": "the belief statement",
  "strength": 0.5,
  "reason": "evidence-linked reason"
}
```

### open_questions
Plain text strings: `"The specific question to investigate"`

### connections
Plain text strings: `"Description of the connection to past experience"`

## See Also

- `references/schema-reference.md` — Pydantic models in human-readable format
- `references/entry-examples.json` — valid and invalid examples with annotations
