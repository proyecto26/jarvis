## ADDED Requirements

### Requirement: SkillToolset wired into all agent instances
All four Trinity agent instances (dreamer, judge_filter, judge_collaborator, executor) SHALL have a `SkillToolset` in their `tools=[]`.

#### Scenario: Auto-discovery pattern
- **WHEN** an agent's `SkillToolset` is constructed
- **THEN** it uses `[load_skill_from_dir(p) for p in SKILLS_DIR.iterdir() if p.is_dir()]` to auto-discover all skill directories — adding a new skill directory = new capability without touching `agent.py`

#### Scenario: SkillToolset is additive to existing tools
- **WHEN** `SkillToolset` is added to an agent
- **THEN** existing tools (`append_to_state`, `recall_similar_decisions`, `exit_loop`, `write_journal_entry`) remain in `tools=[]` alongside the `SkillToolset` — skills do not replace tools

#### Scenario: Judge filter and collaborator get different skill subsets
- **WHEN** `judge_filter` is instantiated
- **THEN** its `SkillToolset` loads from `triforce/agents/judge/skills-filter/` containing: `ethics-evaluation`, `belief-mutation`

- **WHEN** `judge_collaborator` is instantiated
- **THEN** its `SkillToolset` loads from `triforce/agents/judge/skills-collaborator/` containing: `belief-mutation`, `dream-deepening`

#### Scenario: google-adk version requirement satisfied
- **WHEN** the package is installed
- **THEN** `google-adk>=1.25.0` is resolved — `from google.adk.skills import load_skill_from_dir` succeeds without ImportError

### Requirement: write_journal_entry added to Executor
The Executor agent SHALL have `write_journal_entry` in its `tools=[]`.

#### Scenario: Tool available to Executor
- **WHEN** the Executor agent is initialized
- **THEN** `write_journal_entry` from `triforce/tools/journal_tools.py` is in `tools=[]`

#### Scenario: Tool was previously missing
- **WHEN** this change is applied
- **THEN** it corrects the existing bug where `write_journal_entry` existed in `journal_tools.py` but was never added to the Executor's tool list (Phase 1 oversight)

### Requirement: AgentSkills.io spec compliance
All SKILL.md files SHALL be compliant with the AgentSkills.io specification.

#### Scenario: Only valid frontmatter keys
- **WHEN** any SKILL.md is written
- **THEN** its YAML frontmatter contains only: `name`, `description`, and optionally `license`, `compatibility`, `metadata`, `allowed-tools` — no custom top-level keys

#### Scenario: Name matches directory name
- **WHEN** a skill directory is created at `skills/reverse-assumption/`
- **THEN** the `name` frontmatter in its `SKILL.md` is exactly `reverse-assumption`

#### Scenario: Description triggers properly
- **WHEN** an agent's skill menu is presented
- **THEN** each skill's description is self-contained enough for the agent to decide whether to activate it without reading the body — description includes both WHAT the skill does and WHEN to use it

#### Scenario: skills-ref validation passes
- **WHEN** `skills-ref validate triforce/agents/dreamer/skills/reverse-assumption` is run
- **THEN** it exits with code 0 (no validation errors)
