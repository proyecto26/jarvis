## MODIFIED Requirements

### Requirement: Root dispatcher agent
The system SHALL define a root agent named `jarvis` as an ADK `LlmAgent` that routes incoming interactions to the appropriate operating mode sub-agent based on context analysis. In distributed mode (`AGENT_MODE=a2a`), the root agent SHALL route to operating mode sub-agents that use `RemoteA2aAgent` for Dreamer and Judge instead of local agent instances.

#### Scenario: Root agent routes to awake mode
- **WHEN** the user sends a message requiring action or a response
- **THEN** the root agent transfers to the `awake_pipeline` sub-agent

#### Scenario: Root agent routes to sleep mode
- **WHEN** the user explicitly requests deep thinking (e.g., "dream", "think deeply", "explore") or a scheduled invocation triggers sleep
- **THEN** the root agent transfers to the `dream_state` sub-agent

#### Scenario: Root agent routes to reflective mode
- **WHEN** the user requests reflection (e.g., "let's reflect") or a recent high-weight action has completed
- **THEN** the root agent transfers to the `reflective_session` sub-agent

#### Scenario: Root agent uses remote sub-agents in A2A mode
- **WHEN** `AGENT_MODE` is set to `"a2a"`
- **THEN** the operating mode sub-agents SHALL use `RemoteA2aAgent` references for Dreamer and Judge, while maintaining the same routing logic

### Requirement: Sleep mode as LoopAgent
The sleep operating mode SHALL be implemented as an ADK `LoopAgent` named `dream_state` containing two sub-agents: `dreamer` followed by `judge_collaborator`. The loop SHALL have `max_iterations` set to 8 as a safety bound. In distributed mode, the sub-agents SHALL be `RemoteA2aAgent` instances communicating over A2A protocol.

#### Scenario: Sleep loop iterates dreamer and judge
- **WHEN** sleep mode is activated
- **THEN** the Dreamer runs, then the Judge-as-collaborator runs, and this sequence repeats until `exit_loop` is called or `max_iterations` is reached

#### Scenario: Sleep loop bounded by max_iterations
- **WHEN** the Judge-collaborator never calls `exit_loop`
- **THEN** the loop terminates after 8 iterations

#### Scenario: Sleep loop uses A2A for remote agents
- **WHEN** sleep mode is activated with `AGENT_MODE=a2a`
- **THEN** each iteration SHALL call the Dreamer and Judge services via A2A JSON-RPC 2.0, with dream state encoded in A2A message payloads
