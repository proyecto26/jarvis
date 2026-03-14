---
name: cross-domain-synthesis
description: >
  Imports structural mechanisms from distant domains to generate novel ideas.
  Use when dream seeds are coherent but unsurprising — good quality but lacking novelty.
  Activates on well-formed but predictable seed patterns.
compatibility:
  - google-adk
metadata:
  scope: dreamer
  triggers:
    - coherent but unsurprising seeds
    - predictable idea patterns
    - seeds that feel "correct but boring"
  requires_tools:
    - append_to_state
---

# Cross-Domain Synthesis Method

You are activating the **Cross-Domain Synthesis** creative method. This skill breaks
predictability by importing structural mechanisms from distant knowledge domains.

## When to Use

- Seeds are well-formed and coherent but lack surprise
- Ideas feel like obvious next steps rather than creative leaps
- The dream space needs injection of genuinely new structural patterns

## Key Principle

**Import mechanisms, not metaphors.**

Bad synthesis: "Memory is like a river" (metaphor — decorative, not structural)
Good synthesis: "Memory uses the mechanism rivers use — erosion creates channels that
make future flow more likely in the same direction, but floods can carve entirely new paths"

## 4-Step Structural Import Method

### Step 1: Abstract the Shape

Read the current `dream_seeds` from state. For each seed, identify its **abstract
structural shape** — the pattern stripped of domain-specific details.

**Example:**
- Seed: "Build a priority queue for processing dream seeds"
- Shape: "Items compete for limited processing attention based on assigned scores"
- Abstract: **"Competitive allocation under scarcity"**

Common shapes:
- Competitive allocation (priority queues, markets, evolution)
- Feedback amplification (compound interest, epidemics, rumors)
- Phase transition (water→ice, startup→scale, individual→movement)
- Symbiotic coupling (gut bacteria, pollination, trade)
- Signal/noise separation (immune system, spam filter, attention)

See `references/domain-shape-library.md` for 20 shapes with donor domains.

### Step 2: Find Donor Domains

For the abstract shape, identify 2-3 **distant donor domains** where this shape
appears in a dramatically different context. Distance is key — the further the
domain from AI/software, the more surprising the synthesis.

**Distance ranking (prefer bottom):**
1. Other software patterns (closest — avoid)
2. Business/management
3. Biology/ecology
4. Physics/chemistry
5. Music/art/architecture
6. History/anthropology
7. Geology/astronomy (furthest — prefer)

### Step 3: Import and Translate

From each donor domain, extract the **specific mechanism** that makes the shape
work there. Then translate it into the dream seed's domain.

**Translation checklist:**
- What is the equivalent of [donor element] in [seed domain]?
- What constraint in the donor domain doesn't exist in ours? (Remove it)
- What constraint in our domain doesn't exist in the donor? (Add it)
- What emergent property does the donor mechanism produce? (Can we get that too?)

See `references/translation-patterns.md` for failure modes and annotated examples.

### Step 4: Generate Synthesis Seeds

Compose 3-5 new seeds that carry the imported mechanism. Tag each with
`[SYNTHESIS:donor→target]` for lineage tracking.

**Format:**
```
[SYNTHESIS:geology→memory] <new seed importing geological mechanism into memory>
```

### Store via append_to_state

Use `append_to_state` with key `dream_seeds` to add each synthesis seed.

## Quality Checks

Before storing, verify each synthesis seed:
- [ ] Imports a **mechanism** (how something works), not a **metaphor** (what something looks like)
- [ ] The donor domain is at least 3 steps away on the distance ranking
- [ ] The translated mechanism produces a genuinely novel structural pattern
- [ ] Someone from the donor domain would recognize the mechanism
- [ ] Someone from the target domain would find it surprising

## See Also

- `references/domain-shape-library.md` — 20 structural shapes with donor domains
- `references/translation-patterns.md` — failure modes and annotated examples
