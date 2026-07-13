# Delta Spec: llm-router (add-model-preferences-and-topic-routing)

## ADDED Requirements

### Requirement: Five-Level Routing Precedence

The router SHALL resolve every request through an explicit, ordered precedence: (1) environment force override, (2) user runtime preference, (3) topic specialist match, (4) policy scoring with fallback chain, (5) the policy's `on_no_candidate` action. The first level producing a healthy candidate SHALL win, and levels 2 and 3 SHALL be no-ops when no preference/specialist exists, preserving pre-change behavior exactly.

#### Scenario: User preference outranks policy scoring

- **WHEN** a preference `judge_filter → claude-opus-4-8` is set and `JUDGE_MODEL` is not set
- **THEN** the router returns `claude-opus-4-8` regardless of policy scoring
- **AND** the decision records `preference_source: user`

#### Scenario: Env force outranks user preference

- **WHEN** `JUDGE_MODEL` is set in the environment and a user preference exists for the same agent
- **THEN** the env model wins and the decision records `preference_source: env`

#### Scenario: Unhealthy preferred model falls through

- **WHEN** the user-preferred model's provider fails its health check
- **THEN** the router logs a preference miss and continues to the topic-specialist and policy levels
- **AND** the request does not fail because of the stale preference

#### Scenario: No preference, no specialist — unchanged behavior

- **WHEN** no env override, no user preference, and no specialist match exist for a request
- **THEN** the router's decision is identical to the pre-change policy-scoring decision

## MODIFIED Requirements

### Requirement: Decision Observability

Every route decision SHALL be logged as a JSONL record to `journal/llm-routing/YYYY-MM-DD.jsonl`. Records SHALL include `preference_source` (`env` | `user` | `specialist` | `policy`) and `topic` (the classified topic label, or `null` when classification did not run or failed). Readers SHALL treat records missing these fields (pre-change lines) as `preference_source: policy`, `topic: null`.

#### Scenario: Successful local route is logged

- **WHEN** the router returns a decision
- **THEN** a record `{timestamp, request_signature, decision, candidates_considered, reasoning, latency_budget_ms, preference_source, topic}` is appended
- **AND** the file uses atomic writes to prevent corruption (write to temp + rename)

#### Scenario: Privacy-class violation is logged at WARNING

- **WHEN** a `local-only` request fails because no local model is available
- **THEN** a record with `level: warning` and `outcome: refused_cloud_fallback` is appended
- **AND** the Judge's `router-audit` skill surfaces these during the next reflective session

#### Scenario: Specialist route is attributable

- **WHEN** a topic specialist wins the route
- **THEN** the record carries `preference_source: specialist` and the matched `topic`
- **AND** router-audit can compare specialist outcomes against policy picks for the same topic
