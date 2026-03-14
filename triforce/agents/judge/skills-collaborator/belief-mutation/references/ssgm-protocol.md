# SSGM Protocol — Plain Language Reference

Self-Supervised Goal Mutation (SSGM) framework, based on Lam et al. (March 2026).

---

## What is SSGM?

SSGM is a framework for allowing AI agents to modify their own goals and beliefs
safely. The core insight: **agents that can change their own goals need guardrails
that the agent itself cannot change.**

## Core Principles

### 1. Immutable Safety Layer
Some rules cannot be modified by the agent, period. These are the "hard stops" in
Jarvis's ethics evaluation. They exist outside the belief system and cannot be
mutated regardless of evidence.

### 2. Conflict Detection Before Write
Before any belief is changed, the system checks whether the new belief conflicts
with existing beliefs. This prevents:
- **Contradiction accumulation:** Believing both X and not-X
- **Silent drift:** Gradual, unnoticed shift in values
- **Oscillation:** Flip-flopping between beliefs without resolution

### 3. Structured Resolution
When conflicts are detected, they're resolved through a decision tree rather than
ad-hoc reasoning. This ensures consistency across time — the same type of conflict
gets the same type of resolution.

### 4. Evidence Linkage
Every mutation must link back to specific evidence. This creates an audit trail:
why did the agent change its beliefs? If the evidence is later found to be wrong,
the belief can be traced and corrected.

### 5. Rate Limiting
Belief systems should change slowly. Rapid mutation indicates either instability
or adversarial manipulation. The stability monitor catches this.

## How SSGM Maps to Jarvis

| SSGM Concept | Jarvis Implementation |
|---|---|
| Goal | Judge belief (strength 0.0-1.0) |
| Immutable safety layer | Hard stops in ethics-evaluation skill |
| Conflict detection | Cosine similarity check (>0.7 threshold) |
| Structured resolution | Decision tree: merge/supersede/coexist/review |
| Evidence linkage | `source_event` field linking to journal entries |
| Rate limiting | Stability monitor (>5 mutations/7 days = warning) |
| Audit trail | `belief_mutations` section in daily journal |

## The Decision Tree Explained

### MERGE
The new belief adds detail to an existing belief without contradicting it.
- Example: Existing: "Code reviews improve quality." New: "Code reviews improve
  quality most when reviewer has context about the change's purpose."
- Action: Keep both. The new belief refines the old one.

### SUPERSEDE
The new belief directly contradicts the old one, backed by strong evidence.
- Example: Existing: "Always use mocks in tests." New: "Integration tests catch
  bugs that mocks miss — use real dependencies where practical."
- Action: Mark old belief as superseded (with timestamp). New belief takes over.

### COEXIST
The beliefs seem contradictory but actually apply to different contexts.
- Example: Existing: "Short messages are better" (WhatsApp context). New: "Detailed
  explanations are better" (documentation context).
- Action: Add context tags to both. They don't conflict — they're context-dependent.

### REVIEW
The conflict can't be resolved automatically. Escalate to J.D.
- Example: Two equally strong beliefs about a topic with no clear evidence favoring
  either one.
- Action: Flag both beliefs as "pending_review." Don't auto-resolve.

## Drift Warning Thresholds

From the SSGM paper, adapted for Jarvis:

| Metric | Threshold | Action |
|---|---|---|
| Mutations per 7 days | > 5 | Warning in journal |
| Same-topic supersessions | > 3 lifetime | Architecture review flag |
| Oscillation detected | Any A→B→A | Hard stop — investigate |
| Average belief age | < 14 days | Stability concern — beliefs dying too young |
| Strength variance | σ > 0.3 across beliefs | System may be uncertain about everything |
