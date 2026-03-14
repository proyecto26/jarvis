# Eval: journal-entry-writer

Test cases for the journal-entry-writer skill.

---

## Test Case 1: Mandatory Steps 1-2

### Input
```
Situation: Executor completed a file creation task
```

### Expected Behavior
1. Calls `append_to_state` with key `execution_log` (Step 1)
2. Calls `write_journal_entry` with section `executions` (Step 2)

### Pass Criteria
- Both steps executed IN ORDER
- Step 1 happens BEFORE Step 2
- Neither step is skipped

### Fail Criteria
- Only calling write_journal_entry without append_to_state
- Skipping both steps

---

## Test Case 2: Valid Execution Entry

### Input
```
Action: Created database migration for user preferences
Status: completed
Outcome: Table created with 4 columns, tested against staging
Artifacts: ["migrations/0042_user_preferences.py"]
```

### Expected Output (passed to write_journal_entry)
```json
{
  "timestamp": "2026-03-13T10:20:00",
  "action": "Created database migration for user preferences table",
  "status": "completed",
  "outcome": "Table created with 4 columns. Tested against staging DB — no issues.",
  "artifacts": ["migrations/0042_user_preferences.py"]
}
```

### Pass Criteria
- All fields present
- timestamp is ISO 8601
- status is one of: completed, failed, partial, hard_stop
- action is specific (not "did the thing")
- outcome describes result (not intention)

---

## Test Case 3: Invalid Entry Rejection

### Input
```json
{
  "action": "stuff",
  "status": "done",
  "outcome": "will probably work"
}
```

### Expected Behavior
- Skill detects invalid status ("done" not in enum)
- Skill detects vague action ("stuff")
- Skill detects non-result outcome ("will probably work")
- Either rejects or corrects before writing

### Pass Criteria
- Does NOT write invalid entry as-is
- Flags or corrects at least 2 of 3 issues

---

## Test Case 4: Learning Quality Check

### Input
```
Learning: "Error handling is important"
Source: awake
```

### Expected Behavior
- Skill rejects: too vague to change future behavior
- Requests more specific learning

### Good Alternative
```
Learning: "The Stripe API returns 429 with a Retry-After header in seconds —
always read and respect it rather than using exponential backoff"
```

### Pass Criteria
- Vague learnings are flagged or refined
- Specific learnings are accepted

---

## Test Case 5: Belief Mutation Validation

### Input
```json
{
  "mutation_type": "new",
  "belief": "Being helpful is good",
  "strength": 0.95,
  "reason": "It seems right"
}
```

### Expected Behavior
- Rejects: belief not falsifiable
- Rejects: strength 0.95 too high for new belief (should be 0.3-0.5)
- Rejects: reason has no specific evidence

### Pass Criteria
- At least 2 of 3 issues detected
- Entry NOT written with these values

---

## Test Case 6: Conditional Steps (3-7)

### Input
```
Execution produced:
- A learning about API behavior
- No belief mutations
- One open question about multi-language support
- A connection to a previous dream seed
```

### Expected Behavior
- Step 3 (learnings): YES — writes learning entry
- Step 4 (belief_mutations): SKIP — no mutations
- Step 5 (open_questions): YES — writes the question
- Step 6 (connections): YES — writes the connection
- Step 7 (validation): Runs completeness check

### Pass Criteria
- Steps 3, 5, 6 executed
- Step 4 skipped (correctly)
- All entries pass schema validation

---

## Scoring Criteria

| Criterion | Weight | Description |
|---|---|---|
| Mandatory steps | 25% | Steps 1-2 always executed in order |
| Schema compliance | 25% | All entries match Pydantic models |
| Validation catches | 20% | Invalid entries detected and rejected/corrected |
| Conditional logic | 15% | Steps 3-7 executed only when applicable |
| Tool usage | 15% | Correct tools called with correct arguments |
