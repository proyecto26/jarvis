# Tasks: add-model-preferences-and-topic-routing

## 1. External Providers

- [ ] 1.1 Implement `triforce/llm/providers/anthropic.py` (Messages API over httpx; `ANTHROPIC_API_KEY`; `health()` False without key/network, never raises)
- [ ] 1.2 Implement `triforce/llm/providers/openai_compat.py` (Chat Completions over httpx; configurable `base_url` + per-entry key env var, default `OPENAI_API_KEY`)
- [ ] 1.3 Register both in the provider registry (`triforce/llm/providers/registry.py`) and add external model entries (Claude, GPT, OpenRouter examples) to `models.yaml` with capabilities/tags
- [ ] 1.4 Tests: fixture-based `generate()` for both providers; missing-key and unreachable-endpoint scenarios return unhealthy without raising; `local-only` requests never consider external candidates

## 2. Model Preferences

- [ ] 2.1 Implement `triforce/llm/preferences.py`: `set_agent_model`, `clear_agent_model`, `get_preferences`; atomic `memory/model_prefs.json` store
- [ ] 2.2 OKF audit: write `type: Preference` doc with `agent`, `model_id`, `supersedes` link on every change; degrade to log-only when okf module unavailable
- [ ] 2.3 Executor tool `triforce/tools/model_tools.py` (`set_agent_model`, `clear_agent_model`, `get_model_config`) registered on the Executor agent
- [ ] 2.4 Tests: set/clear/persist across reload; supersedes chain in OKF docs; OKF-unavailable path still updates JSON; tool wrappers

## 3. Router Precedence

- [ ] 3.1 Refactor `Router.route()` into ordered resolvers: env force → user preference → topic specialist → policy scoring → on_no_candidate; first healthy hit wins
- [ ] 3.2 Add `preference_source` and `topic` to `RouteDecision` and to observability JSONL records (readers default missing fields to `policy`/`null`)
- [ ] 3.3 Unhealthy preferred model: log preference miss, fall through (never raise)
- [ ] 3.4 Tests: each precedence level in isolation; env beats user; user beats specialist; unchanged decision when levels 2-3 are empty (regression guard against current behavior); DANTE_ROUTER=off unaffected

## 4. Topic Routing

- [ ] 4.1 Implement `triforce/llm/topic.py`: `classify(text)` via `role:classifier` registry model (closed label set from `specializes` tags, ~200 ms timeout, None on any failure); `match_specialist(topic, candidates)`
- [ ] 4.2 Add `specializes` tag support to registry/`models.yaml`; add `topic_routing: bool` to policy schema + `SCHEMA.md`; enable for dreamer/judge policies, disable for executor
- [ ] 4.3 Wire the specialist resolver into `Router.route()` level 3 (only when policy opts in)
- [ ] 4.4 Tests: classification with fake classifier; specialist match beats policy scoring; no-specialist and classifier-down fall-through; executor default adds zero classifier calls

## 5. Documentation & Audit

- [ ] 5.1 Update `docs/llm-router.md` (or create if the original change hasn't) with the five-level precedence diagram, provider setup (API keys), preference tool usage, and how to add a specialist model + topic
- [ ] 5.2 Extend router-audit expectations: note in the Judge skill docs that `preference_source`/`topic` enable "do user pins / specialists outperform policy?" analyses
- [ ] 5.3 Full test suite green; smoke: import all new modules without optional deps installed
