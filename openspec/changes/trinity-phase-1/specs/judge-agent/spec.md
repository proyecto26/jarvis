## ADDED Requirements

### Requirement: Judge agent definition
The system SHALL define a Judge agent as a Google ADK `LlmAgent` with the name `judge` and a configurable model (via `JUDGE_MODEL` env var, default `gemini-2.0-pro`).

#### Scenario: Judge agent instantiation
- **WHEN** the triforce package initializes the Judge agent
- **THEN** an ADK `Agent` is created with name `judge`, the configured medium-tier model, and the appropriate instruction prompt for its current mode

### Requirement: Judge dual-mode operation
The Judge SHALL support two operating modes with distinct instruction prompts:
1. **Filter mode** (awake): Evaluates proposed actions against ethical constraints, strategic alignment, reversibility, and action weight. Outputs a verdict (approved/modified/rejected).
2. **Connector mode** (sleep): Connects Dreamer ideas to past experience, deepens associations, and detects breakthroughs. Does NOT approve or reject.

#### Scenario: Judge in filter mode
- **WHEN** the Judge is instantiated for the awake pipeline
- **THEN** its instruction prompt directs it to evaluate actions and output a verdict to `judge_verdict` state key

#### Scenario: Judge in connector mode
- **WHEN** the Judge is instantiated for the sleep loop
- **THEN** its instruction prompt directs it to connect, deepen, and detect breakthroughs — not to filter or reject

### Requirement: Judge filter mode evaluates action weight
In filter mode, the Judge SHALL assign an `action_weight` score (1-10) to each proposed action based on impact, reversibility, novelty, and alignment risk. Actions with weight >= 6 SHALL be flagged as high-weight.

#### Scenario: Low-weight action auto-approval
- **WHEN** the Judge evaluates an action with weight < 6
- **THEN** it MAY approve automatically with brief reasoning

#### Scenario: High-weight action full evaluation
- **WHEN** the Judge evaluates an action with weight >= 6
- **THEN** it SHALL provide detailed reasoning, store the decision in `high_weight_actions` state, and explicitly state its verdict

### Requirement: Judge filter mode outputs structured verdict
In filter mode, the Judge SHALL write the following keys to session state via `append_to_state`:
- `judge_verdict`: `approved` | `modified` | `rejected`
- `judge_reasoning`: explanation string
- `action_weight`: integer 1-10
- `executor_guidance`: specific guidance for the Executor

#### Scenario: Verdict state keys set
- **WHEN** the Judge completes filter-mode evaluation
- **THEN** all four state keys (`judge_verdict`, `judge_reasoning`, `action_weight`, `executor_guidance`) are populated

### Requirement: Judge connector mode has exit_loop tool
In connector mode, the Judge SHALL have access to the ADK `exit_loop` tool and SHALL call it only when a genuine breakthrough has been detected — defined as a reframing insight that could not arise in awake mode.

#### Scenario: Breakthrough triggers exit_loop
- **WHEN** the Judge-as-connector detects a genuine breakthrough after at least 3 dream cycles
- **THEN** it stores the breakthrough in the `breakthrough` state key and calls `exit_loop`

#### Scenario: No breakthrough continues loop
- **WHEN** the Judge-as-connector does not detect a breakthrough
- **THEN** it adds deepening connections to `dream_deepening` state and lets the loop continue

### Requirement: Judge connector mode deepens dream seeds
In connector mode, the Judge SHALL read `dream_seeds` from state, connect them to past experience (from `journal_context` if available), and write deepening associations to `dream_deepening` state key.

#### Scenario: Judge reads and deepens seeds
- **WHEN** the Judge runs in connector mode during a sleep cycle
- **THEN** it reads `dream_seeds`, produces connections to past experience, and writes them to `dream_deepening`

### Requirement: Judge self-mutation via beliefs file
After significant judgments (action_weight >= 6), the Judge SHALL update `memory/judge_beliefs.json` with new or modified beliefs, including belief text, strength score (0.0-1.0), and timestamp.

#### Scenario: Belief update after high-weight judgment
- **WHEN** the Judge makes a decision with action_weight >= 6
- **THEN** the `judge_beliefs.json` file is updated with any new or changed beliefs resulting from the decision

#### Scenario: Beliefs loaded at session start
- **WHEN** a new Judge session begins
- **THEN** the contents of `judge_beliefs.json` are loaded into the Judge's instruction context

### Requirement: Judge prompt templates in prompts module
The Judge's instruction texts for both modes SHALL be defined in `triforce/agents/judge/prompts.py` as named constants (`FILTER_PROMPT`, `COLLABORATOR_PROMPT`).

#### Scenario: Prompt module structure
- **WHEN** the Judge agent is constructed
- **THEN** it imports the appropriate instruction string from `prompts.py` based on the operating mode
