## Why

The three Trinity agents (Dreamer, Judge, Executor) currently receive all their instructions via their main `instruction=` prompt at agent construction time. This means every interaction carries the full cognitive load of every capability, whether it's needed or not. The Executor's 11-line stub prompt has no platform rules, no journal schema awareness, and no escalation protocol. The Judge's ethics evaluation is 4 vague bullets. The Dreamer has a mandate ("associate wildly") but no method.

Google ADK v1.25.0+ introduces the `SkillToolset` — a mechanism where skills are loaded progressively: only the skill name and description are in context at startup (~100 tokens per skill), and the full instructions load only when the agent decides to activate a skill (~5000 tokens). This is the "Neo downloading kung-fu" pattern described in the README — agents acquire capabilities on demand without rebuilding.

This change implements 8 ADK Skills across the Trinity: 2 for the Dreamer (creative methods), 3 for the Judge (evaluation + belief safety), 3 for the Executor (communication, memory, escalation), and 1 shared cross-agent skill (episodic memory query). It also wires `SkillToolset` into each agent's `tools=[]` and establishes the `skills/` directory convention that all future agent capabilities follow.

## What Changes

- Add `SkillToolset` wiring to all three Trinity agents (Dreamer, Judge filter, Judge collaborator, Executor) via a `skills/` subdirectory per agent
- Implement 8 skill directories following the AgentSkills.io spec (SKILL.md + optional references/ assets/)
- Add shared skills under `triforce/skills/` for cross-agent capabilities
- Add `google-adk>=1.25.0` version pin to `pyproject.toml` (Skills API requires this)
- Install `skill-creator` in `.claude/skills/` so coding agents can create and audit skills properly
- Establish the skill-loading pattern: `SkillToolset(skills=[load_skill_from_dir(p) for p in SKILLS_DIR.iterdir() if p.is_dir()])` — adding a new skill directory = new capability, zero code changes

## Capabilities

### New Capabilities

**Dreamer skills** (`triforce/agents/dreamer/skills/`):
- `reverse-assumption`: Structured divergence method — inverts hidden structural assumptions in stale dream seeds to generate radical new angles. Activated when seeds feel circular or incremental after 3+ cycles.
- `cross-domain-synthesis`: Structural import method — finds the deep "shape" shared between a current idea and a distant domain (biology, physics, history, music) and imports that domain's solutions and failure modes.

**Judge skills** (`triforce/agents/judge/skills/`):
- `ethics-evaluation`: Systematic evaluation framework for filter mode — harm, alignment, reversibility, and action weight scoring. Replaces 4 vague bullets with an explicit, auditable rubric.
- `belief-mutation`: SSGM-aware belief update protocol — conflict detection, similarity scoring, merge/supersede/coexist/review decision tree. Safety layer for the Judge's most consequential operation.
- `dream-deepening`: Structured method for collaborator mode — how to connect Dreamer seeds to past experience, what constitutes a genuine breakthrough vs. a good idea, when to call `exit_loop`.

**Executor skills** (`triforce/agents/executor/skills/`):
- `communication-style`: Tone, length heuristics, and platform-specific formatting rules. WhatsApp (primary channel): no tables, no headers, no code blocks, ≤280 words. With ✅/❌ examples for every case.
- `journal-entry-writer`: Schema-aware workflow for all 7 journal sections. Steps 1-2 (append_to_state + write execution) are never optional. JSON schemas per section, with quality rules.
- `escalation-handler`: action_weight decision matrix (1-3 free, 4-5 log+execute, 6-7 Judge required, 8-10 hard stop), escalation protocol, what to tell J.D. during escalation, absolute never-execute rules.

**Shared skills** (`triforce/skills/`):
- `episodic-recall`: Standard protocol for querying Mem0 episodic memory (Phase 2) and formatting results as ActMem-style reasoning chains. All three agents query memory identically — one skill eliminates three divergent implementations.

### Modified Capabilities

- `dreamer-agent`: Adds `SkillToolset` to `tools=[]`; base prompt trimmed of method-level instructions (moved to skills)
- `judge-agent`: `judge_filter` and `judge_collaborator` each get a `SkillToolset` with their respective skill subsets; `recall_similar_decisions` tool gets `journal-entry-writer` awareness
- `executor-agent`: Adds `SkillToolset` to `tools=[]`; adds `write_journal_entry` tool (currently missing); base prompt trimmed to routing logic only
- `pyproject.toml`: `google-adk` pinned to `>=1.25.0` for Skills API compatibility

## Impact

- **New code**: 8 `SKILL.md` files + ~6 reference files in `references/` (~800 lines total across skills)
- **Modified code**: 4 agent `agent.py` files (SkillToolset wiring, ~10 lines each)
- **Dependencies**: `google-adk>=1.25.0` (Skills API is experimental, added in 1.25.0)
- **Backward compatibility**: `SkillToolset` is additive — existing tools remain in `tools=[]`; skills are additional capabilities, not replacements
- **Future skills**: Any new agent capability can be added as a skill directory without touching `agent.py` — the `[load_skill_from_dir(p) for p in SKILLS_DIR.iterdir() if p.is_dir()]` pattern auto-discovers new skills
- **Limitation**: ADK Skills script execution (`scripts/` directory) is not yet supported in the ADK runtime — all skill logic must be in `SKILL.md` instructions or `references/` files, not executable scripts
