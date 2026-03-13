## Why

Jarvis exists as a vision document but has zero runnable code. The Trinity architecture (Dreamer, Judge, Executor) and the Dream-Judge-Act feedback loop are fully designed in README.md and RESEARCH_DEEP.md, with concrete ADK mappings already identified (LoopAgent for sleep cycles, SequentialAgent for awake pipeline). Phase 1 turns this architecture into a working multi-agent system using Google ADK in Python — making the Trinity real so that all subsequent phases (memory, durability, skills) have a running foundation to build on.

## What Changes

- Add a working Google ADK multi-agent system under `triforce/` with three agents: Dreamer, Judge, and Executor
- Implement three operating modes: Awake (SequentialAgent), Reflective (LlmAgent), and Sleep/Dream (LoopAgent)
- Implement the Dream-Judge-Act feedback loop using ADK session state and agent transfers
- Define Judge dual-mode behavior: filter mode (awake) and connector mode (sleep)
- Create the daily journal (bitacora) schema and basic file-based writer for structured memory
- Wire the root dispatcher agent that routes to the correct operating mode
- Add project scaffolding: pyproject.toml, dependencies, environment config
- Enable running with `adk run triforce` or `python -m triforce`

## Capabilities

### New Capabilities
- `dreamer-agent`: Subconscious agent using ADK LlmAgent with append_to_state tool, unconstrained idea generation, runs within LoopAgent during sleep cycles
- `judge-agent`: Conscience agent with dual-mode system prompts (filter for awake, connector for sleep), exit_loop control, action weight evaluation, self-mutation via structured beliefs
- `executor-agent`: Fast-model frontline agent that operates from Judge briefings, interfaces with J.D., escalates high-weight decisions
- `operating-modes`: Three operating modes (Awake via SequentialAgent, Reflective via LlmAgent, Sleep via LoopAgent) with root dispatcher routing
- `dream-loop`: Sleep state LoopAgent implementation with Dreamer-Judge iteration, breakthrough detection, exit_loop mechanism, and max_iterations safety bound
- `journal-schema`: Daily journal (bitacora) structured schema with sections for dreams, judgments, executions, learnings, and judge self-mutations; basic file-based persistence

### Modified Capabilities

_(none — this is the initial implementation)_

## Impact

- **New code**: Python package under `triforce/` with agents, modes, tools, memory, and root_agent modules
- **Dependencies**: `google-adk`, `pydantic`, `python-dotenv`; Python 3.11+
- **Project config**: New `pyproject.toml` (or updates to existing), `.env` for model/API configuration
- **Existing files**: No modifications to existing README.md, RESEARCH.md, or RESEARCH_DEEP.md — Phase 1 builds alongside them
- **Runtime**: Requires Google ADK CLI (`adk run`) or direct Python execution; requires Gemini API key
