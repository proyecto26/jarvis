## 0. Prerequisites (~0.5 days)

- [ ] 0.1 Pin `google-adk>=1.25.0` in `pyproject.toml` — Skills API requires this version
- [ ] 0.2 Run `pip install -e ".[dev]"` (or `uv sync`) and verify `from google.adk.skills import load_skill_from_dir` succeeds
- [ ] 0.3 Confirm `skill-creator` is in `.claude/skills/skill-creator/` (already done via this change)
- [ ] 0.4 Create all skill directories: `triforce/agents/dreamer/skills/`, `triforce/agents/judge/skills/`, `triforce/agents/executor/skills/`, `triforce/skills/`

## 1. Dreamer Skills (~1 day)

### 1.1 `reverse-assumption`

- [ ] 1.1.1 Create `triforce/agents/dreamer/skills/reverse-assumption/SKILL.md` — frontmatter: name + description only; body: 4-step inversion method (extract assumptions → invert → generate inverted seeds → tag with `[INVERTED]` and store)
- [ ] 1.1.2 Create `references/inversion-examples.md` — 10 worked examples: assumption extraction + inversion across Jarvis-relevant domains (memory, identity, agency, time, belief systems)
- [ ] 1.1.3 Create `references/assumption-taxonomy.md` — taxonomy of assumption types: structural, temporal, causal, agential, scale — with 2-3 examples each for recognition
- [ ] 1.1.4 Validate that SKILL.md description triggers correctly: "seeds feel circular/incremental", "3+ cycles without breakthrough", "ideas feel like extensions not departures"

### 1.2 `cross-domain-synthesis`

- [ ] 1.2.1 Create `triforce/agents/dreamer/skills/cross-domain-synthesis/SKILL.md` — frontmatter: name + description; body: 4-step structural import method (abstract shape → find donor domains → import+translate → generate synthesis seeds tagged `[SYNTHESIS: A→B]`)
- [ ] 1.2.2 Create `references/domain-shape-library.md` — 20 pre-mapped structural shapes with 3 donor domains each, curated for AGI/memory/ethics/agency problem space. Include the immunology→belief-memory example as anchor.
- [ ] 1.2.3 Create `references/translation-patterns.md` — common failure modes: metaphor masquerading as mechanism, adjacent-domain synthesis (software→software), surface inversion instead of structural import. 5 annotated bad examples.

## 2. Judge Skills (~1.5 days)

### 2.1 `ethics-evaluation` (filter mode only)

- [ ] 2.1.1 Create `triforce/agents/judge/skills/ethics-evaluation/SKILL.md` — frontmatter: name + description; body: systematic rubric for filter mode: harm assessment (direct/indirect/systemic), alignment check (objectives + values), reversibility score (1-5 scale with anchors), action weight derivation formula. Output format: structured verdict with each dimension scored.
- [ ] 2.1.2 Create `references/ethics-rubric.md` — detailed scoring anchors per dimension, with worked examples for edge cases: "read a file" (weight 1) vs "send an external email" (weight 5) vs "modify Jarvis's own beliefs" (weight 9). Include Jarvis-specific hard stops (actions that are always weight 10, no exceptions).

### 2.2 `belief-mutation` (filter + collaborator)

- [ ] 2.2.1 Create `triforce/agents/judge/skills/belief-mutation/SKILL.md` — frontmatter: name + description; body: SSGM-aware mutation protocol: pre-write conflict check (cosine similarity > 0.7 with strength > 0.7 → pause), decision tree (merge/supersede/coexist/review), write protocol (strength 0.0-1.0, reason required, source event required), post-write stability check
- [ ] 2.2.2 Create `references/ssgm-protocol.md` — the Stability and Safety Governed Memory framework from Lam et al. (March 2026): conflict detection thresholds, stability monitor (>5 mutations/7 days = drift warning), mutation rate tracking, recovery from belief drift. Plain language, no math.
- [ ] 2.2.3 Add a clear section in SKILL.md for: "When NOT to mutate" — reinforcement (use strength bump, not new mutation), trivial confirmations, single-data-point observations without pattern

### 2.3 `dream-deepening` (collaborator mode only)

- [ ] 2.3.1 Create `triforce/agents/judge/skills/dream-deepening/SKILL.md` — frontmatter: name + description; body: 3-part method: (1) trace seed lineage (INVERTED/SYNTHESIS tags → their origin), (2) connect to past experience via `recall_similar_decisions`, (3) breakthrough detection criteria (reframe ≠ good idea; requires structural shift; only after cycle >= 3). Include `exit_loop` decision protocol: what threshold triggers it, what to store in `breakthrough` state key before calling it.

## 3. Executor Skills (~1.5 days)

### 3.1 `communication-style`

