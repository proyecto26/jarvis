## ADDED Requirements

### Requirement: episodic-recall shared skill (stub)
All three Trinity agents SHALL have access to an `episodic-recall` skill stub that documents the episodic memory query protocol, activated in Phase 2 when Mem0 is integrated.

#### Scenario: Skill exists and is loadable now
- **WHEN** any Trinity agent's `SkillToolset` is initialized
- **THEN** `episodic-recall` appears in the skill menu (name + description) even though the underlying `recall_episodic` tool is not yet available

#### Scenario: Skill body documents the Phase 2 protocol
- **WHEN** `episodic-recall` body is loaded
- **THEN** it describes the planned query format (natural language query → Mem0 hybrid retrieval → top-k results), the ActMem-style reasoning chain output format, and notes that the `recall_episodic` tool will be available after Phase 2 integration

#### Scenario: Skill clearly marks pending implementation
- **WHEN** an agent loads `episodic-recall` and attempts to use it
- **THEN** the skill body explicitly states: "This skill requires the recall_episodic tool which is available from Phase 2 (Mem0 integration). Use recall_similar_decisions (JSON flat scan) as a fallback until then."

#### Scenario: ActMem output format documented
- **WHEN** the skill is fully implemented in Phase 2
- **THEN** query results are formatted as reasoning chains, not flat fact lists: "Context: [what happened] → Implication: [what it means now] → Confidence: [high/medium/low based on recency and reinforcement count]"

### Requirement: SkillToolset includes shared skills
All three Trinity agents SHALL load shared skills from `triforce/skills/` in addition to their agent-specific skills.

#### Scenario: Shared skills loaded alongside agent-specific skills
- **WHEN** an agent's `SkillToolset` is initialized
- **THEN** it loads skills from both `triforce/agents/<agent>/skills/` AND `triforce/skills/` — the agent sees both in its skill menu

#### Scenario: No skill name collisions between shared and agent-specific
- **WHEN** skill directories are loaded
- **THEN** no two skills across the combined set share the same `name` frontmatter value — if a collision occurs, the agent-specific skill takes precedence
