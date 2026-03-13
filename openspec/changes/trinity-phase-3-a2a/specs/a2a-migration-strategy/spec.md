## ADDED Requirements

### Requirement: Phased agent extraction order
The migration from Phase 1 (single-process) to Phase 3 (distributed A2A) SHALL follow a strict order: Dreamer first, Judge second, Executor remains as client.

#### Scenario: Dreamer extracted first
- **WHEN** the first A2A migration step begins
- **THEN** only the Dreamer SHALL be extracted as a remote A2A service, while Judge and Executor remain in-process

#### Scenario: Judge extracted second
- **WHEN** the Dreamer A2A service is verified stable
- **THEN** the Judge SHALL be extracted as the second remote A2A service, while Executor remains in-process as the A2A client

#### Scenario: Executor remains as frontline client
- **WHEN** all migration steps are complete
- **THEN** the Executor SHALL remain a local ADK agent that orchestrates calls to remote Dreamer and Judge via `RemoteA2aAgent`

### Requirement: Backward-compatible execution modes
The system SHALL support running in both single-process mode (Phase 1) and distributed mode (Phase 3) from the same codebase, controlled by the `AGENT_MODE` environment variable.

#### Scenario: Phase 1 mode preserved
- **WHEN** `AGENT_MODE` is `"local"` or unset
- **THEN** all agents SHALL run in-process using ADK session state for communication, identical to Phase 1 behavior

#### Scenario: Phase 3 mode activated
- **WHEN** `AGENT_MODE` is `"a2a"`
- **THEN** Dreamer and Judge SHALL be accessed via `RemoteA2aAgent`, communicating over A2A JSON-RPC 2.0

#### Scenario: Single-process tests remain valid
- **WHEN** Phase 1 integration tests are executed with `AGENT_MODE=local`
- **THEN** all existing tests SHALL pass without modification

### Requirement: Cross-framework agent replacement
The A2A protocol SHALL enable replacing any Trinity agent with a non-ADK agent (e.g., LangChain, CrewAI, custom) as long as the replacement serves a compatible Agent Card and implements the expected A2A message contract.

#### Scenario: Non-ADK Dreamer replacement
- **WHEN** a LangChain-based dreamer agent is deployed as an A2A server with a compatible Agent Card
- **THEN** the Executor SHALL connect to it via `RemoteA2aAgent` and the dream loop SHALL function identically, because A2A protocol is framework-agnostic

#### Scenario: Agent Card compatibility check
- **WHEN** the Executor connects to a remote agent via its Agent Card
- **THEN** the Executor SHALL verify that the remote agent's `skills` include the expected skill IDs (`generate_dreams` for Dreamer, `filter_evaluate`/`collaborate_dream` for Judge) before routing tasks

### Requirement: Rollback procedure
Each migration step SHALL include a documented rollback procedure that reverts to the previous state within minutes.

#### Scenario: Rollback from distributed to local
- **WHEN** a critical issue is detected with a remote agent service
- **THEN** setting `AGENT_MODE=local` and restarting the Executor SHALL revert all agent communication to in-process mode without data loss

#### Scenario: Partial rollback of single agent
- **WHEN** the Judge A2A service has issues but the Dreamer A2A service is stable
- **THEN** unsetting `JUDGE_A2A_URL` while keeping `DREAMER_A2A_URL` SHALL revert only the Judge to in-process mode while Dreamer remains remote

### Requirement: Migration verification checklist
Each migration step SHALL include automated verification that confirms the distributed setup produces equivalent results to the single-process setup.

#### Scenario: Dream loop equivalence test
- **WHEN** the Dreamer is migrated to A2A
- **THEN** a test SHALL run the same dream seed through both local and A2A modes and verify that the response structure (dream content, state keys) is equivalent

#### Scenario: Awake pipeline equivalence test
- **WHEN** the Judge is migrated to A2A
- **THEN** a test SHALL send the same user request through both local and A2A awake pipelines and verify that the Judge verdict structure (verdict, reasoning, action_weight) is equivalent
