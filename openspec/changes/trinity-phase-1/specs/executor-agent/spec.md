## ADDED Requirements

### Requirement: Executor agent definition
The system SHALL define an Executor agent as a Google ADK `LlmAgent` with the name `executor`, a fast model (configurable via `EXECUTOR_MODEL` env var, default `gemini-2.0-flash`), and an instruction prompt that references Judge guidance from session state.

#### Scenario: Executor agent instantiation
- **WHEN** the triforce package initializes the Executor agent
- **THEN** an ADK `Agent` is created with name `executor`, the configured fast-tier model, and an instruction that reads `{ judge_verdict? }` and `{ executor_guidance? }` from state

### Requirement: Executor acts on Judge verdict
The Executor SHALL read `judge_verdict` and `executor_guidance` from session state and act accordingly:
- `approved`: Execute the original request
- `modified`: Execute the modified plan from the Judge
- `rejected`: Explain the rejection to the user and suggest alternatives

#### Scenario: Approved action execution
- **WHEN** `judge_verdict` is `approved`
- **THEN** the Executor proceeds with the original request and records the outcome

#### Scenario: Modified action execution
- **WHEN** `judge_verdict` is `modified`
- **THEN** the Executor follows the Judge's modified plan from `executor_guidance`

#### Scenario: Rejected action explanation
- **WHEN** `judge_verdict` is `rejected`
- **THEN** the Executor explains the rejection reason from `judge_reasoning` to the user and suggests alternatives

### Requirement: Executor is the only external voice
The Executor SHALL be the only agent that communicates directly with the user (J.D.). Dreamer and Judge outputs are internal — only visible through session state, not through direct user-facing messages.

#### Scenario: User receives Executor output only
- **WHEN** the awake pipeline completes
- **THEN** only the Executor's response is visible to the user; Judge reasoning is in state but not directly shown unless the user asks

### Requirement: Executor records execution outcomes
The Executor SHALL write execution outcomes to the `execution_outcome` session state key after completing an action, including status (completed/failed/partial) and a brief description of what happened.

#### Scenario: Outcome recorded after action
- **WHEN** the Executor completes an action
- **THEN** it writes `execution_outcome` to state with status and description fields

### Requirement: Executor escalates high-weight decisions
When the Executor encounters a situation that appears to have high impact, low reversibility, or ethical implications, it SHALL flag this for Judge evaluation rather than acting independently.

#### Scenario: Escalation to Judge
- **WHEN** the Executor detects a potentially high-weight situation during execution
- **THEN** it signals the need for Judge review by noting the escalation in its response rather than proceeding autonomously

### Requirement: Executor presents dream breakthroughs
When the system returns from sleep mode, the Executor SHALL read the `breakthrough` state key and present the distilled insight to the user in a clear, actionable format.

#### Scenario: Post-sleep breakthrough delivery
- **WHEN** the dream_state LoopAgent completes and `breakthrough` contains an insight
- **THEN** the Executor presents the breakthrough to the user with context about how it emerged

### Requirement: Executor prompt template in prompts module
The Executor's instruction text SHALL be defined in `triforce/agents/executor/prompts.py` as a named constant, separate from the agent definition.

#### Scenario: Prompt separation
- **WHEN** the Executor agent is constructed in `agent.py`
- **THEN** it imports the instruction string from `prompts.py`
