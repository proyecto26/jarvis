# Design: add-model-preferences-and-topic-routing

## Context

The router (`triforce/llm/`) resolves models via: `RouteRequest(agent=...)` → `load_policy(agent)` (YAML per agent in `policies/`) → registry scoring with fallback chain → `RouteDecision(model, reasoning)`. Providers implement an ABC (`providers/base.py`: `generate()`, `health(timeout_ms)`, `capabilities()`); today only `gemini.py` and `ollama.py` exist. Env vars `DREAMER_MODEL`/`JUDGE_MODEL`/`EXECUTOR_MODEL` act as forced overrides. Every decision is logged to `journal/llm-routing/YYYY-MM-DD.jsonl`.

Reference patterns studied in `examples/` (2026-07-12): hermes-agent's `/model [provider:model]` runtime switching over provider-agnostic endpoints; OpenClaw's per-agent model config with fallback chains.

The parallel change `adopt-okf-knowledge` introduces `triforce/memory/okf.py` (OKF documents: YAML frontmatter + Markdown, `OKFBundle` under `Config.KNOWLEDGE_DIR`).

## Goals / Non-Goals

**Goals:**
- Frontier models beyond Gemini (Anthropic, OpenAI-compatible endpoints) as registry candidates.
- Operator can set/clear a default model per agent at runtime; survives restarts; auditable.
- Content-aware dispatch to topic-specialized local models when they exist.
- Explicit, tested five-level precedence; today's behavior unchanged when new levels are absent.

**Non-Goals:**
- No LoRA adapter serving/fine-tuning (that remains the `specialization-adapters` follow-up of the original router change; this change only honors `specializes` tags however served).
- No per-conversation or per-message model switching UI — one preference per agent.
- No cloud-based topic classification, ever.
- No changes to consolidation, journal, or memory code paths.

## Decisions

### D1 — Raw `httpx` providers, no vendor SDKs
`anthropic.py` and `openai_compat.py` implement the existing `Provider` ABC with plain `httpx` calls (Messages API; Chat Completions API). Rationale: `httpx` is already a dependency; the ABC surface is tiny (`generate`, `health`, `capabilities`); vendor SDKs add heavy deps for features the router doesn't use. `openai_compat` takes a base URL so OpenAI, OpenRouter, vLLM, and LM Studio are all one provider. Alternative considered: LiteLLM — rejected as a large dependency that duplicates the router's own job (routing/fallback).

### D2 — Preferences as a small JSON runtime store + OKF audit docs
`triforce/llm/preferences.py` keeps `memory/model_prefs.json` (atomic writes, same pattern as `judge_beliefs.json`) as the fast runtime store: `{agent: {model_id, set_at, reason}}`. Every `set_agent_model()`/`clear_agent_model()` additionally writes an OKF `Preference` doc via `OKFBundle` (frontmatter: `type: Preference`, `agent`, `model_id`, `supersedes` link to the prior preference doc, `reason` in body). Rationale: mirrors the belief dual-store decision in `adopt-okf-knowledge` — JSON for the hot path, OKF for the human-legible bitácora. If `okf.py` is unavailable, preference setting still works (audit doc skipped with a log line) — graceful degradation invariant.

### D3 — Precedence implemented as ordered resolvers inside `Router.route()`
```
1. env force        (existing DREAMER_MODEL etc. — unchanged, logs preference_source=env)
2. user preference  (prefs store; skipped if model unhealthy/absent → log miss, fall through)
3. topic specialist (only if policy sets topic_routing: true; see D4)
4. policy scoring   (existing behavior, unchanged)
5. on_no_candidate  (existing behavior, unchanged)
```
Each resolver returns a candidate or `None`; the first hit wins and stamps `RouteDecision.preference_source`. Rationale: keeps `route()` a pure, testable decision function; each level is independently unit-testable. Alternative considered: preferences as generated policy YAML overrides — rejected because policies are git-versioned declarations of temperament, while preferences are runtime operator state; mixing them muddies review.

### D4 — Topic stage: classify-then-match, per-policy opt-in
`triforce/llm/topic.py`:
- `classify(text) -> str | None`: one call to a designated edge model (registry tag `role:classifier`, expected Gemma 4 1B via Ollama) with a constrained prompt returning one label from the topics declared in `models.yaml` (closed set — no free-form labels). Timeout ~200 ms; any failure → `None`.
- Registry entries gain optional `specializes: [<topic>, ...]`.
- `match_specialist(topic, candidates)` filters healthy candidates whose `specializes` contains the topic; ties broken by existing scoring.
- Policy schema gains `topic_routing: bool` (default `false`; SCHEMA.md updated). Default ON for `dreamer.yaml` and both judge policies, OFF for `executor.yaml` until latency is measured (proposal risk).
Rationale for closed label set: an open-vocabulary classifier invents labels that never match tags; the topic vocabulary lives next to the models that claim it. Alternative considered: embedding-similarity matching against adapter descriptions — deferred; heavier and unnecessary until there are real specialists.

### D5 — Executor tool, not a new mode
One new ADK tool in `triforce/tools/` (e.g. `model_tools.py`): `set_agent_model`, `clear_agent_model`, `get_model_config` — thin wrappers over `preferences.py`, registered on the Executor agent. The Judge is NOT consulted on preference changes (the operator outranks the Judge on model choice), but the change lands in the OKF bitácora where reflective mode will see it.

### D6 — Observability fields are additive
`observability.py` log records gain `preference_source` and `topic` (nullable). Router-audit (Judge skill) can then answer "do user-pinned models underperform policy picks?" — no schema migration needed for old JSONL lines (readers treat missing fields as `policy`/`null`).

## Risks / Trade-offs

- [Preferred model unhealthy at call time] → resolver 2 logs the miss and falls through; never raises. The miss count in routing logs surfaces stale preferences to router-audit.
- [Classifier adds latency to interactive path] → per-policy opt-in, OFF for Executor initially; 200 ms hard timeout; `None` on timeout falls through with zero added semantics.
- [Anthropic/OpenAI API drift vs raw httpx] → provider tests use recorded fixtures; `health()` failures just mark the provider unhealthy (router skips), so drift degrades to "model unavailable", never a crash.
- [Two stores diverge (JSON prefs vs OKF docs)] → JSON is authoritative for routing; OKF is audit-only; both written in one function; a divergence affects history, not behavior.
- [Closed topic vocabulary goes stale] → vocabulary lives in `models.yaml` next to `specializes` tags; adding a specialist model and its topic is one edit, reviewable in git.

## Migration Plan

1. Providers + registry entries land first (inert until models referenced by a policy/preference).
2. Preferences module + Executor tool (inert until operator sets one).
3. Precedence rewiring in `router.py` behind the existing `DANTE_ROUTER` flag — when the flag is off, nothing changes at all.
4. Topic stage last, opt-in per policy.
Rollback: each step is independently revertible; disabling `DANTE_ROUTER` restores hardcoded per-role models throughout.

## Open Questions

- Should `specializes` topics eventually be OKF `Question`/`Learning`-driven (the Dreamer proposing new specialist topics from observed workload)? Deferred to router-audit follow-up.
- Preference scope: per `agent` matches the four policy names (`dreamer`, `executor`, `judge_filter`, `judge_collaborator`) — is a single `judge` alias covering both judge policies more ergonomic for the operator? Decide during implementation with the tool's UX.
