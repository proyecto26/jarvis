---
name: reverse-assumption
description: >
  Inverts implicit assumptions in dream seeds to generate structurally novel ideas.
  Use when seeds repeat themes across 2+ cycles or produce only incremental variations.
  Activates on stale, converging, or overly similar dream outputs.
compatibility:
  - google-adk
metadata:
  scope: dreamer
  triggers:
    - repeated themes across dream cycles
    - incremental-only variations in seeds
    - convergent idea patterns
  requires_tools:
    - append_to_state
---

# Reverse-Assumption Inversion Method

You are activating the **Reverse-Assumption** creative method. This skill breaks creative
ruts by finding and inverting the hidden assumptions in existing dream seeds.

## When to Use

- Seeds from the last 2+ cycles share similar themes or structures
- Ideas feel incremental (adding adjectives to existing concepts, not restructuring)
- The dream space is converging instead of expanding

## 4-Step Inversion Method

### Step 1: Extract Assumptions

Read the current `dream_seeds` from state. For each seed, identify 2-3 **implicit
structural assumptions** — things the seed takes for granted about how the world works.

Focus on assumptions that are:
- **Structural**: How things are organized (centralized vs distributed, hierarchical vs flat)
- **Temporal**: How things relate to time (sequential, simultaneous, reversible)
- **Causal**: What causes what (A→B, but what if B→A?)
- **Agential**: Who/what has agency (humans, systems, data, environment)
- **Scale**: At what level things operate (individual, group, civilization, cosmic)

Use the taxonomy in `references/assumption-taxonomy.md` for classification.

**Output format per seed:**
```
Seed: "<original seed>"
Assumptions:
  1. [TYPE] <assumption>
  2. [TYPE] <assumption>
  3. [TYPE] <assumption>
```

### Step 2: Invert Each Assumption

For each assumption, generate its **structural inverse** — not the surface opposite,
but a world where the assumption's structure is reversed.

**Bad inversion** (surface): "centralized storage" → "distributed storage"
**Good inversion** (structural): "centralized storage" → "storage that doesn't need a central
authority — each experience is self-indexing and finds its own place"

Rules:
- Invert the **mechanism**, not just the adjective
- If the assumption is about control, invert who/what controls
- If about sequence, invert the order or remove sequentiality entirely
- If about agency, give agency to what was passive

### Step 3: Generate Inverted Seeds

From the best inversions (most surprising, most structurally different), compose 3-5
new dream seeds. Each must:
- Be specific and actionable (not vague philosophical musings)
- Carry the structural inversion into a concrete scenario
- Be tagged with `[INVERTED]` prefix for lineage tracking

**Format:**
```
[INVERTED] <new seed based on structural inversion>
```

### Step 4: Store via append_to_state

Use `append_to_state` with key `dream_seeds` to add each new inverted seed.

Do NOT remove the original seeds — the Judge will evaluate both original and
inverted seeds for breakthrough potential.

## Quality Checks

Before storing, verify each inverted seed passes:
- [ ] It is NOT just the original with a negation word added
- [ ] It describes a different **structure**, not just a different **attribute**
- [ ] Someone reading it would say "I never thought of it that way"
- [ ] It could lead to at least 2 follow-up ideas

## See Also

- `references/inversion-examples.md` — 10 worked examples across domains
- `references/assumption-taxonomy.md` — full taxonomy of assumption types
