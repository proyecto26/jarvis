# LLM Router Spec

## ADDED Requirements

### Requirement: Route Decision API

The router SHALL expose a pure function `route(request: RouteRequest) -> RouteDecision` that takes a structured task description and returns the selected model, adapter, provider, and the reasoning trace.

#### Scenario: Local model with task-specific adapter is available

- **WHEN** the registry contains a local model marked `available=true` AND a LoRA adapter tagged with the requested `task_type`
- **THEN** the router returns that `(model, adapter)` pair
- **AND** the `RouteDecision.reasoning` field cites both the model match and the adapter match
- **AND** no cloud API call is made

#### Scenario: Local model is unavailable but cloud fallback is allowed

- **WHEN** no local model in the registry has `available=true`
- **AND** `request.privacy_class` is `cloud-ok`
- **THEN** the router returns the configured cloud fallback (Gemini)
- **AND** the decision is logged with reason `local_unavailable_cloud_allowed`

#### Scenario: Local-only privacy class with no local model available

- **WHEN** `request.privacy_class == "local-only"`
- **AND** no local model satisfies the request
- **THEN** the router raises `LocalOnlyRouteFailure` with a structured error
- **AND** no cloud call is made under any circumstance

### Requirement: Provider Health Checks

The router SHALL validate provider health before returning a `RouteDecision`. A provider is considered healthy if it responds to a lightweight `health()` probe within a configurable timeout (default 200 ms).

#### Scenario: Local Ollama is selected but the daemon is not running

- **WHEN** the router selects a model whose provider is `ollama`
- **AND** the Ollama daemon does not respond to `health()` within timeout
- **THEN** the router demotes that model in the candidate list
- **AND** retries selection with the next-best candidate

### Requirement: Routing Policies are Declarative YAML

Each agent and skill MAY define a routing policy in `triforce/llm/policies/` as a YAML file. The policy SHALL declare *preferences* and *constraints*, not specific model IDs.

#### Scenario: Policy declares preferred capabilities

- **WHEN** a policy YAML lists `prefer: [reasoning, tools]` and `must_have: [function_calling]`
- **THEN** the router scores each registry model by capability match
- **AND** filters out models lacking `function_calling`

#### Scenario: Policy declares latency budget

- **WHEN** a policy YAML sets `max_latency_ms: 800`
- **THEN** the router excludes any model whose measured P95 latency exceeds 800 ms
- **AND** if no candidate remains, falls back per the policy's `on_no_candidate` directive (fail, escalate, or relax constraint)

### Requirement: Decision Observability

Every route decision SHALL be logged as a JSONL record to `journal/llm-routing/YYYY-MM-DD.jsonl`.

#### Scenario: Successful local route is logged

- **WHEN** the router returns a decision
- **THEN** a record `{timestamp, request_signature, decision, candidates_considered, reasoning, latency_budget_ms}` is appended
- **AND** the file uses atomic writes to prevent corruption (write to temp + rename)

#### Scenario: Privacy-class violation is logged at WARNING

- **WHEN** a `local-only` request fails because no local model is available
- **THEN** a record with `level: warning` and `outcome: refused_cloud_fallback` is appended
- **AND** the Judge's `router-audit` skill surfaces these during the next reflective session

### Requirement: Backward-Compatible Escape Hatch

The router SHALL be disable-able via environment variable `DANTE_ROUTER=off`, restoring the pre-router hardcoded model selection.

#### Scenario: Router disabled — falls back to legacy behavior

- **WHEN** `DANTE_ROUTER=off`
- **THEN** `Config.MODEL_ROUTER.for_agent("executor")` returns the legacy `EXECUTOR_MODEL` string
- **AND** no provider health checks are performed
- **AND** no routing log file is created

#### Scenario: Forced per-agent override via env

- **WHEN** `EXECUTOR_MODEL=nemotron-nano-9b` is explicitly set
- **THEN** the router honors it as a forced override
- **AND** logs a warning that the override bypasses normal routing logic
