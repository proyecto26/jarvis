# Routing Policy Schema

Each agent (or named call site) gets one YAML policy under
`triforce/llm/policies/`. The policy declares **preferences and constraints**,
not specific model IDs — the router walks the registry and the fallback chain
to pick the actual model at call time.

## Top-level fields

```yaml
agent: string                  # required — matches RouteRequest.agent
default_privacy_class: enum    # cloud-ok | local-preferred | local-only
max_latency_ms: int            # latency budget; candidates exceeding this are dropped
must_have: [string, ...]       # capabilities the model MUST declare
prefer: [string, ...]          # capabilities to favor in scoring (additive)
prefer_tags: [string, ...]     # tags to favor (e.g. "family:nemotron")
fallback_chain: [step, ...]    # ordered relaxations to try
on_no_candidate: enum          # error | escalate | use_default_gemini
```

## fallback_chain step

A step relaxes constraints to find a candidate. Steps are tried top-to-bottom.

```yaml
- capability_match: [reasoning, tools]   # required capabilities at this step
  privacy_class: cloud-ok                # privacy class override for this step
  prefer_local: true                     # bias toward local even when cloud is OK
  max_latency_ms: 1500                   # optional step-level latency override
```

## `on_no_candidate` enum

- `error` — raise `NoCandidateError` (fail fast; the caller must handle it)
- `escalate` — escalate to the Judge for manual model selection (skill hook)
- `use_default_gemini` — fall back to the registry's `gemini-3.5-flash` regardless

## Worked example

```yaml
agent: executor
default_privacy_class: cloud-ok
max_latency_ms: 800
prefer: [low_latency, tools]
must_have: [function_calling]
fallback_chain:
  - capability_match: [reasoning, tools]
    prefer_local: true
  - capability_match: [tools]
    privacy_class: cloud-ok
on_no_candidate: use_default_gemini
```

This says: "I'm the Executor; I need function calling; I want low latency.
First try a local reasoning+tools model; if none, try any cloud tools model;
if everything fails, use Gemini 1.5 Pro as a last resort."
