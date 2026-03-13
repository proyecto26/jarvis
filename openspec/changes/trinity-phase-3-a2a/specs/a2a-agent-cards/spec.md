## ADDED Requirements

### Requirement: Dreamer Agent Card
The system SHALL define an Agent Card file (`dreamer/agent.json`) for the Dreamer agent that describes its capabilities, input/output modes, skills, and service URL following the A2A protocol Agent Card schema.

#### Scenario: Dreamer Agent Card contains required fields
- **WHEN** the Dreamer Agent Card is loaded
- **THEN** it SHALL contain `name` as `"dreamer_agent"`, `description` describing unconstrained idea generation, `version`, `url` pointing to the Dreamer service endpoint, `defaultInputModes` including `"application/json"`, `defaultOutputModes` including `"application/json"`, and at least one entry in `skills`

#### Scenario: Dreamer Agent Card declares dream generation skill
- **WHEN** the Dreamer Agent Card's `skills` array is inspected
- **THEN** it SHALL contain a skill with `id` `"generate_dreams"`, a human-readable `name` and `description`, and `tags` including `"dreaming"` and `"ideation"`

### Requirement: Judge Agent Card
The system SHALL define an Agent Card file (`judge/agent.json`) for the Judge agent that describes its dual-mode capabilities (filter and collaborator), input/output modes, skills, and service URL.

#### Scenario: Judge Agent Card contains required fields
- **WHEN** the Judge Agent Card is loaded
- **THEN** it SHALL contain `name` as `"judge_agent"`, `description` describing conscience and evaluation capabilities, `version`, `url` pointing to the Judge service endpoint, `defaultInputModes` including `"application/json"`, `defaultOutputModes` including `"application/json"`, and at least two entries in `skills`

#### Scenario: Judge Agent Card declares filter and collaborator skills
- **WHEN** the Judge Agent Card's `skills` array is inspected
- **THEN** it SHALL contain a skill with `id` `"filter_evaluate"` for awake-mode filtering and a skill with `id` `"collaborate_dream"` for sleep-mode dream collaboration

### Requirement: Executor Agent Card
The system SHALL define an Agent Card file (`executor/agent.json`) for the Executor agent that describes its action execution capabilities, input/output modes, skills, and service URL.

#### Scenario: Executor Agent Card contains required fields
- **WHEN** the Executor Agent Card is loaded
- **THEN** it SHALL contain `name` as `"executor_agent"`, `description` describing fast frontline action execution, `version`, `url` pointing to the Executor service endpoint, `defaultInputModes` including `"text/plain"` and `"application/json"`, `defaultOutputModes` including `"text/plain"` and `"application/json"`, and at least one entry in `skills`

### Requirement: Agent Card URL configuration
Each Agent Card's `url` field SHALL be configurable via environment variables (`DREAMER_A2A_URL`, `JUDGE_A2A_URL`, `EXECUTOR_A2A_URL`) to support different deployment environments (local Docker, Cloud Run).

#### Scenario: Agent Card URL defaults to local Docker endpoint
- **WHEN** no environment variable override is set
- **THEN** the Agent Card `url` SHALL default to the local Docker Compose endpoint (e.g., `http://dreamer:8001/a2a/dreamer_agent`)

#### Scenario: Agent Card URL overridden for Cloud Run
- **WHEN** `DREAMER_A2A_URL` is set to a Cloud Run URL
- **THEN** the Dreamer Agent Card's `url` SHALL reflect the Cloud Run endpoint

### Requirement: Agent Card version field
Each Agent Card SHALL include a `version` field following semantic versioning (e.g., `"1.0.0"`) that is updated when the agent's skills or interface change.

#### Scenario: Agent Card version matches deployment
- **WHEN** an Agent Card is served by an A2A server
- **THEN** the `version` field SHALL match the deployed agent's capability version
