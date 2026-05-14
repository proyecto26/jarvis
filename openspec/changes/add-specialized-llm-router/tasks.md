## 1. Foundation

- [x] 1.1 Create `triforce/llm/__init__.py` — exports types and errors
- [x] 1.2 Define `RouteRequest`, `RouteDecision`, `Model`, `Adapter`, `PrivacyClass` in `triforce/llm/types.py`
- [x] 1.3 Define `LocalOnlyRouteFailure`, `NoCandidateError`, `ProviderUnhealthy`, `PolicyError` in `triforce/llm/errors.py`

## 2. Registry

- [x] 2.1 Implement `Registry` class in `triforce/llm/registry.py` — loads from `triforce/llm/models.yaml`
- [x] 2.2 Author initial `models.yaml` — 9 models: 3 Gemini, 2 Nemotron, 4 Gemma 4
- [x] 2.3 Per-model metadata: provider, context window, capabilities, P95 latency, supports_tools, supports_vision, tags

## 3. Providers

- [x] 3.1 Define `Provider` ABC in `triforce/llm/providers/base.py` with `generate()`, `health()`, `capabilities()`
- [x] 3.2 Implement `GeminiProvider` wrapping `google-genai` SDK with system instruction + tool support
- [x] 3.3 Implement `OllamaProvider` using httpx → `/api/chat` for Nemotron + Gemma 4
- [x] 3.4 Provider health-check with 200ms timeout + 30s result cache
- [x] 3.5 Response normalization — uniform `ProviderResponse(text, function_calls, raw, provider, model_id)`

## 4. Routing Policies

- [x] 4.1 Policy YAML schema documented in `triforce/llm/policies/SCHEMA.md`
- [x] 4.2 Policy loader in `triforce/llm/policies/loader.py` with caching + validation
- [x] 4.3 `dreamer.yaml` — prefers Nemotron deep reasoning, local-preferred, 30s latency budget
- [x] 4.4 `judge_filter.yaml` — function_calling required, 1500ms budget, cloud-ok by default
- [x] 4.5 `judge_collaborator.yaml` — long-context preference, 15s budget, local-preferred
- [x] 4.6 `executor.yaml` — low-latency Gemma 4 4B target, 800ms budget, cloud fallback allowed

## 5. Router Engine

- [x] 5.1 Implement `Router.route(request)` in `triforce/llm/router.py`
- [x] 5.2 Candidate scoring: capability match + tag match + latency + locality bonus (with tightest-budget enforcement across step/request/policy)
- [x] 5.3 Adapter selection — `Registry.find_adapters_for(model_id, task_type)` matches task tags
- [x] 5.4 Provider health gating — unhealthy providers demoted; cached for 30s
- [x] 5.5 `local-only` enforcement — `_effective_privacy()` uses strictest of (request, step); raises `LocalOnlyRouteFailure` if no local candidate exists

## 6. Observability

- [x] 6.1 Implement `log_decision()` in `triforce/llm/observability.py` — JSONL append with atomic single-line writes
- [x] 6.2 Every route decision logs: ts, agent, task_type, decision_id, model_id, base_id, provider, is_local, fallback_depth, reasoning, candidates_considered
- [x] 6.3 Policy violations (e.g. `refused_cloud_fallback`) logged at level=warning
- [x] 6.4 `journal/llm-routing/` is under `journal/` (already in `.gitignore` via `journal/*` pattern)

## 7. Agent Integration

- [x] 7.1 Add `Config.model_for(agent, fallback)` to `triforce/config.py` — router-aware, with try/except fallback so router failures never crash the agent
- [x] 7.2 Update `triforce/agents/dreamer/agent.py` — `model=Config.model_for("dreamer", Config.DREAMER_MODEL)`
- [x] 7.3 Update `triforce/agents/judge/agent.py` — `model_for("judge_filter", ...)` and `model_for("judge_collaborator", ...)`
- [x] 7.4 Update `triforce/agents/executor/agent.py` — `model_for("executor", Config.EXECUTOR_MODEL)`
- [x] 7.5 Router returns `base_id` (a plain string) — ADK `Agent(model=...)` accepts strings, no wrapper needed

## 8. Backward Compatibility Escape Hatch

- [x] 8.1 `DANTE_ROUTER=off` (default) → `Config.model_for()` returns the supplied fallback unchanged → byte-identical to pre-router
- [x] 8.2 Forced per-agent overrides via legacy env vars work because they ARE the `fallback` parameter to `model_for()` when router is off
- [x] 8.3 Verified: with `DANTE_ROUTER=off`, agents resolve to `gemini-2.0-flash`, `gemini-2.0-pro-exp`, `gemini-1.5-pro` (legacy defaults); with `DANTE_ROUTER=on` they resolve to `gemma4:4b`, `nemotron:super-49b-v2`, `gemma4:12b` (router picks)

## 9. Router-Audit ADK Skill

- [ ] 9.1 Create `triforce/agents/judge/skills-filter/router-audit/SKILL.md`
- [ ] 9.2 Define audit method: "review the last 24 h of `journal/llm-routing/*.jsonl` for: (a) repeated cloud fallbacks where a local model existed, (b) decision divergence between models on identical tasks, (c) latency budget violations"
- [ ] 9.3 Define output schema: `{regressions: [...], suggested_policy_changes: [...]}`
- [ ] 9.4 Wire skill into Judge filter's `SkillToolset`

## 10. Temporal Activity Determinism (interaction with trinity-temporal-durable-loop)

- [ ] 10.1 In `triforce/temporal/activities.py`, record `routing_decision_id` in `GeminiChatRequest` metadata
- [ ] 10.2 On workflow replay, prefer the originally-recorded model rather than re-routing (replay determinism)
- [ ] 10.3 Add test: workflow that ran on Gemini Pro replays on Gemini Pro even if Nemotron becomes available

## 11. Fine-tuning Hooks (Future Work — Documented, Not Implemented)

- [ ] 11.1 Document `triforce/llm/adapters/README.md` — directory layout for LoRA adapters
- [ ] 11.2 Document `triforce/llm/adapters/manifest.yaml` schema — per-adapter `{id, base_model, task_tags, training_data_ref, eval_score}`
- [ ] 11.3 Document the Unsloth/Gemma 4 fine-tuning workflow (no code, just steps)

## 12. Documentation

- [ ] 12.1 Write `docs/llm-router.md` — overview, policy DSL, how to add a model
- [ ] 12.2 Update `README.md` — add router to the architecture diagram
- [ ] 12.3 Update `.env.example` — document `DANTE_ROUTER`, `OLLAMA_HOST`, optional `NEMOTRON_API_KEY` for cloud Nemotron

## 13. Validation

- [ ] 13.1 Unit tests for `Router.route()` — golden tests for each policy file
- [ ] 13.2 Integration test: with no Ollama running, router falls back to Gemini cleanly
- [ ] 13.3 Integration test: with Ollama running and a local model available, Executor uses local
- [ ] 13.4 Privacy test: `local-only` request with no local model raises rather than falls back
- [ ] 13.5 Determinism test (interacts with Temporal): workflow replay uses the recorded model id
