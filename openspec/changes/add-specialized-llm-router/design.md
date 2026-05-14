# Design — Specialized LLM Router

## Context

DANTE today picks LLMs in exactly one place: `triforce/config.py`, hardcoding one Gemini model per Trinity role. This is fine for an MVP but it precludes three things the recent work points toward:

1. The local-first memory rewrite (commit `2734779`) made it so the only hard external dependency left is the LLM.
2. NVIDIA Nemotron and Google Gemma 4 (both released 2026) put credible local agentic reasoning on consumer GPUs for the first time.
3. The `autoresearch.md` learnings showed weighted RRF and tiered fallback work well — the same pattern applies to model selection.

This design proposes a router that is **pure, declarative, and observable**. Pure: routing decisions are a function of (request, registry, policy, provider health) — no hidden state. Declarative: policies live in YAML, not code. Observable: every decision logs to the journal so the Judge can audit the router itself.

## Goals

- Make model selection a first-class decision (not a config string).
- Enable graceful fallback: prefer local → fall back to cloud → respect privacy class.
- Open the door to task-specialized LoRA adapters (Judge-tuned, Dreamer-tuned, etc.) without touching agent code.
- Preserve byte-identical legacy behavior behind a single env var.
- Stay compatible with Temporal replay determinism.

## Non-Goals

- Training LoRA adapters (separate change; just lay the directory + manifest schema).
- Multi-tenant cost optimization (we're single-user).
- Cross-provider streaming abstraction (each provider streams natively; the router doesn't intercept tokens).
- "Mixture of experts" runtime model swapping mid-turn — selection is per call, not per token.

## Architecture

```
                    ┌─────────────────────┐
   Agent.run() ───▶ │   Config.MODEL_ROUTER.for_agent("executor")   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │      Router         │
                    │  pure function      │
                    └──────────┬──────────┘
                               │ reads
                               ▼
              ┌──────────┬────────────┬────────────────┐
              │ Registry │  Policies  │ Provider Health │
              │ models.  │ executor.  │  (live probes)  │
              │  yaml    │  yaml      │                 │
              └──────────┴────────────┴────────────────┘
                               │ returns
                    ┌──────────▼──────────┐
                    │   RouteDecision     │
                    │ model, adapter,     │
                    │ provider, reasoning │
                    └──────────┬──────────┘
                               │ logs
                               ▼
                ┌──────────────────────────┐
                │ journal/llm-routing/     │
                │  YYYY-MM-DD.jsonl        │
                └──────────────────────────┘
```

## Policy DSL — Worked Example

`triforce/llm/policies/executor.yaml`:

```yaml
agent: executor
default_privacy_class: cloud-ok
max_latency_ms: 800
prefer:
  - local
  - tools
  - low_cost
must_have:
  - function_calling
fallback_chain:
  - capability_match: [reasoning, tools]
    privacy_class: cloud-ok
  - capability_match: [tools]
    privacy_class: cloud-ok
on_no_candidate: error      # alt: relax, escalate-to-judge
```

The router walks `fallback_chain` top-to-bottom, picking the first candidate that:
- has all `must_have` capabilities,
- is within the privacy class,
- passes provider health,
- meets the latency budget.

## Why This Is Worth Building

Three concrete savings from day 1, even before any fine-tuning:

| Workload | Today (Gemini) | After router (local where viable) |
|----------|----------------|-----------------------------------|
| Executor short-turn classification | ~$0.001/call × ~100/day | Gemma 4 4B local — $0 |
| Dreamer 6-h scheduled cycles | Gemini 2.0 Pro Exp × 4/day | Nemotron Super local — $0 |
| Contradiction check (TF-IDF + Judge ratification) | Gemini 1.5 Pro × N | Gemma 4 1B local — $0 |

The Judge filter on user-visible decisions stays on Gemini Pro by default — that's where latency budget and quality matter most. The router *gates* the cheap calls behind local execution, while preserving cloud for the calls that matter.

## Tradeoffs

- **Complexity floor.** A router is more code than a config string. We accept that because the existing 4 hardcoded `MODEL` env vars are already three special-cases waiting to multiply when Nemotron/Gemma adapters land. Better to land the abstraction once.
- **Model drift across providers.** A Gemini judgment ≠ a Nemotron judgment even with the same prompt. The router-audit Skill is the explicit mitigation — the Judge reviews divergence over time.
- **Latency variance.** Local first-token latency depends on GPU thermals, model load state, etc. The router treats latency as a *budget*, not a guarantee, and falls back to cloud when the budget is exceeded.
- **Temporal replay determinism.** A workflow that originally ran on Gemini Pro must replay on Gemini Pro even after we add Nemotron. Solution: persist `routing_decision_id` in the Activity input; replay uses the recorded id and bypasses the router.

## Risks We Accept

- **Local-only refusal can deadline-stall a session** if the user revokes cloud and has no local model. We log this loudly rather than silently falling back. The user-facing failure is the *point* of `local-only`.
- **Adapter manifest is YAML, which has known footguns.** We use strict-mode pyyaml + a JSON-schema validator on load; a malformed adapter manifest fails fast.

## Open Questions

- **Q1:** Should the router itself be an ADK Skill so the Judge can override its decisions in real time? *Initial answer: no.* Routing must be deterministic and fast (<1 ms). Letting an LLM influence it re-introduces the same coupling we're trying to break.
- **Q2:** Should the router cache decisions per `(request_signature, hour)` to amortize health-check cost? *Yes, but add only after measuring.* Don't preempt with a TTL cache before we see the latency profile.
- **Q3:** Should Temporal workflows pay the cost of recording the model id even when `DANTE_ROUTER=off`? *Yes — it's two strings of metadata; the future-proofing is worth it.*

## Related Work in the Repo

- **`autoresearch.md`** — the memory-system autoresearch loop's "weighted RRF" pattern is structurally identical to fallback-chain scoring here.
- **`trinity-temporal-durable-loop`** — the Activity layer is where router decisions need to be persisted for replay.
- **`trinity-adk-skills`** — the router-audit Skill follows the same `SkillToolset` pattern established there.
