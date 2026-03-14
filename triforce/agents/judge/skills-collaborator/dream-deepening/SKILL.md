---
name: dream-deepening
description: >
  Deepens Dreamer's ideas by tracing seed lineage, connecting to past experience,
  and detecting breakthroughs. Use when the Judge is in collaborator mode during
  dream cycles. Activates when evaluating dream seeds for breakthrough potential.
compatibility:
  - google-adk
metadata:
  scope: judge_collaborator
  triggers:
    - evaluating dream seeds during sleep mode
    - looking for breakthrough connections
    - tracing idea lineage across cycles
  requires_tools:
    - append_to_state
    - exit_loop
    - recall_similar_decisions
---

# Dream Deepening Method

You are activating the **Dream Deepening** skill. This helps the Judge-as-collaborator
find genuine breakthroughs in the Dreamer's output by connecting ideas to past experience.

## When to Use

- During every dream cycle evaluation in collaborator mode
- When dream seeds show tags like `[INVERTED]` or `[SYNTHESIS:X→Y]`
- When evaluating whether the dream loop should continue or exit

## 3-Part Method

### Part 1: Trace Seed Lineage

For each dream seed, trace its creative lineage by examining tags:

**[INVERTED] seeds:**
- Which assumption was inverted?
- What was the original seed before inversion?
- How many inversions deep is this? (Count [INVERTED] tags in lineage)
- Is the inversion structural (good) or surface (weak)?

**[SYNTHESIS:donor→target] seeds:**
- What mechanism was imported?
- From which domain?
- Is it a mechanism import (good) or a metaphor (weak)?
- Does the synthesis create a genuinely new pattern?

**Untagged seeds:**
- These are first-generation ideas
- Useful baseline but unlikely to be breakthroughs on their own
- Can they be deepened via inversion or synthesis?

Build a **lineage map:**
```
Seed A (original)
  └── Seed B [INVERTED] (inverted A's temporal assumption)
       └── Seed C [SYNTHESIS:ecology→B] (imported symbiosis into B)
            └── Seed D [INVERTED] (inverted C's agency assumption) ← depth 3+
```

### Part 2: Connect to Past Experience

Use `recall_similar_decisions` to find past beliefs, decisions, or experiences
related to the current dream seeds.

For each connection found:
- How does the past experience **reframe** the current seed?
- Does the seed address a problem that past experience identified?
- Does the seed contradict past beliefs? (Could be a breakthrough OR a regression)
- Does the seed open a new direction that past experience couldn't see?

**Key question:** "Does this seed let me see something I couldn't see before,
specifically because of what I've experienced since?"

### Part 3: Breakthrough Detection

A breakthrough is NOT:
- A "good idea" (incremental quality improvement)
- A "useful suggestion" (practical but not structural)
- A "clever analogy" (decorative, not structural)

A breakthrough IS:
- A **reframe** — a structural shift in how a problem or domain is understood
- It changes the question, not just the answer
- After seeing it, you can't unsee it — it permanently expands the solution space

**Breakthrough criteria (ALL must be met):**

1. **Structural reframe:** The seed doesn't just answer a question differently —
   it changes what question is being asked
2. **dream_depth >= 3:** The seed has gone through at least 3 transformations
   (inversions, syntheses, or deepenings). Raw ideas at depth 0-2 are rarely
   true breakthroughs.
3. **Past connection:** The seed connects to past experience in a way that
   reframes that experience (not just reminds of it)
4. **Novelty:** This specific structural insight hasn't appeared in previous
   dream cycles (check via recall_similar_decisions)

### Scoring

Rate each seed:
```
dream_depth: <number of transformations>
past_connections: <number of meaningful connections to past experience>
reframe_score: 0-10 (0 = no reframe, 10 = fundamental structural shift)
breakthrough: true/false
```

## Exit Loop Protocol

**When to exit (call `exit_loop`):**
- A breakthrough has been detected (all 4 criteria met)
- Before exiting, you MUST:
  1. Store the breakthrough seed and its lineage map via `append_to_state`
     with key `dream_deepening`
  2. Store the specific reframe in `append_to_state` with key `breakthrough_insight`
  3. Record the past connections that validated the breakthrough
  4. THEN call `exit_loop`

**When NOT to exit:**
- No breakthrough yet AND iteration count < max (8)
- Seeds are still being refined (depth increasing)
- New [INVERTED] or [SYNTHESIS] tags appeared this cycle (still evolving)

**When to exit without breakthrough:**
- If iteration count reaches max (8) with no breakthrough, exit gracefully
- Store the best seed and explain why it fell short of breakthrough
- This is normal — not every dream cycle produces a breakthrough

## Output

Store results via `append_to_state`:
- Key `dream_deepening`: Full analysis with lineage maps and scores
- Key `breakthrough_insight`: The breakthrough reframe (if detected)
- Key `dream_seeds`: Refined/deepened seeds for next iteration (if continuing)
