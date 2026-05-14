## 1. Foundation

- [ ] 1.1 Create `triforce/llm/__init__.py`
- [ ] 1.2 Define `RouteRequest`, `RouteDecision`, `Model`, `Provider`, `Adapter` dataclasses in `triforce/llm/types.py`
- [ ] 1.3 Define `LocalOnlyRouteFailure`, `NoCandidateError`, `ProviderUnhealthy` exceptions in `triforce/llm/errors.py`

## 2. Registry

- [ ] 2.1 Implement `Registry` class in `triforce/llm/registry.py` — loads model declarations from `triforce/llm/models.yaml`
- [ ] 2.2 Author initial `models.yaml` with: Gemini Pro/Flash, Nemotron Nano/Super (via Ollama), Gemma 4 1B/4B/12B (via Ollama)
- [ ] 2.3 Capture per-model metadata: provider, context window, capabilities, P95 latency, supports_tools, supports_vision

## 3. Providers

- [ ] 3.1 Define `Provider` ABC in `triforce/llm/providers/base.py` with `generate()`, `health()`, `capabilities()` methods
- [ ] 3.2 Implement `GeminiProvider` wrapping `google-genai` SDK
- [ ] 3.3 Implement `OllamaProvider` for both Nemotron and Gemma 4 served via local Ollama
- [ ] 3.4 Add provider health-check with configurable timeout (default 200 ms)
- [ ] 3.5 Add provider response normalization (all providers return uniform `Response(text, function_calls, raw)`)

## 4. Routing Policies

- [ ] 4.1 Define policy YAML schema in `triforce/llm/policies/SCHEMA.md`
- [ ] 4.2 Implement policy loader in `triforce/llm/policies/loader.py`
- [ ] 4.3 Author `dreamer.yaml` — prefer local reasoning model, allow cloud for vision, latency budget = unlimited (Sleep mode)
- [ ] 4.4 Author `judge_filter.yaml` — prefer model with ethics adapter, fall back to Gemini Pro, latency budget = 1500 ms
- [ ] 4.5 Author `judge_collaborator.yaml` — prefer long-context model, latency budget = unlimited (Sleep mode)
- [ ] 4.6 Author `executor.yaml` — prefer low-latency local model, latency budget = 800 ms, cloud allowed if budget exceeded

## 5. Router Engine

- [ ] 5.1 Implement `Router.route(request)` in `triforce/llm/router.py`
- [ ] 5.2 Implement candidate scoring (capability match + latency budget + privacy class)
- [ ] 5.3 Implement adapter selection (match `task_type` to adapter tags)
- [ ] 5.4 Implement provider health gating (demote unhealthy providers in candidate ranking)
- [ ] 5.5 Implement `local-only` enforcement (raise `LocalOnlyRouteFailure` rather than fall back to cloud)

## 6. Observability

- [ ] 6.1 Implement `RoutingLogger` in `triforce/llm/observability.py` — JSONL append-only with atomic writes
- [ ] 6.2 Log every route decision with: timestamp, request_signature, decision, candidates_considered, reasoning
- [ ] 6.3 Log policy violations at WARNING level
- [ ] 6.4 Add `journal/llm-routing/` to `.gitignore` template (it's per-machine)

## 7. Agent Integration

- [ ] 7.1 Add `Config.MODEL_ROUTER` singleton in `triforce/config.py` (lazy-initialized, idempotent)
- [ ] 7.2 Update `triforce/agents/dreamer/agent.py` to use `Config.MODEL_ROUTER.for_agent("dreamer")`
- [ ] 7.3 Update `triforce/agents/judge/agent.py` to use `Config.MODEL_ROUTER.for_agent("judge_filter")` and `for_agent("judge_collaborator")`
- [ ] 7.4 Update `triforce/agents/executor/agent.py` to use `Config.MODEL_ROUTER.for_agent("executor")`
- [ ] 7.5 Verify ADK accepts the router-returned model surface (may need a thin `ModelHandle` wrapper)

## 8. Backward Compatibility Escape Hatch

- [ ] 8.1 Honor `DANTE_ROUTER=off` env var — restore legacy hardcoded model selection
- [ ] 8.2 Honor forced overrides via existing env vars (`EXECUTOR_MODEL`, etc.) — log warning that override bypasses routing
- [ ] 8.3 Add migration test: with `DANTE_ROUTER=off`, behavior is byte-identical to pre-router code paths

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
