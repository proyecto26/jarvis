## 1. Dependencies & Configuration (~0.5 days)

- [x] 1.1 Add `temporalio` and `google-genai` to `pyproject.toml` `[temporal]` extras
- [x] 1.2 Add Temporal config to `triforce/config.py`: `TEMPORAL_ADDRESS`, `TEMPORAL_NAMESPACE`, `TEMPORAL_TASK_QUEUE` (aligned during this audit — was previously read directly via `os.getenv` in worker/schedules)
- [x] 1.3 Add dream schedule config: `DREAM_INTERVAL_HOURS` (default: 6), `CONSOLIDATION_HOUR_UTC` (default: 3 UTC — implementation chose hourly cron instead of full cron expression)
- [x] 1.4 Update `.env.example` with Temporal config variables
- [x] 1.5 Create `triforce/temporal/__init__.py`

## 2. Temporal Activities (~1.5 days)

- [x] 2.1 Create `triforce/temporal/activities.py`
- [x] 2.2 Implement `GeminiChatRequest` dataclass: `model`, `system_instruction`, `contents`, `tools`
- [x] 2.3 Implement `GeminiChatResponse` dataclass: `text | None`, `function_calls: list[dict]`, `raw_parts: list`
- [x] 2.4 Implement `generate_content` Temporal Activity — calls Gemini API with `automatic_function_calling` disabled and retries disabled; returns `GeminiChatResponse`
- [x] 2.5 Implement Jarvis tool registry — `register_tool(name, handler)` / `get_handler(name)` in `activities.py`
- [x] 2.6 Implement `dynamic_tool_activity` Temporal Activity (dynamic=True) — handles sync and async handlers, returns dict
- [ ] 2.7 Implement `write_journal_entry_activity` Temporal Activity — *NOT YET IMPLEMENTED. Journal writes currently go through `dynamic_tool_activity` via the tool registry; a dedicated Activity wrapper for Mem0 indexing was deferred when Mem0 was dropped from the memory stack.*
- [ ] 2.8 Implement `run_consolidation_activity` Temporal Activity — *Pending: `ConsolidationWorkflow.run` exists but calls `dynamic_tool_activity` with `run_consolidation`; the dedicated Activity with heartbeats is still TODO.*
- [ ] 2.9 Implement `seed_dream_context_activity` — *Pending: depends on episodic memory tool wiring into the Temporal Activity registry.*

## 3. Temporal Workflows (~2 days)

- [x] 3.1 Create `triforce/temporal/workflows.py`
- [x] 3.2 Implement `AwakeWorkflow` — durable ReAct agentic loop (input/output dataclasses defined, loop logic in place)
- [x] 3.3 Implement `DreamWorkflow` — scheduled Dreamer cycle with breakthrough detection
- [x] 3.4 Implement `ConsolidationWorkflow` — nightly memory worker
- [x] 3.5 `@workflow.defn` decorators and Temporal sandbox `imports_passed_through()` blocks in workflows.py

## 4. Temporal Worker (~1 day)

- [x] 4.1 Create `triforce/temporal/worker.py`
- [x] 4.2 Implement `start_worker()` — registers `AwakeWorkflow`, `DreamWorkflow`, `ConsolidationWorkflow` and `generate_content`, `dynamic_tool_activity`
- [ ] 4.3 Use `pydantic_data_converter` from `temporalio.contrib.pydantic` for Pydantic model serialization — *not yet wired; default JSON converter used. Add when Pydantic models start flowing through Activity inputs.*
- [x] 4.4 `__main__` entry point: `python -m triforce.temporal.worker` starts the worker
- [x] 4.5 Load `.env` via `python-dotenv` — imported transitively via `triforce.config`

## 5. Temporal Schedules (~0.5 days)

- [x] 5.1 Create `triforce/temporal/schedules.py`
- [x] 5.2 Implement `create_dream_schedule(client)` — idempotent, uses `ScheduleIntervalSpec(every=timedelta(hours=DREAM_INTERVAL_HOURS))`
- [x] 5.3 Implement `create_consolidation_schedule(client)` — daily at `CONSOLIDATION_HOUR_UTC` via `ScheduleCalendarSpec`
- [ ] 5.4 Add `setup_schedules` CLI entry: `python -m triforce.temporal.schedules` — *NOT IMPLEMENTED. Both schedule-creation functions exist but no module-level CLI hook calls them yet.*

## 6. ADK Integration — Action Weight Routing (~1 day)

- [ ] 6.1 Update `triforce/root_agent.py` — route to `AwakeWorkflow` via Temporal client when `action_weight >= 4` — *DEFERRED. Today the root agent uses ADK in-process for all weights; the Temporal escape hatch exists as workflows but isn't auto-routed.*
- [ ] 6.2 Implement `triforce/temporal/client.py` — lazy client singleton — *DEFERRED with 6.1.*
- [ ] 6.3 Update Executor agent — add `escalate_to_durable_workflow` tool — *DEFERRED with 6.1.*
- [ ] 6.4 Update Judge filter — add `workflow_mode` to verdict output — *DEFERRED with 6.1.*

## 7. `workflow.py` Extension (~0.5 days)

- [ ] 7.1 Add `gemini_activity_as_tool(...)` to `workflow.py` — *not present; `workflow.py` does not exist at repo root. Tasks 7.1/7.2 may need re-scoping.*
- [ ] 7.2 Ensure existing `activity_as_tool()` is unchanged — *N/A: no `workflow.py` at root.*

## 8. Documentation & Verification (~0.5 days)

- [x] 8.1 Add `TEMPORAL.md` to repo root — quick-start guide for Temporal CLI setup
- [ ] 8.2 Verify `AwakeWorkflow` crash recovery — *requires live Temporal server*
- [ ] 8.3 Verify `DreamWorkflow` schedule firing — *requires live Temporal server*
- [ ] 8.4 Verify `ConsolidationWorkflow` end-to-end — *requires live Temporal server*
- [ ] 8.5 Verify Temporal Web UI shows correct workflow history — *requires live Temporal server*

## Implementation Notes

- The implementation diverged from the plan in two architecturally relevant places:
  1. **Action-weight routing (§6)** — never wired. The Trinity currently runs ADK in-process for all weights; the Temporal workflows are available as opt-in but not auto-routed by the Judge.
  2. **`workflow.py` bridge (§7)** — the OpenAI Agents SDK / Temporal `activity_as_tool()` bridge described in the plan does not exist at the repo root. Tasks 7.1–7.2 likely refer to an earlier file layout and should be re-scoped or removed.
- Verification tasks (§8.2–8.5) all require a live `temporal server start-dev` instance plus `GOOGLE_API_KEY`; they were left unchecked to surface in the next integration session.
- The new `add-specialized-llm-router` change will add `routing_decision_id` to `GeminiChatRequest` for replay determinism — a forward dependency to track.
