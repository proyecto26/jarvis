## Why

The Trinity runs — but it runs fragile. If a Dreamer loop crashes mid-iteration, or the Executor's LLM call times out during a 12-step action plan, the entire session state is lost. Jarvis must restart from zero. For a system designed to accumulate wisdom and act in the world, this is unacceptable.

Google's Temporal + Gemini example (March 2026) demonstrates exactly what Jarvis needs: a **durable agentic loop** where every LLM call and every tool invocation is persisted as a Temporal Activity. If the process crashes, Temporal replays completed steps from its event log and resumes exactly where it left off — no repeated tool calls, no lost conversation history.

This change adapts that pattern to Jarvis's Trinity architecture. The existing `workflow.py` already bridges Temporal and OpenAI Agents SDK via `activity_as_tool()` — this change extends that foundation to support Gemini API directly (matching the Google example) and adds Temporal scheduling for the Dreamer's background cycles (the original vision from README.md: *"the Dreamer runs as a Temporal workflow — like sleep cycles, it operates without direct human prompting"*).

## What Changes

- Add `triforce/temporal/activities.py` — durable Temporal Activities for Gemini LLM calls and dynamic tool dispatch; adapted from Google's `generate_content` and `dynamic_tool_activity` pattern
- Add `triforce/temporal/workflows.py` — three durable workflows: `AwakeWorkflow` (ReAct loop for Executor), `DreamWorkflow` (scheduled Dreamer cycles), `ConsolidationWorkflow` (nightly memory consolidation trigger)
- Add `triforce/temporal/worker.py` — Temporal worker startup that registers all workflows and activities, connects to Temporal server
- Add `triforce/temporal/schedules.py` — Temporal Schedule definitions for `DreamWorkflow` (default: every 6 hours) and `ConsolidationWorkflow` (default: nightly at 02:00 local time)
- Update `triforce/config.py` — add Temporal connection config (`TEMPORAL_HOST`, `TEMPORAL_NAMESPACE`, `TEMPORAL_TASK_QUEUE`)
- Update `workflow.py` — extend `activity_as_tool()` bridge to support Gemini API as an activity, not just OpenAI Agents SDK tools

## Capabilities

### New Capabilities

- `durable-awake-loop`: `AwakeWorkflow` — durable ReAct agentic loop for Executor interactions; each Gemini call and each tool invocation is a separate Temporal Activity; crash-safe — resumes from last completed step on failure
- `durable-dream-cycles`: `DreamWorkflow` — Dreamer runs as a Temporal scheduled workflow; background operation without user prompting; configurable schedule (default 6h); produces `DreamOutput` (idea graph + breakthrough candidate) written to journal via durable Activity
- `durable-consolidation`: `ConsolidationWorkflow` — nightly memory consolidation as a Temporal workflow; triggers FadeMem decay, episode compression, SSGM audit; retries individually failed activities without restarting the whole consolidation
- `gemini-activity`: `generate_content` Temporal Activity — direct Gemini API call with automatic retries disabled (Temporal handles it); supports system instructions, tools, multi-turn contents; returns structured `GeminiChatResponse`
- `dynamic-tool-activity`: Dynamic Temporal Activity — executes any registered Jarvis tool by name; Pydantic-model-based argument parsing (matching Google pattern); tool registry extensible without workflow changes

### Modified Capabilities

- `workflow.py`: Extended `activity_as_tool()` bridge now supports Gemini API activities alongside existing OpenAI Agents SDK tools
- `operating-modes`: Awake mode can optionally route through `AwakeWorkflow` for durability on long-running tasks; short interactions still use ADK directly (no overhead)
- `memory-consolidation` (from Phase 2): `consolidation.run_nightly()` now triggered by `ConsolidationWorkflow` on a Temporal Schedule instead of a plain cron job

## Impact

- **New code**: `triforce/temporal/` package (~500 lines): `activities.py`, `workflows.py`, `worker.py`, `schedules.py`
- **Dependencies**: `temporalio` (already referenced in `workflow.py`), `google-genai` (for direct Gemini API in activities)
- **Infrastructure**: Requires a Temporal server (local dev: `temporal server start-dev`; production: Temporal Cloud or self-hosted)
- **Backward compatibility**: ADK agents continue to work without Temporal — the durable loop is additive, not a replacement. Short Awake interactions skip the Temporal overhead entirely
- **Existing `workflow.py`**: Enhanced, not replaced — the `activity_as_tool()` bridge is extended to support Gemini activities
