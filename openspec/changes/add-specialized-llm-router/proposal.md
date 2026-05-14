## Why

DANTE today hardcodes a single Gemini model per Trinity role (`DREAMER_MODEL=gemini-2.0-pro-exp`, `JUDGE_MODEL=gemini-1.5-pro`, `EXECUTOR_MODEL=gemini-2.0-flash`). This is a one-dimensional optimization: it picks per-role *speed/reasoning tradeoff*, but it cannot pick the *right tool for the job*.

Two model families released in 2026 change the calculus for local-first agent systems:

- **NVIDIA Nemotron** — a family of open, locally-runnable reasoning models (Nano, Super, Ultra) explicitly designed for agentic tasks. Permissive license, optimized for tool use, runs on consumer GPUs at the Nano/Super tier. Refs: <https://developer.nvidia.com/nemotron>, <https://github.com/NVIDIA-NeMo/Nemotron>.
- **Google Gemma 4** — on-device / edge-class open models (1B / 4B / 12B / 27B), with the 1B tier explicitly tuned for mobile and edge agentic workloads. Refs: <https://deepmind.google/models/gemma/gemma-4/>, <https://ai.google.dev/gemma/docs/core>, <https://developer.nvidia.com/blog/bringing-ai-closer-to-the-edge-and-on-device-with-gemma-4>, <https://unsloth.ai/docs/models/gemma-4>.

Together with the existing Gemini cloud models, this gives DANTE three latency/cost/capability tiers it cannot currently choose between:

| Tier | Example | Latency | Cost | Best for |
|------|---------|---------|------|----------|
| **Edge / on-device** | Gemma 4 1B/4B (local) | <50 ms first token | $0 | Cheap classification, intent routing, contradiction detection |
| **Specialized local** | Nemotron Nano/Super (local GPU) | ~200 ms first token | $0 (electricity) | Deep reasoning with no privacy leak; long tool chains |
| **Frontier cloud** | Gemini 2.x Pro/Flash | ~500 ms + network | $$$ per token | Multi-modal, very long context, highest quality |

Two additional axes matter for DANTE specifically:
1. **Specialization via fine-tuning.** Unsloth/Gemma-4 docs show LoRA fine-tuning is now cheap enough to train task-specialized adapters (e.g. a Judge-tuned Gemma-4-4B for ethics evaluation, a Dreamer-tuned Nemotron for cross-domain synthesis). These adapters dominate generic frontier models on their narrow task while costing nothing to run.
2. **Local-first alignment.** The recent memory-system rewrite (commit `2734779`) committed DANTE to local-first storage. Hardcoded cloud LLMs are now the *only* mandatory external dependency — a router that prefers local models when they're capable enough closes that gap.

The proposal: add a **smart LLM router** that the Trinity agents query before each significant LLM call. The router picks the best model based on (a) task signature, (b) currently-loaded specialized adapters, (c) latency budget, (d) privacy class, and (e) local hardware availability. The existing Gemini config becomes the default fallback, so nothing regresses.

## What Changes

- Add `triforce/llm/` package with three modules:
  - `router.py` — the routing decision engine. Takes a `RouteRequest` (task type, agent name, privacy class, latency budget, max input/output tokens, requires_vision) and returns a `RouteDecision` (model_id, provider, adapter_id, reasoning).
  - `providers.py` — pluggable provider adapters (Gemini, Ollama-for-Nemotron, Ollama-for-Gemma, llama.cpp, vLLM-local). Each provider exposes a uniform `generate(messages, tools, params) -> Response` interface.
  - `registry.py` — declarative model registry (`MODELS = [Model(id="nemotron-nano-9b", provider="ollama", capabilities=["reasoning","tools"], context=128_000, ...)]`).
- Add `triforce/llm/adapters/` directory where fine-tuned LoRA adapters live (`judge-ethics-v1.safetensors`, etc.) plus a metadata file describing which task each adapter specializes in.
- Add `triforce/llm/policies/` — YAML policies per agent that declare *preferences* without hardcoding model IDs: e.g. `judge_filter.yaml` declares "prefer local reasoning model with ethics adapter; fall back to Gemini Pro if local unavailable."
- Modify `triforce/config.py` — replace fixed per-agent model strings with a `Config.MODEL_ROUTER` instance; preserve `DREAMER_MODEL`/`JUDGE_MODEL`/`EXECUTOR_MODEL` env overrides as *forced* selections that bypass the router (escape hatch).
- Modify `triforce/agents/{dreamer,judge,executor}/agent.py` — replace `model=Config.X_MODEL` with `model=Config.MODEL_ROUTER.for_agent("dreamer")`. The router returns a callable Gemini-compatible model surface so ADK doesn't change.
- Add `triforce/llm/observability.py` — every route decision is logged with reasoning to `journal/llm-routing/YYYY-MM-DD.jsonl` so the Judge can later audit whether the router's choices were correct.
- Add `triforce/agents/judge/skills-filter/router-audit/` ADK Skill — gives the Judge a method to evaluate router decisions during reflective mode (closing the self-improvement loop).
- Documentation: `docs/llm-router.md` explaining the routing policy DSL, how to add a model, how to fine-tune an adapter for a task.

