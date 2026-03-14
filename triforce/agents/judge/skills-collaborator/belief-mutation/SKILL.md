---
name: belief-mutation
description: >
  SSGM-aware protocol for safely mutating the Judge's belief system. Checks for
  conflicts before writing, uses a decision tree (merge/supersede/coexist/review),
  and enforces required fields. Use when the Judge needs to update, add, or modify
  its beliefs based on new experience or evidence.
compatibility:
  - google-adk
metadata:
  scope: judge
  triggers:
    - new evidence contradicts existing belief
    - experience suggests a belief update
    - belief reinforcement after successful outcome
    - dream cycle produces insight affecting beliefs
  requires_tools:
    - append_to_state
    - recall_similar_decisions
---

# Belief Mutation Protocol (SSGM-Aware)

You are activating the **Belief Mutation** protocol. This skill ensures that changes
to the Judge's belief system are safe, traceable, and conflict-aware.

Based on the Self-Supervised Goal Mutation (SSGM) framework (Lam et al., March 2026).
See `references/ssgm-protocol.md` for the underlying research.

## When to Use

- When new evidence or experience suggests a belief should be updated
- When a dream cycle produces an insight that affects the Judge's beliefs
- When a belief needs reinforcement (strength increase) after positive outcome
- When a belief should be weakened after contradictory evidence

## Mutation vs Reinforcement

**Reinforcement** (not a mutation — simpler process):
- Same belief, higher strength, same reason
- Example: "I believed X with strength 0.6, and X was confirmed → strength 0.7"
- Does NOT trigger conflict check
- Still requires logging

**Mutation** (this protocol):
- Changed belief content, new belief, or belief removal
- Example: "I believed X, but evidence Y suggests Z instead"
- REQUIRES full conflict check before writing

## Pre-Write Conflict Check (MANDATORY)

Before writing any belief mutation, you MUST:

1. **Retrieve existing beliefs** using `recall_similar_decisions` with the new belief text
2. **Check for conflicts:** Does any existing belief with strength > 0.7 have
   semantic similarity > 0.7 with the proposed belief but different content?
3. **If conflict detected:** Follow the decision tree below
4. **If no conflict:** Proceed to write

## Decision Tree for Conflicts

When a conflict is detected between new belief N and existing belief E:

```
Is N more specific than E?
├── YES → MERGE: Keep E, add N as a refinement (both persist, N references E)
├── NO
│   Is E contradicted by strong evidence?
│   ├── YES → SUPERSEDE: Close E (set valid_until=now), write N with supersedes_id=E.id
│   ├── NO
│   │   Are N and E about different contexts?
│   │   ├── YES → COEXIST: Both persist with context tags differentiating them
│   │   └── NO → REVIEW: Flag for J.D.'s attention. Do NOT auto-resolve.
│   │           Store both with a "pending_review" tag.
```

## Required Fields for Every Mutation

Every belief mutation MUST include:

```json
{
  "belief": "<the belief statement — clear, specific, falsifiable>",
  "strength": <0.0 to 1.0>,
  "reason": "<why this mutation is happening — link to evidence>",
  "source_event": "<what triggered this: dream_id, judgment_id, or execution_id>",
  "mutation_type": "<new | updated | superseded | merged | coexisting>"
}
```

**Field rules:**
- `belief`: Must be a complete sentence. No fragments. Must be falsifiable.
- `strength`: 0.0 = no confidence, 1.0 = certain. New beliefs start at 0.3-0.5.
  Beliefs only reach 0.9+ after multiple independent confirmations.
- `reason`: Must reference specific evidence. "It seems right" is NOT a valid reason.
- `source_event`: Must trace back to a specific journal entry or dream cycle.
- `mutation_type`: Must be one of the five allowed types.

## Stability Monitor

Track the mutation rate. If the Judge detects:
- **> 5 mutations in 7 days**: Emit a drift warning in the journal
- **> 3 supersessions of the same belief topic**: Flag for architectural review
- **Oscillation** (A→B→A pattern): HARD STOP — something is wrong with the evidence

## Output

After completing the protocol, use `append_to_state` to store:
- Key `belief_mutation`: The mutation record (JSON)
- Key `belief_conflict_report`: Conflict check result (if any)

## See Also

- `references/ssgm-protocol.md` — SSGM framework in plain language
