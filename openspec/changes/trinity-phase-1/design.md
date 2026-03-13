## Context

Jarvis is an experimental AGI architecture designed around a three-agent Trinity: Dreamer (subconscious), Judge (conscience), and Executor (action). The architecture is fully documented in README.md, RESEARCH.md, and RESEARCH_DEEP.md, with detailed ADK mappings already identified. However, no runnable code exists.

The existing `workflow.py` demonstrates a Temporal + OpenAI Agents SDK bridge via `activity_as_tool()`. Phase 1 intentionally sets aside Temporal integration (Phase 3) and focuses on getting the three agents running with Google ADK's native multi-agent primitives.

Key constraints:
- Python 3.11+ (AI ecosystem priority)
- Google ADK as agent framework (LoopAgent, SequentialAgent, ParallelAgent primitives)
- Gemini models (configurable per agent tier)
- File-based journal for memory (no database in Phase 1)
- Must run locally with `adk run` or `python -m triforce`

## Goals / Non-Goals

**Goals:**
- Working three-agent system with Dreamer, Judge, and Executor as ADK agents
- Three operating modes (Awake, Reflective, Sleep) with root dispatcher routing
- Dream-Judge-Act feedback loop via ADK session state
- Judge dual-mode: filter (awake) and connector (sleep) via different system prompts
- Daily journal schema with basic file-based persistence
- Clean project structure that supports incremental Phase 2+ additions
- Runnable with `adk run triforce` for interactive use