## Capabilities

### New Capabilities

- **`llm-router`**: Declarative model selection per call — given a task signature and constraints, picks the best `(model, adapter)` pair from the registry. Pure function; testable in isolation; logs every decision.
- **`local-model-providers`**: Provider adapters for Nemotron (via Ollama or NeMo native), Gemma 4 (via Ollama, llama.cpp, or unsloth-served), with health-check + automatic fallback when a local backend is down.
- **`specialization-adapters`**: Storage and metadata for LoRA fine-tuned adapters. Adapters are tagged by *task* (`ethics-evaluation`, `dream-deepening`, `journal-entry-writer`, `contradiction-detection`) so the router can compose `(base-model, task-adapter)`.
- **`routing-policies`**: YAML policy files per agent/skill declaring routing *preferences* (privacy class, max latency, must-be-local, requires-tools). Policies are versioned in git; changes are reviewable.
- **`router-audit`**: Judge ADK Skill for reflective-mode evaluation of router decisions over time. Detects regressions ("router has been picking cloud model for `ethics-evaluation` 80% of the time despite local adapter being available — investigate").

### Modified Capabilities

- **`dreamer-agent`**: `model=` argument resolved via router; preference policy `dreamer.yaml` declares "prefer Nemotron Super for deep reasoning, fall back to Gemini Pro for vision-required dreams."
- **`judge-agent`**: Filter and collaborator each get their own routing policy. Filter prefers an ethics-adapted local model; collaborator prefers a model with strong long-context (for the dream loop).
- **`executor-agent`**: Routing policy `executor.yaml` strongly prefers low-latency local models (Gemma 4 4B / Nemotron Nano) since the Executor is on the user-facing critical path; cloud fallback is gated on `latency_budget_ms > 800`.
- **`operating-modes`**: Awake mode now runs through the router by default; Sleep mode allows higher-latency local models since there's no user waiting; Reflective mode prefers the same model that made the original decision (so router-audit can compare apples to apples).
- **`config`**: `Config.MODEL_ROUTER` replaces the three model strings; `DREAMER_MODEL`/`JUDGE_MODEL`/`EXECUTOR_MODEL` env vars become *forced overrides* with a warning logged.

## Impact

- **New code**: `triforce/llm/` package (~900 lines: router 250, providers 400, registry 80, policies loader 90, observability 80) + 4 YAML policy files + `docs/llm-router.md`.
- **Dependencies**: `ollama` Python client (already an optional dep), `pyyaml` (already transitively required by Google ADK), `httpx` (already required). Optional: `peft` + `transformers` only when serving LoRA adapters locally.
- **Infrastructure**: Optional local Ollama install (one binary, ~50 MB) for the local-model tiers. The router degrades gracefully if Ollama isn't running — it just always returns the cloud model.
- **Backward compatibility**: If `MODEL_ROUTER` is disabled (`DANTE_ROUTER=off`), the system falls back to today's hardcoded Gemini selection. Zero-regression escape hatch.
- **Cost model**: Once a task has a competent local adapter, the per-call cost drops from $0.001–$0.01 (Gemini) to $0 (local). For DANTE's projected workload (Dreamer runs every 6h, Executor on every user turn, Judge on every Executor turn), this is the single largest cost saver available.
- **Privacy**: New `privacy_class` field on each `RouteRequest`. `local-only` requests will refuse to fall back to cloud — the router raises rather than silently exfiltrating.
- **Phase ordering**: This depends on `trinity-phase-1` (need the three agents) and *interacts with* `trinity-temporal-durable-loop` (Temporal activities should record which model was chosen, for replay determinism). It does NOT depend on `trinity-phase-2-memory` or `trinity-phase-3-a2a`.
- **Risk: model drift across providers.** A judgment made by Gemini Pro and one made by Nemotron Super may differ even on identical prompts. Mitigation: the router-audit skill explicitly tracks decision-divergence between models for the same task, surfacing this to the Judge during reflective mode.
- **Risk: fine-tuning overhead.** Initially shipping with *zero* fine-tuned adapters — just base models. Adapters are a follow-up change. Router still has value on day 1 by picking the right *base* model.