- [ ] 3.1.1 Create `triforce/agents/executor/skills/communication-style/SKILL.md` — frontmatter: name + description; body: core principles (clarity first, warmth without filler, presence, never start with "I"), response length matrix per situation, platform rules (WhatsApp primary: no tables/headers/code blocks, ≤280 words; web: full markdown; unknown: default to WhatsApp rules), what to never do, J.D. tone reference
- [ ] 3.1.2 Create `references/tone-examples.md` — 10+ before/after message pairs covering: task completion, rejection with alternative, escalation notification, error diagnosis, philosophical/reflective response, code output, multi-step result. Each with WhatsApp and web variants.

### 3.2 `journal-entry-writer`

- [ ] 3.2.1 Create `triforce/agents/executor/skills/journal-entry-writer/SKILL.md` — frontmatter: name + description; body: required post-execution workflow (steps 1-2 always, 3-7 conditional), tool reference for `write_journal_entry`, JSON schema per section, quality rules (past tense, no fabricated timestamps, real artifacts only)
- [ ] 3.2.2 Create `references/schema-reference.md` — full Pydantic model definitions mirrored from `triforce/memory/schema.py`: `JournalEntry`, `DreamCycle`, `Judgment`, `Execution`, `Learning`, `BeliefMutation`, `JournalMetadata`. Human-readable format with field descriptions and allowed values.
- [ ] 3.2.3 Create `references/entry-examples.json` — 3-4 complete valid examples per section (executions, judgments, learnings, belief_mutations, open_questions, connections, dreams). Each with a matching ❌ bad example and a comment explaining the error.
- [ ] 3.2.4 Add `write_journal_entry` tool to `executor_agent.tools` in `triforce/agents/executor/agent.py` (currently missing despite the tool existing in `journal_tools.py`)

### 3.3 `escalation-handler`

- [ ] 3.3.1 Create `triforce/agents/executor/skills/escalation-handler/SKILL.md` — frontmatter: name + description; body: action_weight decision matrix (1-3 free / 4-5 log+execute / 6-7 Judge required before acting / 8-10 absolute hard stop), escalation protocol (pause → inform J.D. → write to state → wait), what to tell J.D. during escalation (1-2 sentences, never ghost), hard stop examples (irreversible external commits, self-modification, anything touching Jarvis's own architecture without Judge approval)

## 4. Shared Skills (~0.5 days)

### 4.1 `episodic-recall` (stub for Phase 2)

- [ ] 4.1.1 Create `triforce/skills/episodic-recall/SKILL.md` — frontmatter: name + description (clearly states "requires Phase 2 Mem0 integration"); body: stub that describes the protocol (query format, ActMem-style reasoning chain output format, reinforcement on retrieval) but notes the tool (`recall_episodic`) is not yet available. Agents that load this skill will know the capability exists but is pending.

## 5. SkillToolset Wiring (~1 day)

- [ ] 5.1 Update `triforce/agents/dreamer/agent.py` — import `SkillToolset`, `load_skill_from_dir`, `pathlib`; add `SkillToolset(skills=[load_skill_from_dir(p) for p in SKILLS_DIR.iterdir() if p.is_dir()])` to `tools=[...]`
- [ ] 5.2 Update `triforce/agents/judge/agent.py` — create `FILTER_SKILLS_DIR` and `COLLABORATOR_SKILLS_DIR` (or use a single dir with conditional loading); wire separate `SkillToolset` instances into `judge_filter` and `judge_collaborator`
- [ ] 5.3 Update `triforce/agents/executor/agent.py` — add `SkillToolset` + add `write_journal_entry` to tools (task 3.2.4 above)
- [ ] 5.4 Add shared `triforce/skills/` path to each agent's `SkillToolset` via `additional_tools` or a second `SkillToolset` instance

## 6. Verification (~0.5 days)

- [ ] 6.1 Run `adk run triforce` — confirm all three agents start without import errors
- [ ] 6.2 Verify skill metadata loads at startup: confirm skill names + descriptions appear in agent context without full body loaded
- [ ] 6.3 Test Dreamer: trigger a sleep cycle, confirm `reverse-assumption` or `cross-domain-synthesis` activates in context when seeds are stale
- [ ] 6.4 Test Judge filter: trigger a high-weight action, confirm `ethics-evaluation` and `belief-mutation` activate
- [ ] 6.5 Test Executor: complete a simple task, confirm `journal-entry-writer` workflow produces a valid journal entry with correct schema
- [ ] 6.6 Test `communication-style`: send a message via WhatsApp channel, verify output has no tables/headers and stays under 280 words
- [ ] 6.7 Validate all SKILL.md files with `skills-ref validate` (install: `pip install skills-ref`): check naming, frontmatter, description quality
