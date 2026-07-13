# Proposal: add-model-preferences-and-topic-routing

## Why

The LLM router (change `add-specialized-llm-router`, implemented on branch `autoresearch/memory-optimization-2026-03-22`) picks models per *agent role* via YAML policies, but it cannot (a) reach any frontier model besides Gemini — only `gemini.py` and `ollama.py` providers exist, (b) let the operator change an agent's default model at runtime the way hermes-agent's `/model [provider:model]` or OpenClaw's per-agent model config do, or (c) look at the *content* of a query and dispatch it to a topic-specialized local model (e.g. a fine-tuned Gemma 4). The 2026-07-12 harness research (`examples/README.md`) showed every serious harness converged on runtime model switching; DANTE's router proposal already reserved "cheap classification, intent routing" as an edge-model use case but never specified the stage.

## What Changes

- **New providers** for Anthropic and OpenAI-compatible endpoints (the latter covers OpenAI, OpenRouter, and any compatible server), implementing the existing `Provider` ABC (`generate`, `health`, `capabilities`) so Fable/Opus/GPT models become registry candidates alongside Gemini and local Ollama models.
- **Runtime per-agent model preferences**: a `set_agent_model(agent, model_id, reason)` / `clear_agent_model(agent)` API, exposed to the operator through an Executor tool. Preferences persist across restarts and are recorded as OKF `Preference` documents in the knowledge bundle (change `adopt-okf-knowledge`), so every model switch lands in the bitácora with date and reason.
- **Topic-based specialist routing**: an optional classify-then-route stage — a cheap local edge model (Gemma 4 1B via Ollama) tags the request's topic; registry models/adapters may declare `specializes: [<topic>, ...]`; a specialist match outranks generic policy scoring. Fully skippable: if no edge model or no specialist matches, routing proceeds exactly as today.
- **Routing precedence becomes explicit and documented**: env force (`DREAMER_MODEL` etc.) → user runtime preference → topic specialist → policy scoring/fallback chain → `on_no_candidate`. Today's behavior is preserved when no preference/specialist exists (zero regression).
- Route decisions logged to `journal/llm-routing/` gain two fields: `preference_source` (env | user | specialist | policy) and `topic` (when classified), so the Judge's router-audit can evaluate whether user preferences and specialists actually outperform policy picks.

## Capabilities

### New Capabilities
- `external-model-providers`: Anthropic and OpenAI-compatible provider adapters with health checks, uniform `generate()` surface, and API-key-based configuration; absent keys degrade gracefully (provider reports unhealthy, router skips it).
- `model-preferences`: runtime per-agent default model selection — set/clear/inspect, persistence across restarts, OKF `Preference` audit trail, and precedence between env force and policy scoring.
- `topic-routing`: content-based specialist dispatch — edge-model topic classification, `specializes` tags in the registry, specialist scoring boost, and graceful skip when classification is unavailable.

### Modified Capabilities
- `llm-router` (defined in change `add-specialized-llm-router`, not yet archived): the routing decision order changes from "env force → policy" to the five-level precedence above; `RouteDecision` gains `preference_source` and `topic` fields.

## Impact

- **Code**: new `triforce/llm/providers/anthropic.py`, `triforce/llm/providers/openai_compat.py`; new `triforce/llm/preferences.py`; new `triforce/llm/topic.py` (classifier + specialist matching); modifications to `triforce/llm/router.py` (precedence), `triforce/llm/registry.py` + `models.yaml` (external models, `specializes` tags), `triforce/llm/observability.py` (new fields); one new Executor tool in `triforce/tools/`.
- **Dependencies**: `httpx` (already required) is sufficient for both new providers — no `anthropic`/`openai` SDK needed. No new mandatory deps.
- **Interaction with in-flight work**: depends on `adopt-okf-knowledge` for the OKF `Preference` doc type (currently being implemented); builds directly on `add-specialized-llm-router`. Does NOT touch consolidation or journal code paths.
- **Cost/privacy**: external providers are only eligible when the request's privacy class allows cloud; `local-only` requests never reach them. Topic classification always runs locally or not at all — query content is never sent to a cloud model for classification.
- **Risk — classifier latency on the Executor's critical path**: the edge classification adds one local call (<50 ms target). Mitigation: topic stage is enabled per-policy (`topic_routing: true`), default ON for Dreamer/Judge (batch/background) and OFF for Executor until latency is measured.
- **Risk — stale user preferences**: an operator-pinned model may degrade or disappear. Mitigation: preferences carry the standard fallback — if the preferred model is unhealthy, the router logs the miss and falls through to the next precedence level instead of failing.
