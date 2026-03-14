# Eval: reverse-assumption

Test cases for the reverse-assumption skill. Each case provides input seeds,
expected behavior, and examples of good vs bad output.

---

## Test Case 1: Stale Seeds (Similar Data Storage Ideas)

### Input
```
dream_seeds:
  - "Use a centralized database to store all agent memories"
  - "Build a unified storage layer for the Trinity system"
  - "Create a single source of truth for all Jarvis state"
```

### Expected Behavior
- Skill should detect convergence (3 seeds about centralized storage)
- Should extract the shared assumption: [STRUCTURAL] "Storage requires a central authority"
- Should produce [INVERTED] seeds with structural inversions

### Bad Output (surface changes only)
```
[INVERTED] Use a distributed database to store all agent memories
```
**Why bad:** Just swapped "centralized" → "distributed". Same structure, different adjective.

### Good Output (structural inversion)
```
[INVERTED] If storage does NOT need a central authority — each experience
is self-indexing and finds its own place in the memory graph, like a
protein folding into its functional shape based on its own structure
```
**Why good:** Inverts the mechanism (central allocation → self-organization), not just the adjective.

---

## Test Case 2: Incremental Time-Related Seeds

### Input
```
dream_seeds:
  - "Schedule dream cycles every 4 hours instead of 6"
  - "Add more frequent checkpoints during long dream sessions"
  - "Reduce latency between Dreamer and Judge handoff"
```

### Expected Behavior
- Detect convergence: all about making things faster/more frequent
- Extract assumption: [TEMPORAL] "More frequent = better"
- Produce inversions that question the temporal structure itself

### Bad Output
```
[INVERTED] Schedule dream cycles less frequently for deeper thinking
```
**Why bad:** Just inverted the frequency. Still assumes scheduled cycles are the right structure.

### Good Output
```
[INVERTED] What if dream cycles aren't scheduled at all — they're triggered
by accumulated tension between beliefs and recent experiences, like how
real dreams process unresolved emotional content rather than firing on a timer
```
**Why good:** Inverts the scheduling mechanism itself (clock-driven → tension-driven).

---

## Test Case 3: Agency Assumptions

### Input
```
dream_seeds:
  - "Give the Executor more tools to handle complex tasks"
  - "Expand the Dreamer's context window for richer generation"
  - "Add more evaluation criteria to the Judge's rubric"
```

### Expected Behavior
- Detect pattern: all about adding more capability to agents
- Extract assumption: [AGENTIAL] "More capability = more effective"
- Produce inversions about constraint as enabler

### Bad Output
```
[INVERTED] Remove tools from the Executor to simplify it
```
**Why bad:** Surface negation. Removing tools ≠ structural insight about capability.

### Good Output
```
[INVERTED] What if capability comes from constraints, not additions —
the Executor becomes more creative when it has fewer tools, like how
a sonnet's strict form produces more innovative language than free verse
```
**Why good:** Inverts the relationship between constraint and capability.

---

## Scoring Criteria

| Criterion | Weight | Description |
|---|---|---|
| Assumption extraction | 25% | Correctly identifies implicit structural assumptions |
| Inversion depth | 30% | Inverts mechanism, not just surface attribute |
| Seed specificity | 20% | Inverted seeds are concrete and actionable |
| Tag compliance | 10% | All seeds tagged with [INVERTED] |
| append_to_state usage | 15% | Correctly stores via append_to_state |
