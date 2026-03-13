## ADDED Requirements

### Requirement: Root dispatcher agent
The system SHALL define a root agent named `jarvis` as an ADK `LlmAgent` that routes incoming interactions to the appropriate operating mode sub-agent based on context analysis.

#### Scenario: Root agent routes to awake mode
- **WHEN** the user sends a message requiring action or a response
- **THEN** the root agent transfers to the `awake_pipeline` sub-agent

#### Scenario: Root agent routes to sleep mode
- **WHEN** the user explicitly requests deep thinking (e.g., "dream", "think deeply", "explore") or a scheduled invocation triggers sleep
- **THEN** the root agent transfers to the `dream_state` sub-agent

#### Scenario: Root agent routes to reflective mode
- **WHEN** the user requests reflection (e.g., "let's reflect") or a recent high-weight action has completed
- **THEN** the root agent transfers to the `reflective_session` sub-agent

### Requirement: Awake mode as SequentialAgent
The awake operating mode SHALL be implemented as an ADK `SequentialAgent` named `awake_pipeline` containing two sub-agents in order: `judge_filter` followed by `executor`.

#### Scenario: Awake pipeline execution order
- **WHEN** awake mode is activated
- **THEN** the Judge filter agent runs first, populates verdict state, and then the Executor agent runs using the Judge's output

#### Scenario: Awake pipeline completes without user turn between agents
- **WHEN** the SequentialAgent runs
- **THEN** both sub-agents execute in sequence without breaking for user input between them

### Requirement: Sleep mode as LoopAgent
The sleep operating mode SHALL be implemented as an ADK `LoopAgent` named `dream_state` containing two sub-agents: `dreamer` followed by `judge_collaborator`. The loop SHALL have `max_iterations` set to 8 as a safety bound.

#### Scenario: Sleep loop iterates dreamer and judge
- **WHEN** sleep mode is activated
- **THEN** the Dreamer runs, then the Judge-as-collaborator runs, and this sequence repeats until `exit_loop` is called or `max_iterations` is reached

#### Scenario: Sleep loop bounded by max_iterations
- **WHEN** the Judge-collaborator never calls `exit_loop`
- **THEN** the loop terminates after 8 iterations

### Requirement: Reflective mode as LlmAgent
The reflective operating mode SHALL be implemented as an ADK `LlmAgent` named `reflective_session` that processes recent experiences using the Judge's reasoning capability with access to journal context.

#### Scenario: Reflective session processes recent events
- **WHEN** reflective mode is activated
- **THEN** the reflective agent reviews recent execution outcomes and judge decisions from session state, producing learnings and updated beliefs

### Requirement: Mode context in session state
The root agent SHALL maintain a `mode_context` key in session state that tracks the current operating mode and relevant transition context.

#### Scenario: Mode context updated on transition
- **WHEN** the root agent routes to any operating mode
- **THEN** the `mode_context` state key is updated with the current mode name and transition reason

### Requirement: Post-sleep handoff to executor
When the `dream_state` LoopAgent completes, the root agent SHALL ensure the `breakthrough` state value (if any) is available for the Executor to present to the user.

#### Scenario: Breakthrough available after sleep
- **WHEN** the dream_state completes with a `breakthrough` in state
- **THEN** the root agent routes to the Executor (or awake pipeline) with the breakthrough context available in state

### Requirement: ADK run compatibility
The root agent SHALL be defined in `triforce/root_agent.py` following ADK conventions so that `adk run triforce` discovers and runs it.

#### Scenario: ADK CLI discovery
- **WHEN** a user runs `adk run triforce` from the project root
- **THEN** ADK discovers the `root_agent` in `triforce/root_agent.py` and starts an interactive session

### Requirement: Python module entry point
The system SHALL provide a `triforce/__main__.py` that allows running with `python -m triforce`.

#### Scenario: Module execution
- **WHEN** a user runs `python -m triforce`
- **THEN** the system starts the root agent in an interactive session
