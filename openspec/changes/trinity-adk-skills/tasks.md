## 0. Prerequisites (~0.5 days)

- [x] 0.1 Pin `google-adk>=1.25.0` in `pyproject.toml` — Skills API requires this version
- [x] 0.2 Run `pip install -e ".[dev]"` (or `uv sync`) and verify `from google.adk.skills import load_skill_from_dir` succeeds
- [x] 0.3 Confirm `skill-creator` is in `.claude/skills/skill-creator/` (already done via this change)
- [x] 0.4 Create all skill directories: `triforce/agents/dreamer/skills/`, `triforce/agents/judge/skills/`, `triforce/agents/executor/skills/`, `triforce/skills/`

## 1. Dreamer Skills (~1 day)

### 1.1 `reverse-assumption`

- [x] 1.1.1 Create `triforce/agents/dreamer/skills/reverse-assumption/SKILL.md` — frontmatter: name + description only; body: 4-step inversion method (extract assumptions → invert → generate inverted seeds → tag with `[INVERTED]` and store)
- [x] 1.1.2 Create `references/inversion-examples.md` — 10 worked examples: assumption extraction + inversion across Jarvis-relevant domains (memory, identity, agency, time, belief systems)
- [x] 1.1.3 Create `references/assumption-taxonomy.md` — taxonomy of assumption types: structural, temporal, causal, agential, scale — with 2-3 examples each for recognition
- [ ] 1.1.4 Validate that SKILL.md description triggers correctly: "seeds feel circular/incremental", "3+ cycles without breakthrough", "ideas feel like extensions not departures" — *runtime verification, deferred until live agent run*

### 1.2 `cross-domain-synthesis`

- [x] 1.2.1 Create `triforce/agents/dreamer/skills/cross-domain-synthesis/SKILL.md` — frontmatter: name + description; body: 4-step structural import method (abstract shape → find donor domains → import+translate → generate synthesis seeds tagged `[SYNTHESIS: A→B]`)
- [x] 1.2.2 Create `references/domain-shape-library.md` — 20 pre-mapped structural shapes with 3 donor domains each, curated for AGI/memory/ethics/agency problem space. Include the immunology→belief-memory example as anchor.
- [x] 1.2.3 Create `references/translation-patterns.md` — common failure modes: metaphor masquerading as mechanism, adjacent-domain synthesis (software→software), surface inversion instead of structural import. 5 annotated bad examples.

## 2. Judge Skills (~1.5 days)

### 2.1 `ethics-evaluation` (filter mode only)

- [x] 2.1.1 Create `triforce/agents/judge/skills/ethics-evaluation/SKILL.md` — implemented at `skills-filter/ethics-evaluation/SKILL.md` (split filter/collaborator dirs)
- [x] 2.1.2 Create `references/ethics-rubric.md` — detailed scoring anchors per dimension, with worked examples for edge cases

### 2.2 `belief-mutation` (filter + collaborator)

- [x] 2.2.1 Create `triforce/agents/judge/skills/belief-mutation/SKILL.md` — implemented in BOTH `skills-filter/belief-mutation/` AND `skills-collaborator/belief-mutation/`
- [x] 2.2.2 Create `references/ssgm-protocol.md` — present under both skills-filter and skills-collaborator
- [x] 2.2.3 "When NOT to mutate" section in SKILL.md — reinforcement, trivial confirmations, single-data-point observations

### 2.3 `dream-deepening` (collaborator mode only)

- [x] 2.3.1 Create `triforce/agents/judge/skills/dream-deepening/SKILL.md` — implemented at `skills-collaborator/dream-deepening/SKILL.md`

## 3. Executor Skills (~1.5 days)

### 3.1 `communication-style`

- [x] 3.1.1 Create `triforce/agents/executor/skills/communication-style/SKILL.md`
- [x] 3.1.2 Create `references/tone-examples.md`

### 3.2 `journal-entry-writer`

- [x] 3.2.1 Create `triforce/agents/executor/skills/journal-entry-writer/SKILL.md`
- [x] 3.2.2 Create `references/schema-reference.md`
- [x] 3.2.3 Create `references/entry-examples.json`
- [x] 3.2.4 Add `write_journal_entry` tool to `executor_agent.tools` in `triforce/agents/executor/agent.py`

### 3.3 `escalation-handler`

- [x] 3.3.1 Create `triforce/agents/executor/skills/escalation-handler/SKILL.md` (+ `references/escalation-examples.md`)

## 4. Shared Skills (~0.5 days)

### 4.1 `episodic-recall` (now backed by Phase 2 memory)

- [x] 4.1.1 Create `triforce/skills/episodic-recall/SKILL.md` — *Note: was originally a stub for Phase 2 Mem0 integration; the Phase 2 rewrite (commit `2734779`) replaced Mem0 with BM25+sentence-transformers+Grafeo. The skill is now backed by the real `recall_episodic` tool in `triforce/tools/memory_tools.py`.*

## 5. SkillToolset Wiring (~1 day)

- [x] 5.1 Update `triforce/agents/dreamer/agent.py` — `SkillToolset(skills=[load_skill_from_dir(p) for p in SKILLS_DIR.iterdir() if p.is_dir()])` wired
- [x] 5.2 Update `triforce/agents/judge/agent.py` — separate `SkillToolset` instances for filter and collaborator (using `skills-filter/` and `skills-collaborator/` directories)
- [x] 5.3 Update `triforce/agents/executor/agent.py` — `SkillToolset` wired + `write_journal_entry` in tools + `recall_episodic`, `check_belief_conflict`, `reinforce_memory` (from Phase 2 integration)
- [x] 5.4 Add shared `triforce/skills/` path — included via shared `SHARED_SKILLS` directory walk in each agent

## 6. Verification (~0.5 days)

- [ ] 6.1 Run `adk run triforce` — *requires GOOGLE_API_KEY env; deferred to live integration test*
- [ ] 6.2 Verify skill metadata loads at startup
- [ ] 6.3 Test Dreamer skill activation
- [ ] 6.4 Test Judge filter skill activation
- [ ] 6.5 Test Executor `journal-entry-writer` workflow end-to-end
- [ ] 6.6 Test `communication-style` WhatsApp constraints
- [ ] 6.7 Validate all SKILL.md files with `skills-ref validate`

## Implementation Notes

- The plan called for a single `skills/` directory per agent; the implementation uses `skills-filter/` and `skills-collaborator/` directories under the judge agent to enable mode-specific skill loading. Functionally equivalent.
- Reference files exist for all skills that the plan specified.
- All 6 verification tasks require a running ADK runtime + Gemini API key — left unchecked to surface in the next live-test session.
