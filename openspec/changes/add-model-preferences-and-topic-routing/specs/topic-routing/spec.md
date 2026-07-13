# Spec: topic-routing

## ADDED Requirements

### Requirement: Local Closed-Set Topic Classification

The system SHALL classify request content into a topic using a locally-served edge model (registry tag `role:classifier`) constrained to a closed label set derived from the `specializes` tags declared in `models.yaml`. Classification SHALL never send content to a cloud model, SHALL enforce a hard timeout (~200 ms), and SHALL return no topic on any failure.

#### Scenario: Query classified into a declared topic

- **WHEN** a request's content matches a topic that at least one registry model declares in `specializes`
- **THEN** `classify()` returns that label from the closed set

#### Scenario: Classifier unavailable — routing proceeds untouched

- **WHEN** no `role:classifier` model is healthy or the call times out
- **THEN** classification returns no topic and the route resolves exactly as if topic routing were disabled

### Requirement: Specialist Matching via `specializes` Tags

Registry entries MAY declare `specializes: [<topic>, ...]`. When a request's classified topic matches a healthy candidate's `specializes` list, that candidate SHALL outrank generic policy scoring (precedence level 3), with ties broken by the existing scoring function.

#### Scenario: Fine-tuned local model wins its topic

- **WHEN** a request is classified as topic `ethics-evaluation` and a local Gemma 4 entry declares `specializes: [ethics-evaluation]`
- **THEN** that model wins the route with `preference_source: specialist`

#### Scenario: No specialist for the topic

- **WHEN** a topic is classified but no healthy candidate declares it
- **THEN** routing falls through to policy scoring with no penalty

### Requirement: Topic Routing is Per-Policy Opt-In

The policy schema SHALL gain a `topic_routing` boolean (default `false`). The stage SHALL run only when the resolved policy enables it. Initial defaults: enabled for `dreamer` and both judge policies; disabled for `executor` until classification latency on the interactive path is measured.

#### Scenario: Executor skips classification by default

- **WHEN** the Executor routes a request under the default policies
- **THEN** no classifier call is made and no latency is added

#### Scenario: Policy enables the stage

- **WHEN** `dreamer.yaml` sets `topic_routing: true` and a Dreamer request arrives
- **THEN** the classifier runs before policy scoring
