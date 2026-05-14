# Agent Model Selection Spec

## ADDED Requirements

### Requirement: Agents Resolve Models via Router

Each Trinity agent (Dreamer, Judge filter, Judge collaborator, Executor) SHALL resolve its `model=` parameter through `Config.MODEL_ROUTER.for_agent(agent_name)` rather than reading a hardcoded environment variable directly.

#### Scenario: Executor resolves model via router at construction time

- **WHEN** the executor agent module is imported
- **AND** `DANTE_ROUTER` is unset or `on`
- **THEN** `Config.MODEL_ROUTER.for_agent("executor")` is called
- **AND** the returned model surface is passed to the ADK `Agent(model=...)` constructor

#### Scenario: Reflective mode preserves originating model

- **WHEN** Reflective mode reviews a past decision
- **AND** the journal entry records which model made the original decision
- **THEN** the same model is re-routed for the reflective evaluation
- **AND** the router-audit skill compares the two decisions for divergence

### Requirement: Privacy Class Per Agent

Each agent's policy SHALL declare a default `privacy_class` for routine calls. The Judge filter defaults to `cloud-ok`; the Executor defaults to `cloud-ok`; the Dreamer defaults to `local-preferred`; reflective-mode calls default to `local-only`.

#### Scenario: Dreamer prefers local but allows cloud for vision

- **WHEN** the Dreamer is generating a non-multimodal dream cycle
- **THEN** the router prefers local Nemotron/Gemma over Gemini
- **AND** falls back to Gemini Pro only if no local reasoning model is available

#### Scenario: Reflective mode refuses cloud

- **WHEN** Reflective mode reviews a sensitive past decision
- **AND** the policy declares `privacy_class: local-only`
- **THEN** the router refuses to route to cloud
- **AND** if no local model is available, the reflective session is deferred rather than leaking data

### Requirement: Router Decisions are Recorded in the Journal

Every LLM call that affects journal state SHALL include the `routing_decision_id` in the journal entry, so future audits can trace which model produced which artifact.

#### Scenario: Judgment entry includes router decision id

- **WHEN** the Judge writes a `Judgment` entry to the journal
- **THEN** the entry's metadata SHALL include `routing_decision_id: <id>` matching a record in `journal/llm-routing/YYYY-MM-DD.jsonl`

#### Scenario: BeliefMutation links to its router decision

- **WHEN** a BeliefMutation is written
- **THEN** the mutation record SHALL include `routing_decision_id` so the SSGM audit can detect "this belief was created by an under-qualified model" patterns
