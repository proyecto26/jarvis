# Spec: model-preferences

## ADDED Requirements

### Requirement: Runtime Per-Agent Model Preference

The system SHALL let the operator set, clear, and inspect a default model per agent (`dreamer`, `executor`, `judge_filter`, `judge_collaborator`) at runtime via `set_agent_model(agent, model_id, reason)`, `clear_agent_model(agent)`, and `get_model_config()`. Preferences SHALL persist across process restarts in `memory/model_prefs.json` using atomic writes.

#### Scenario: Set and use a preference

- **WHEN** the operator sets `executor → gemini-2.0-flash` and the Executor next resolves a model
- **THEN** the router returns `gemini-2.0-flash` with `preference_source: user`

#### Scenario: Preference survives restart

- **WHEN** a preference is set and the process restarts
- **THEN** the preference is still honored on the next route

#### Scenario: Clear restores policy routing

- **WHEN** the operator clears an agent's preference
- **THEN** subsequent routes for that agent resolve via topic/policy levels as if no preference had existed

### Requirement: Preferences are Audited as OKF Documents

Every preference change SHALL additionally be recorded as an OKF document (`type: Preference`, frontmatter: `agent`, `model_id`, `supersedes` link to the previous preference doc when one exists; reason in the body) in the knowledge bundle. If the OKF module is unavailable, the preference change SHALL still take effect and the skipped audit SHALL be logged.

#### Scenario: Model switch lands in the bitácora

- **WHEN** the operator sets a new model for the Judge with a reason
- **THEN** an OKF `Preference` doc is written and `log.md` gains a dated entry
- **AND** the previous preference doc is linked via `supersedes`

#### Scenario: OKF unavailable does not block the switch

- **WHEN** the OKF bundle cannot be written (module missing or IO error)
- **THEN** `model_prefs.json` is still updated and routing honors the new preference
- **AND** a warning is logged about the missing audit record

### Requirement: Preference Management is an Executor Tool

The set/clear/inspect operations SHALL be exposed as an ADK tool registered on the Executor agent, since the Executor is the only agent with an external interface. Preference changes SHALL NOT require Judge approval (the operator outranks the Judge on model choice).

#### Scenario: Operator changes a model conversationally

- **WHEN** the operator tells the Executor to use a given model for the Dreamer
- **THEN** the Executor invokes the tool and confirms the change, and the next Dreamer cycle uses that model
