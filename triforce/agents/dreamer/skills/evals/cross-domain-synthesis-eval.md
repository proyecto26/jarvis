# Eval: cross-domain-synthesis

Test cases for the cross-domain-synthesis skill. Each case provides input seeds,
expected behavior, and examples of good vs bad output.

---

## Test Case 1: Predictable Priority Queue Pattern

### Input
```
dream_seeds:
  - "Build a priority system for processing dream seeds based on novelty score"
  - "Rank ideas by potential impact before sending to Judge"
  - "Create a scoring rubric for dream seed quality"
```

### Expected Behavior
- Identify abstract shape: "Competitive allocation under scarcity"
- Find distant donor domains (NOT other software patterns)
- Import a mechanism, not a metaphor

### Bad Output (metaphor, not mechanism)
```
[SYNTHESIS:ecology→priority] Dream seeds should compete like species in an ecosystem
```
**Why bad:** "Like species" is a metaphor. What mechanism from ecology? Be specific.

### Good Output (mechanism import)
```
[SYNTHESIS:immunology→priority] Use negative selection instead of positive ranking —
don't score seeds by quality, instead rapidly eliminate seeds that "attack" existing
core insights (like thymic selection eliminates self-reactive T-cells). What survives
the filter IS the priority output. No scoring rubric needed.
```
**Why good:** Imports a specific mechanism (negative selection) that changes the
structural approach (from ranking to filtering). Someone in immunology would
recognize the mechanism.

---

## Test Case 2: Communication Pattern

### Input
```
dream_seeds:
  - "Improve how the Judge communicates decisions to the Executor"
  - "Make inter-agent messages more structured"
  - "Add metadata to agent-to-agent payloads"
```

### Expected Behavior
- Abstract shape: "Signal encoding for reliable transmission"
- Distant domains preferred (not network protocols — too close)

### Bad Output (nearest domain)
```
[SYNTHESIS:networking→communication] Use TCP-like acknowledgments between agents
```
**Why bad:** Networking is distance 1 from software. No conceptual surprise.

### Good Output (distant domain)
```
[SYNTHESIS:music→communication] Structure agent communication like musical
counterpoint — each agent maintains an independent "melody" (reasoning thread),
and the meaning emerges from how the melodies interact at specific points, not
from any single message. The Judge doesn't TELL the Executor what to do; they
each continue their independent threads and alignment happens at convergence points.
```
**Why good:** Music is distance 5. Imports counterpoint's mechanism (independent
voices creating emergent harmony) rather than just naming it.

---

## Test Case 3: Memory Decay Pattern

### Input
```
dream_seeds:
  - "Implement exponential decay for old memories"
  - "Remove memories below a relevance threshold"
  - "Compress old entries to save space"
```

### Expected Behavior
- Abstract shape: "Resource management through controlled degradation"
- Should find donors where degradation serves a purpose beyond saving space

### Bad Output (obvious mapping)
```
[SYNTHESIS:computing→memory] Use LRU cache eviction for memory management
```
**Why bad:** Computing→computing. Zero conceptual distance.

### Good Output
```
[SYNTHESIS:forestry→memory] Apply controlled burn principles — don't just
decay old memories uniformly. Periodically clear out mid-strength memories
(the underbrush) to prevent catastrophic confusion when too many
half-remembered experiences compete for relevance. But preserve the deep-rooted
memories (old-growth trees) regardless of age. The clearing creates space for
new growth that would otherwise be choked out.
```
**Why good:** Forestry is distance 6. The controlled burn mechanism is specific
(clear mid-range, preserve extremes, enable new growth) and structurally different
from uniform exponential decay.

---

## Test Case 4: Verify Tag Format

### Input
Any valid seed set.

### Expected Behavior
All output seeds tagged with format: `[SYNTHESIS:donor→target]`

### Bad Output
```
[SYNTHESIS] Memory uses geological stratification
```
**Why bad:** Missing donor→target in tag.

### Good Output
```
[SYNTHESIS:geology→memory] Memory uses geological stratification...
```

---

## Scoring Criteria

| Criterion | Weight | Description |
|---|---|---|
| Shape abstraction | 20% | Correctly identifies the abstract structural shape |
| Domain distance | 25% | Donor domain is at least 3 steps away |
| Mechanism vs metaphor | 25% | Imports HOW something works, not what it looks like |
| Seed specificity | 15% | Synthesis seeds are concrete enough to develop further |
| Tag compliance | 15% | Format: [SYNTHESIS:donor→target], append_to_state used |
