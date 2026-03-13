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

---

## Inter-Agent Communication Model Evolution

This section clarifies how agent communication evolves across phases, providing the architectural bridge from Phase 1 to Phase 3.

### Phase 1: ADK Native Session State (Same Process, No Network)

In Phase 1, all three Trinity agents (Dreamer, Judge, Executor) run within a **single Python process** using Google ADK's native multi-agent primitives. Communication happens entirely through **ADK session state** (`tool_context.state`):

- **Mechanism**: `tool_context.state` — a shared in-memory dictionary scoped to the session
- **Transport**: None (same process, direct memory access)
- **Key conventions**:
  - Awake pipeline: `judge_verdict`, `judge_reasoning`, `action_weight`
  - Sleep loop: `dream_seeds`, `dream_deepening`, `dream_depth`, `breakthrough`
  - Executor context: `executor_guidance`, `execution_outcome`
  - Persistent: `judge_beliefs` (loaded from file at session start)
- **Agent wiring**: ADK `sub_agents` parameter — local `LlmAgent` instances nested within `SequentialAgent`, `LoopAgent`, etc.
- **Prompt data flow**: Agent instructions use `{ variable? }` templates that resolve from session state at zero cost
- **Latency**: Negligible (in-process function calls)
- **How to run**: `adk run triforce` or `python -m triforce`

### Phase 3: A2A Protocol (Independent Services, JSON-RPC 2.0, Agent Cards)

In Phase 3, each Trinity agent is deployed as an **independent A2A-compatible service** communicating over the **Agent-to-Agent (A2A) protocol**:

- **Mechanism**: A2A protocol — JSON-RPC 2.0 over HTTPS
- **Transport**: HTTP network calls between independent service endpoints
- **Discovery**: Each agent publishes an **Agent Card** (`agent.json`) describing its name, capabilities, skills, input/output modes, and service URL
- **Agent wiring**: ADK `RemoteA2aAgent` — reads Agent Cards and routes calls to remote A2A servers
- **State translation**: Session state keys are serialized as JSON in A2A message payloads; the receiving agent's `A2aAgentExecutor` unpacks them into local session state
- **Prompt data flow**: Same `{ variable? }` templates — prompts don't change, only the transport layer changes
- **Latency**: 50-200ms per hop (acceptable for non-real-time operations like dream loops)
- **Deployment**: Cloud Run (production), Docker Compose (local development)
- **Migration order**: Dreamer first (heavy model, scheduled, non-latency-critical) → Judge second (medium model, event-driven) → Executor stays as frontline client
- **Cross-framework**: Any A2A-compatible agent (LangChain, CrewAI, custom) can replace a Trinity member by serving a compatible Agent Card

### Evolution Path: Phase 1 → Phase 3

| Aspect | Phase 1 (Local) | Phase 3 (Distributed) |
|--------|-----------------|----------------------|
| **Process model** | Single Python process | Independent services per agent |
| **Communication** | ADK session state (in-memory) | A2A JSON-RPC 2.0 (HTTPS) |
| **Agent discovery** | `sub_agents` parameter (compile-time) | Agent Cards (runtime discovery) |
| **Agent instantiation** | `LlmAgent(...)` | `RemoteA2aAgent(agent_card=...)` |
| **State passing** | Direct `tool_context.state` read/write | JSON payload in A2A messages → local state |
| **Prompt templates** | `{ variable? }` from session state | Same (state unpacked from A2A messages) |
| **Deployment** | `adk run triforce` | `docker compose up` / Cloud Run |
| **Scaling** | All agents share one process | Each agent scales independently |
| **Framework lock-in** | ADK only | Any A2A-compatible framework |
| **Mode switch** | N/A (default) | `AGENT_MODE=local` (Phase 1) vs `AGENT_MODE=a2a` (Phase 3) |

The transition is **backward-compatible**: setting `AGENT_MODE=local` (or leaving it unset) preserves exact Phase 1 behavior. The same codebase supports both modes, with an agent factory that instantiates local or remote agents based on configuration.
