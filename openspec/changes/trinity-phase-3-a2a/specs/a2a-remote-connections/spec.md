## ADDED Requirements

### Requirement: Executor uses RemoteA2aAgent for Dreamer
In distributed mode, the Executor SHALL use ADK's `RemoteA2aAgent` to connect to the Dreamer service, passing the Dreamer's Agent Card (file path or URL) for capability discovery.

#### Scenario: Executor instantiates remote Dreamer
- **WHEN** `AGENT_MODE` is set to `"a2a"`
- **THEN** the Executor SHALL create a `RemoteA2aAgent` instance with `name="dreamer_agent"`, `description` matching the Dreamer's role, and `agent_card` pointing to the Dreamer's Agent Card location

#### Scenario: Executor calls Dreamer via A2A during sleep mode
- **WHEN** the sleep mode LoopAgent invokes the Dreamer
- **THEN** the Dreamer call SHALL be routed through the `RemoteA2aAgent`, sending dream context as an A2A message and receiving dream content in the response

### Requirement: Executor uses RemoteA2aAgent for Judge
In distributed mode, the Executor SHALL use ADK's `RemoteA2aAgent` to connect to the Judge service for both filter mode (awake) and collaborator mode (sleep) evaluations.

#### Scenario: Executor instantiates remote Judge
- **WHEN** `AGENT_MODE` is set to `"a2a"`
- **THEN** the Executor SHALL create a `RemoteA2aAgent` instance with `name="judge_agent"` and `agent_card` pointing to the Judge's Agent Card location

#### Scenario: Awake pipeline calls Judge filter via A2A
- **WHEN** the awake SequentialAgent runs and the Judge filter step executes
- **THEN** the filter request SHALL be sent as an A2A message to the Judge service, and the verdict/reasoning/action_weight SHALL be received in the A2A response

### Requirement: Dreamer uses RemoteA2aAgent for Judge in sleep loops
In distributed mode, the sleep LoopAgent SHALL use `RemoteA2aAgent` to call the Judge collaborator after each Dreamer iteration, maintaining the Dream-Judge feedback loop over A2A.

#### Scenario: Sleep loop iteration calls Judge remotely
- **WHEN** the Dreamer completes a dream iteration within the LoopAgent
- **THEN** the Judge collaborator SHALL be called via `RemoteA2aAgent` with the current dream state, and the Judge's response (deepening, depth, breakthrough) SHALL be received via A2A

#### Scenario: Judge exit_loop signal transmitted via A2A
- **WHEN** the Judge collaborator determines a breakthrough has been reached (dream_depth >= 3)
- **THEN** the exit_loop signal SHALL be communicated via the A2A response message, and the LoopAgent SHALL terminate the loop

### Requirement: Agent mode environment switch
The system SHALL support an `AGENT_MODE` environment variable that controls whether agents are instantiated as local ADK agents (`"local"`) or `RemoteA2aAgent` references (`"a2a"`).

#### Scenario: Local mode uses in-process agents
- **WHEN** `AGENT_MODE` is set to `"local"` or is not set
- **THEN** all agents SHALL be instantiated as local ADK `LlmAgent` instances communicating via session state (Phase 1 behavior)

#### Scenario: A2A mode uses remote agents
- **WHEN** `AGENT_MODE` is set to `"a2a"`
- **THEN** Dreamer and Judge SHALL be instantiated as `RemoteA2aAgent` references, and Executor SHALL remain a local `LlmAgent` that orchestrates remote calls

#### Scenario: Mixed mode for phased migration
- **WHEN** `AGENT_MODE` is set to `"a2a"` and `DREAMER_A2A_URL` is set but `JUDGE_A2A_URL` is not
- **THEN** only Dreamer SHALL be a `RemoteA2aAgent`; Judge SHALL remain a local agent — enabling incremental migration

### Requirement: A2A message payload conventions
A2A messages between Trinity agents SHALL encode session state data as structured JSON in the message content, using the same key names established in Phase 1 (`dream_seeds`, `judge_verdict`, `action_weight`, etc.).

#### Scenario: Dreamer receives context via A2A message
- **WHEN** the Executor sends a dream request to the Dreamer via A2A
- **THEN** the A2A message content SHALL include a JSON object with `dream_seeds`, `mode_context`, and any relevant session state as key-value pairs

#### Scenario: Judge response encodes verdict in A2A message
- **WHEN** the Judge completes an evaluation and responds via A2A
- **THEN** the A2A response message content SHALL include a JSON object with `judge_verdict`, `judge_reasoning`, and `action_weight` fields

#### Scenario: State key compatibility
- **WHEN** an agent receives an A2A message with state payload
- **THEN** the agent's A2A executor SHALL unpack the JSON payload into local session state using the same key names, ensuring agent prompts with `{ variable? }` templates continue to work without modification

### Requirement: Remote agent error handling
The Executor SHALL handle `RemoteA2aAgent` failures gracefully, degrading functionality rather than crashing when a remote agent is unreachable.

#### Scenario: Dreamer service unavailable
- **WHEN** the Executor attempts to call the Dreamer via A2A and the service is unreachable
- **THEN** the system SHALL log the failure and skip the dream cycle, informing the user that deep thinking is temporarily unavailable

#### Scenario: Judge service unavailable during awake mode
- **WHEN** the Executor attempts to call the Judge filter via A2A and the service is unreachable
- **THEN** the system SHALL log the failure and proceed with a default permissive verdict, allowing the Executor to act without Judge evaluation

#### Scenario: A2A timeout handling
- **WHEN** an A2A call exceeds the configured timeout (default 30 seconds for Judge, 120 seconds for Dreamer)
- **THEN** the system SHALL abort the call, log the timeout, and apply the same degraded-mode behavior as an unreachable service
