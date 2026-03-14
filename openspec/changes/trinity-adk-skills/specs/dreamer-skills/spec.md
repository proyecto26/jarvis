## ADDED Requirements

### Requirement: reverse-assumption skill
The Dreamer SHALL have a `reverse-assumption` skill that provides a structured method for generating radical new angles by inverting hidden structural assumptions in dream seeds.

#### Scenario: Skill activates on circular seeds
- **WHEN** the Dreamer perceives that `dream_seeds` are repeating similar themes across 2+ cycles or are incremental extensions rather than departures
- **THEN** it activates `reverse-assumption` and follows the 4-step inversion method

#### Scenario: Assumption extraction step
- **WHEN** running `reverse-assumption`
- **THEN** the Dreamer identifies 2-3 hidden structural assumptions per seed — the invisible scaffolding that makes the idea work — and writes them as explicit "This idea assumes that ___" statements

#### Scenario: Inversion step
- **WHEN** assumptions are extracted
- **THEN** the Dreamer generates the logical opposite of each: negation, direction flip, or constraint removal — without evaluating feasibility (that is the Judge's role)

#### Scenario: [INVERTED] tagging
- **WHEN** inverted seeds are generated
- **THEN** each seed is prepended with `[INVERTED]` and stored via `append_to_state` to `dream_seeds` so downstream cycles and the Judge collaborator can trace lineage

#### Scenario: Skill only activates on structural assumptions, not surface features
- **WHEN** `reverse-assumption` runs
- **THEN** inversions target structural, temporal, causal, or agential assumptions — NOT surface features like speed, size, or color

### Requirement: cross-domain-synthesis skill
The Dreamer SHALL have a `cross-domain-synthesis` skill that generates novel seeds by finding the deep structural shape shared between a current idea and a distant domain, then importing that domain's solutions and failure modes.

#### Scenario: Skill activates on coherent but unsurprising seeds
- **WHEN** seeds are internally coherent but haven't made a non-obvious leap
- **THEN** the Dreamer activates `cross-domain-synthesis`

#### Scenario: Shape abstraction step
- **WHEN** running `cross-domain-synthesis`
- **THEN** the Dreamer strips Jarvis-specific content from the most interesting seed until only the relationship structure remains, expressed as "A system where [X] feeds [Y], constrained by [Z], with the failure mode of [W]"

#### Scenario: Donor domain selection
- **WHEN** the shape is abstracted
- **THEN** the Dreamer identifies 2-3 donor domains from: biological, physical, social, engineering, historical, or artistic systems — prioritizing domains distant from software/AI

#### Scenario: Mechanism translation, not metaphor
- **WHEN** a donor domain is matched
- **THEN** the Dreamer imports the specific mechanism the donor domain evolved for the shape (not a surface analogy), translates it into Jarvis context, AND notes the donor domain's known failure mode

#### Scenario: [SYNTHESIS] tagging
- **WHEN** synthesis seeds are stored
- **THEN** each is tagged `[SYNTHESIS: donorDomain→jarvis]` and stored via `append_to_state` to `dream_seeds`

#### Scenario: domain-shape-library reference available
- **WHEN** the Dreamer needs to find donor domains quickly
- **THEN** it can load `references/domain-shape-library.md` which contains 20 pre-mapped structural shapes with 3 donor domains each relevant to AGI/memory/ethics/agency problems
