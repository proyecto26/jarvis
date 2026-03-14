## 1. Dependencies & Configuration (~0.5 days)

- [ ] 1.1 Add `temporalio` and `google-genai` to `pyproject.toml` dependencies (verify versions compatible with existing `workflow.py`)
- [ ] 1.2 Add Temporal config to `triforce/config.py`: `TEMPORAL_HOST` (default: `localhost:7233`), `TEMPORAL_NAMESPACE` (default: `default`), `TEMPORAL_TASK_QUEUE` (default: `jarvis-main`)
- [ ] 1.3 Add dream schedule config: `DREAM_INTERVAL_HOURS` (default: 6), `CONSOLIDATION_CRON` (default: `"0 2 * * *"`)
- [ ] 1.4 Update `.env.example` with Temporal config variables
- [ ] 1.5 Create `triforce/temporal/__init__.py`

## 2. Temporal Activities (~1.5 days)

- [ ] 2.1 Create `triforce/temporal/activities.py`
- [ ] 2.2 Implement `GeminiChatRequest` dataclass: `model`, `system_instruction`, `contents`, `tools`
- [ ] 2.3 Implement `GeminiChatResponse` dataclass: `text | None`, `function_calls: list[dict]`, `raw_parts: list`
- [ ] 2.4 Implement `generate_content` Temporal Activity — calls Gemini API with `automatic_function_calling` disabled and `retry_options.attempts=1`; returns `GeminiChatResponse`
- [ ] 2.5 Implement Jarvis tool registry in `activities.py` — `get_handler(tool_name)` returning async handler; initial registry: journal tools, state tools, memory tools (from Phase 2)
- [ ] 2.6 Implement `dynamic_tool_activity` Temporal Activity (dynamic=True) — inspects handler signature, handles Pydantic model args (matching Google pattern); returns `dict`
- [ ] 2.7 Implement `write_journal_entry_activity` Temporal Activity — wraps `triforce/tools/journal_tools.py` write + Mem0 indexing as a single durable unit
- [ ] 2.8 Implement `run_consolidation_activity` Temporal Activity — calls `consolidation.run_nightly()` (Phase 2); heartbeats every 30s during long consolidation runs
- [ ] 2.9 Implement `seed_dream_context_activity` — queries Mem0 episodic index for recent memories, returns `dream_seeds` list for DreamWorkflow

## 3. Temporal Workflows (~2 days)

- [ ] 3.1 Create `triforce/temporal/workflows.py`
- [ ] 3.2 Implement `AwakeWorkflow` — durable ReAct agentic loop:
  - Initialize `contents` with user input
  - Loop: call `generate_content` Activity → check for `function_calls`
  - If function calls: call `dynamic_tool_activity` for each → append results to `contents`
  - If no function calls: call `write_journal_entry_activity` → return final text
  - `start_to_close_timeout=60s` per LLM call, `30s` per tool call
- [ ] 3.3 Implement `DreamWorkflow` — scheduled Dreamer cycle:
  - Call `seed_dream_context_activity` to load episodic seeds
  - Loop up to `max_iterations=8`: call `generate_content` (Dreamer prompt) → call `generate_content` (Judge collaborator prompt)
  - Break on `breakthrough=true` in Judge response content
  - Call `write_journal_entry_activity` with `DreamCycle` section
- [ ] 3.4 Implement `ConsolidationWorkflow` — nightly memory worker:
  - Call `run_consolidation_activity` with heartbeat
  - Log completion to journal via `write_journal_entry_activity`
- [ ] 3.5 Add `@workflow.defn` decorators and proper Temporal sandbox `imports_passed_through()` blocks for `pydantic_core`, `httpx`, `google.genai` (following Google pattern)

## 4. Temporal Worker (~1 day)

- [ ] 4.1 Create `triforce/temporal/worker.py`
- [ ] 4.2 Implement `start_worker()` async function — creates Temporal client, registers `AwakeWorkflow`, `DreamWorkflow`, `ConsolidationWorkflow`; registers `generate_content`, `dynamic_tool_activity`, `write_journal_entry_activity`, `run_consolidation_activity`, `seed_dream_context_activity`
- [ ] 4.3 Use `pydantic_data_converter` from `temporalio.contrib.pydantic` for Pydantic model serialization
- [ ] 4.4 Add `__main__` entry point: `python -m triforce.temporal.worker` starts the worker
- [ ] 4.5 Load `.env` via `python-dotenv` before worker start

## 5. Temporal Schedules (~0.5 days)

- [ ] 5.1 Create `triforce/temporal/schedules.py`
- [ ] 5.2 Implement `create_dream_schedule(client)` — creates Temporal Schedule for `DreamWorkflow` with `every=timedelta(hours=DREAM_INTERVAL_HOURS)`
- [ ] 5.3 Implement `create_consolidation_schedule(client)` — creates Temporal Schedule for `ConsolidationWorkflow` with cron expression from `CONSOLIDATION_CRON`
- [ ] 5.4 Add `setup_schedules` CLI entry: `python -m triforce.temporal.schedules` creates both schedules (idempotent — skips if already exists)

## 6. ADK Integration — Action Weight Routing (~1 day)

- [ ] 6.1 Update `triforce/root_agent.py` — after Judge evaluation returns `action_weight`, if `>= 4` route to `AwakeWorkflow` via Temporal client; otherwise continue ADK inline
- [ ] 6.2 Implement `triforce/temporal/client.py` — lazy Temporal client singleton, initialized from config; `start_awake_workflow(input, workflow_id)` helper
- [ ] 6.3 Update Executor agent — add tool `escalate_to_durable_workflow(task_description)` for Executor to self-escalate long-running tasks mid-interaction
- [ ] 6.4 Update Judge filter — add `workflow_mode: "inline" | "durable"` to judge verdict output; "durable" when plan has > 3 sequential steps

## 7. `workflow.py` Extension (~0.5 days)

- [ ] 7.1 Add `gemini_activity_as_tool(activity_fn, **temporal_opts) -> Tool` to `workflow.py` — variant of `activity_as_tool()` that wraps Gemini-specific activities for use in hybrid ADK+Temporal setups
- [ ] 7.2 Ensure existing `activity_as_tool()` (OpenAI Agents SDK bridge) is unchanged and still passes existing tests

## 8. Documentation & Verification (~0.5 days)

- [ ] 8.1 Add `TEMPORAL.md` to repo root — quick-start guide: install Temporal CLI, `temporal server start-dev`, run worker, setup schedules
- [ ] 8.2 Verify `AwakeWorkflow` crash recovery: start a multi-step workflow, kill the worker mid-execution, restart it — confirm it resumes from last completed Activity
- [ ] 8.3 Verify `DreamWorkflow` schedule: confirm it fires at configured interval, writes to journal, does not fire duplicate runs
- [ ] 8.4 Verify `ConsolidationWorkflow`: trigger manually via `temporal workflow start`, confirm consolidation runs and journal entry is written
- [ ] 8.5 Verify Temporal Web UI shows workflow history with correct Activity names and arguments
