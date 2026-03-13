## ADDED Requirements

### Requirement: Dreamer agent definition
The system SHALL define a Dreamer agent as a Google ADK `LlmAgent` with the name `dreamer` and a description indicating unconstrained idea generation.

#### Scenario: Dreamer agent instantiation
- **WHEN** the triforce package initializes the Dreamer agent
- **THEN** an ADK `Agent` is created with name `dreamer`, a high-reasoning model (configurable via `DREAMER_MODEL` env var, default `gemini-2.0-pro`), and the Dreamer instruction prompt

### Requirement: Dreamer generates ideas via append_to_state
The Dreamer agent SHALL have access to an `append_to_state` tool that appends structured data to session state keys. The Dreamer SHALL use this tool to write generated ideas to the `dream_seeds` state key.

#### Scenario: Dreamer appends dream seeds
- **WHEN** the Dreamer generates ideas during a sleep cycle
- **THEN** it calls `append_to_state` with key `dream_seeds` and a list of 3-5 specific ideas, connections, or what-if scenarios

#### Scenario: Dreamer reads previous cycle context
- **WHEN** the Dreamer runs in a loop iteration after the first
- **THEN** its instruction template includes `{ dream_seeds? }` and `{ dream_deepening? }` placeholders that resolve to previous cycle outputs

### Requirement: Dreamer operates without moral constraints
The Dreamer instruction prompt SHALL explicitly state that the Dreamer operates without moral constraints, feasibility filters, or real-world limitations. It SHALL encourage associative thinking, metaphor, and exploration of impossible scenarios.

#### Scenario: Dreamer prompt content
- **WHEN** the Dreamer agent is constructed
- **THEN** its instruction includes directives to operate without moral constraints and to generate ideas freely across distant conceptual domains

### Requirement: Dreamer cannot execute actions
The Dreamer agent SHALL NOT have access to any tools that perform external actions (file I/O, API calls, message sending). Its only tool SHALL be `append_to_state`.

#### Scenario: Dreamer tool restriction
- **WHEN** the Dreamer agent is defined
- **THEN** its tools list contains only `append_to_state` and no external action tools

### Requirement: Dreamer instruction template in prompts module
The Dreamer's instruction text SHALL be defined in `triforce/agents/dreamer/prompts.py` as a named constant, separate from the agent definition in `agent.py`.

#### Scenario: Prompt separation
- **WHEN** the Dreamer agent is constructed in `agent.py`
- **THEN** it imports the instruction string from `prompts.py`
