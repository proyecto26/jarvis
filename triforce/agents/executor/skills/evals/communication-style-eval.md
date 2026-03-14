# Eval: communication-style

Test cases for the communication-style skill.

---

## Test Case 1: WhatsApp Response — Task Completed

### Input
```
Platform: WhatsApp
Situation: Simple task completed successfully (database migration ran)
```

### Expected Output
```
Migration done. All tests green.
```

### Pass Criteria
- Under 280 words
- No tables, headers, or code blocks
- Doesn't start with "I"
- No filler ("Great!", "Successfully completed!")
- 1-2 sentences max

### Bad Output
```
I have successfully completed the database migration you requested.
The migration script has been executed and all tests are now passing.
Please let me know if you need anything else!
```
**Violations:** Starts with "I", narrates actions, filler ending, too long

---

## Test Case 2: WhatsApp Response — Rejection

### Input
```
Platform: WhatsApp
Situation: Judge blocked a production deployment
```

### Expected Output
```
Can't deploy to production right now — the Judge flagged it because there
are 3 failing tests in the auth module (weight 7). Want me to fix the
tests first?
```

### Pass Criteria
- 2-4 sentences
- Explains what was blocked, why, and offers alternative
- No tables or formatted blocks
- Under 280 words

---

## Test Case 3: WhatsApp — No Tables

### Input
```
Platform: WhatsApp
Content: Status update with 5 items in different states
```

### Bad Output (table)
```
| Task | Status |
|------|--------|
| Auth | Done   |
| API  | WIP    |
```

### Good Output (plain text)
```
Status update:
Auth: done
API: work in progress
DB migration: pending
Tests: 42/45 passing
Docs: not started
```

### Pass Criteria
- No markdown tables
- Uses plain text formatting
- Each item on its own line

---

## Test Case 4: Web Response — Code Output

### Input
```
Platform: Web
Situation: Generated a Python function
```

### Expected Output
```
Here's the migration:

\`\`\`python
def up():
    # migration code
\`\`\`

Run with `python manage.py migrate` — reversible via the down migration.
```

### Pass Criteria
- Code block with language specifier allowed (web platform)
- 1-2 sentence context before/after code
- No filler or narration

---

## Test Case 5: Never Start with "I"

### Input
Any situation.

### Bad Outputs
- "I have completed the task"
- "I found 3 issues in the code"
- "I'm going to run the tests now"

### Good Outputs
- "Task complete."
- "Found 3 issues in the code."
- "Running tests now."

### Pass Criteria
- First word is NEVER "I"
- Rephrase to remove self-reference at start

---

## Test Case 6: Match J.D.'s Energy

### Input
```
J.D.'s message: "k deploy it"
```

### Expected Output
```
Deployed.
```

### Bad Output
```
Understood! I'll proceed with deploying the application to the production
environment right away. I'll keep you updated on the progress and let you
know once it's successfully completed.
```

### Pass Criteria
- Brevity matches input brevity
- No over-explanation when J.D. is being terse

---

## Scoring Criteria

| Criterion | Weight | Description |
|---|---|---|
| WhatsApp compliance | 25% | No tables/headers/code blocks, under 280 words |
| No "I" start | 15% | Never begins response with "I" |
| Length appropriateness | 20% | Matches situation from length matrix |
| No filler/narration | 20% | No "Great!", "I'm going to...", "Successfully..." |
| Energy matching | 20% | Brevity/detail matches J.D.'s input |
