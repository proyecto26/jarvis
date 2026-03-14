# Translation Patterns

Common failure modes in cross-domain synthesis, with 5 annotated bad examples
and guidance on correct translation.

---

## Failure Mode 1: Metaphor Without Mechanism

**Symptom:** The synthesis sounds poetic but doesn't specify HOW the mechanism works.

**Bad Example 1:**
- Donor: Ecology (symbiosis)
- Seed: "Agent memory should be symbiotic with the user"
- Why bad: What does "symbiotic" mean operationally? Nothing. It's decoration.
- **Fix:** "Agent memory and user input co-evolve: each user correction strengthens
  the memory pathway that produced the response, AND the memory system's patterns
  shape what questions the user thinks to ask (like gut bacteria influencing food cravings)"

## Failure Mode 2: Surface Mapping Only

**Symptom:** Mapping nouns 1:1 between domains without translating the structural relationships.

**Bad Example 2:**
- Donor: Immunology (T-cell selection)
- Seed: "Ideas are like T-cells — we should select the best ones"
- Why bad: Maps "ideas"→"T-cells" and "selection"→"selection" but misses the actual
  mechanism: negative selection (eliminating self-reactive cells) is more important
  than positive selection (finding useful ones).
- **Fix:** "Like thymic selection, the Judge should primarily eliminate ideas that would
  'attack' existing core beliefs (negative selection), rather than trying to pick
  the 'best' ideas (positive selection). What survives the filter IS the output."

## Failure Mode 3: Picking the Nearest Domain

**Symptom:** Importing from a domain that's already conceptually close.

**Bad Example 3:**
- Donor: Database systems (indexing)
- Seed: "Use B-tree indexing for memory retrieval"
- Why bad: This is just software engineering borrowing from software engineering.
  No conceptual distance = no surprise = no creative value.
- **Fix:** Import from a distant domain: "Use geological stratigraphy — memories are
  layered by deposition time, and retrieval requires 'excavating' through layers,
  where deeper memories carry more contextual sediment from their era"

## Failure Mode 4: Ignoring Domain Constraints

**Symptom:** Importing a mechanism that only works because of constraints absent in the target.

**Bad Example 4:**
- Donor: Ant colony (pheromone trails)
- Seed: "Leave pheromone trails on good ideas so other cycles find them"
- Why bad: Pheromone trails work because they EVAPORATE — there's a built-in decay
  mechanism. Without evaporation, every path gets marked and the signal is meaningless.
- **Fix:** "Leave decaying relevance markers on ideas — markers that fade over time
  unless reinforced by multiple independent cycles visiting the same idea. The decay
  IS the mechanism, not just the marking."

## Failure Mode 5: Losing the Emergent Property

**Symptom:** Translating the mechanism correctly but missing the emergent behavior it produces.

**Bad Example 5:**
- Donor: Music (counterpoint)
- Seed: "Have the Dreamer and Judge alternate like musical counterpoint"
- Why bad: Alternation is just turn-taking. The emergent property of counterpoint
  is that two independent melodies create a third thing — harmony — that neither
  contains alone.
- **Fix:** "Structure Dreamer-Judge interaction so their independent outputs, when
  combined, produce emergent insights that neither could generate alone — like
  counterpoint where the harmony exists between the voices, not in either one"

---

## Translation Checklist

When importing a mechanism from donor → target domain:

1. **Name the mechanism explicitly** — not what it looks like, but how it works
2. **Identify the essential constraint** — what makes this mechanism function?
3. **Check: does that constraint exist in the target?** If not, you must add it
4. **Identify the emergent property** — what behavior arises from the mechanism?
5. **Verify the emergent property is desirable** — do we want that in our domain?
6. **Specify the translation concretely** — enough detail to implement, not just admire
