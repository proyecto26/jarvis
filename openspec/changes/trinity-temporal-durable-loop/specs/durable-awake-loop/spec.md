## ADDED Requirements

### Requirement: AwakeWorkflow durable ReAct loop
The system SHALL implement `AwakeWorkflow` as a Temporal Workflow in `triforce/temporal/workflows.py` that executes the Executor's ReAct loop as durable Activities.

#### Scenario: Workflow takes user input
- **WHEN** `AwakeWorkflow` is started with `input: str`
- **THEN** it initializes a `contents` list with the user input as a `user` role `Content` object and enters the ReAct loop

#### Scenario: LLM call as durable activity
- **WHEN** the ReAct loop calls the LLM
- **THEN** it uses `workflow.execute_activity(generate_content, GeminiChatRequest(...), start_to_close_timeout=timedelta(seconds=60))`
- **AND** each call is independently persisted by Temporal — not re-executed on workflow replay

#### Scenario: Tool call as durable activity
- **WHEN** the LLM response contains `function_calls`
- **THEN** each function call is executed via `workflow.execute_activity(tool_name, tool_args, start_to_close_timeout=timedelta(seconds=30))`
- **AND** `raw_parts` from the LLM response are preserved and appended to `contents` to maintain Gemini thought signatures

#### Scenario: Loop termination on text response
- **WHEN** the LLM response contains `text` and no `function_calls`
- **THEN** `write_journal_entry_activity` is called to record the execution, and the workflow returns the final text

#### Scenario: Crash recovery
- **WHEN** the worker process crashes after completing 3 of 5 tool calls
- **THEN** on worker restart, Temporal replays the workflow from its event log, skips the 3 already-completed Activities, and resumes from Activity 4 without re-executing completed tool calls

### Requirement: Action weight routing
The system SHALL route high-weight interactions to `AwakeWorkflow` and short interactions to inline ADK.

#### Scenario: High action weight → durable workflow
- **WHEN** the Judge assigns `action_weight >= 4` to a requested action
- **THEN** the Executor routes to `AwakeWorkflow` via the Temporal client

#### Scenario: Low action weight → inline ADK
- **WHEN** the Judge assigns `action_weight < 4`
- **THEN** the Executor continues inline through the ADK pipeline without Temporal overhead

### Requirement: Executor self-escalation tool
The Executor SHALL have a tool to self-escalate to a durable workflow mid-interaction.

#### Scenario: Escalation tool call
- **WHEN** the Executor calls `escalate_to_durable_workflow(task_description)`
- **THEN** a new `AwakeWorkflow` is started with the task description and the workflow ID is returned for reference