**Non-Goals:**
- Temporal integration (Phase 3 — durability layer)
- PageIndex / reasoning-based RAG over journal (Phase 2 — memory retrieval)
- Dynamic skill loading for Executor (Phase 4 — skills system)
- PersonaPlex voice integration (Phase 5)
- PostHog feature flags (added when there's something to gate)
- Production deployment or cloud infrastructure
- Fine-tuning or model training
- Web UI or API server

## Decisions

### 1. Google ADK as sole agent framework

**Choice**: Use Google ADK exclusively; do not integrate OpenAI Agents SDK in Phase 1.

**Rationale**: ADK provides the exact multi-agent primitives needed — LoopAgent maps to dream cycles, SequentialAgent maps to awake pipeline. The existing `workflow.py` uses OpenAI SDK but is tightly coupled to Temporal, which is out of scope for Phase 1. Introducing two agent frameworks adds complexity without benefit at this stage.

**Alternative considered**: Abstraction layer over both ADK and OpenAI SDK. Rejected — premature abstraction for a system with zero running code.

### 2. Agent hierarchy with LlmAgent root dispatcher

**Choice**: Root agent is an `LlmAgent` (named `jarvis`) that routes to three sub-agents based on context: `awake_pipeline` (SequentialAgent), `dream_state` (LoopAgent), `reflective_session` (LlmAgent).

**Rationale**: ADK's `LlmAgent` with `sub_agents` performs LLM-driven routing based on agent descriptions — matching the natural-language mode selection Jarvis needs. This mirrors the `film_concept_team` pattern from the ADK multi-agent lab.

**Alternative considered**: Manual mode switching via explicit commands only. Rejected — loses the fluid, cognitive feel of the architecture.

### 3. Model tier per agent via environment variables

**Choice**: Each agent's model is configured via environment variables (`DREAMER_MODEL`, `JUDGE_MODEL`, `EXECUTOR_MODEL`) with sensible defaults:
- Dreamer: `gemini-2.0-pro` (high reasoning)
- Judge: `gemini-2.0-pro` (medium, balanced)
- Executor: `gemini-2.0-flash` (fast)

**Rationale**: Allows local development with flash models everywhere, while production can use tiered models matching each agent's cognitive role. Environment-based config avoids hardcoding and works with both `adk run` and direct Python execution.

**Alternative considered**: Single model for all agents. Rejected — undermines the core architectural insight that different cognitive roles need different speed/depth trade-offs.

### 4. Judge dual-mode via instruction switching, not separate agents

**Choice**: One Judge agent class with two instruction templates (`filter_prompt` and `collaborator_prompt`). The mode is set when constructing the agent for each operating mode.

**Rationale**: Same underlying capability, different activation context — exactly as described in RESEARCH_DEEP.md. Two separate agent classes would duplicate shared logic (beliefs, memory access, self-mutation).

**Alternative considered**: Two distinct Judge agents. Rejected — they share the same beliefs, memory, and mutation logic.

### 5. Session state as working memory between agents

**Choice**: Use ADK's `tool_context.state` (session state) for all inter-agent communication. Key conventions:
- `judge_verdict`, `judge_reasoning`, `action_weight` — awake pipeline
- `dream_seeds`, `dream_deepening`, `dream_depth`, `breakthrough` — sleep loop
- `executor_guidance`, `execution_outcome` — executor context
- `judge_beliefs` — persistent beliefs loaded at session start

**Rationale**: ADK session state is the native mechanism for agent-to-agent data passing. Key-templating (`{ variable? }`) in agent instructions allows zero-code data flow. This matches the "silent communication" principle from README.md.

### 6. Journal as structured Markdown files, one per day

**Choice**: Daily journal entries as `journal/YYYY-MM-DD.md` files following a fixed schema. Written via an ADK tool (`write_journal_entry`). No database.

**Rationale**: Phase 1 needs persistence but not retrieval intelligence (that's Phase 2 with PageIndex). Markdown files are human-readable, git-trackable, and trivially parseable. The schema mirrors RESEARCH_DEEP.md's proposed structure.

**Alternative considered**: SQLite or JSON files. Rejected — Markdown is more inspectable and aligns with the journal metaphor. JSON loses readability; SQLite adds a dependency for no Phase 1 benefit.

### 7. Judge self-mutation via `judge_beliefs.json`

**Choice**: The Judge maintains a `memory/judge_beliefs.json` file containing structured beliefs, constraints, and learned principles. This file is loaded into the Judge's context at session start and updated after significant judgments.

**Rationale**: This is the "structured memory" approach from RESEARCH_DEEP.md — fast, debuggable, human-readable. Fine-tuning is too expensive; RAG over own history requires PageIndex (Phase 2).

### 8. Project structure

**Choice**:
```
triforce/
  __init__.py
  __main__.py              # python -m triforce entry point
  agents/
    dreamer/
      __init__.py
      agent.py             # ADK Agent definitions
      prompts.py           # Instruction templates
    judge/
      __init__.py
      agent.py
      prompts.py
    executor/
      __init__.py
      agent.py
      prompts.py
  modes/
    __init__.py
    awake.py               # SequentialAgent pipeline
    sleep.py               # LoopAgent dream state
    reflective.py          # LlmAgent reflective session
  tools/
    __init__.py
    state_tools.py         # append_to_state, etc.
    journal_tools.py       # write_journal_entry, read_journal
  memory/
    __init__.py
    journal.py             # Journal file I/O
    beliefs.py             # Judge beliefs load/save
    schema.py              # Pydantic models
  root_agent.py            # Root dispatcher (adk run entry point)
  config.py                # Environment-based configuration
journal/                   # Daily journal entries (gitignored data)
memory/
  judge_beliefs.json       # Judge's evolving beliefs
```

**Rationale**: Mirrors the structure proposed in RESEARCH_DEEP.md Section 7. Separates agents, modes, tools, and memory into clear modules. `root_agent.py` at package root is the ADK convention for `adk run`.

## Risks / Trade-offs

**[Risk] ADK API instability** — Google ADK is relatively new; APIs may change.
→ Mitigation: Pin ADK version in pyproject.toml. Keep agent definitions thin (mostly prompts + tool references) so migration is low-cost.

**[Risk] Session state size limits** — Dream loops accumulate state across iterations; large `dream_seeds` lists could exceed context windows.
→ Mitigation: Implement state summarization — after N iterations, compress dream_seeds to key themes. `max_iterations=8` provides a hard bound.

**[Risk] Journal files grow unbounded** — No automatic cleanup or archival in Phase 1.
→ Mitigation: Acceptable for Phase 1 (personal use, low volume). Phase 2 introduces PageIndex which handles large journal sets.

**[Risk] Judge self-mutation drift** — `judge_beliefs.json` could accumulate contradictory beliefs over time.
→ Mitigation: Include belief strength scores and timestamps. Phase 2 adds RAG-based contradiction detection. For Phase 1, the file is human-reviewable.

**[Risk] No durability** — Without Temporal, crashes lose in-flight dream cycles.
→ Mitigation: Acceptable for Phase 1 (local development). Journal writes are atomic (write-to-temp-then-rename). Phase 3 adds Temporal durability.

**[Trade-off] No retrieval over journal** — Judge cannot search past entries in Phase 1; only current session state is available.
→ Accepted: Phase 2 (PageIndex) addresses this. Phase 1 loads `judge_beliefs.json` as accumulated wisdom proxy.

**[Trade-off] Single-process execution** — No background Dreamer scheduling.
→ Accepted: Phase 1 triggers sleep mode explicitly (user says "dream" or "think deeply"). Phase 3 adds Temporal-scheduled background cycles.
