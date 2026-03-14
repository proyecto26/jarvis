## ADDED Requirements

### Requirement: generate_content Temporal Activity
The system SHALL implement a `generate_content` Temporal Activity in `triforce/temporal/activities.py` that makes durable Gemini API calls.

#### Scenario: Activity definition
- **WHEN** `generate_content` is registered with a Temporal Worker
- **THEN** it is decorated with `@activity.defn` and accepts a `GeminiChatRequest` dataclass

#### Scenario: GeminiChatRequest dataclass
- **WHEN** constructing a `GeminiChatRequest`
- **THEN** it SHALL contain: `model: str`, `system_instruction: str`, `contents: list[types.Content]`, `tools: list[types.Tool]`

#### Scenario: Automatic function calling disabled
- **WHEN** `generate_content` calls the Gemini API
- **THEN** it sets `automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)` so tool calls are handled as separate Activities

#### Scenario: SDK retries disabled — Temporal owns retries
- **WHEN** `generate_content` constructs the Gemini client
- **THEN** it sets `http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1))` — exactly one attempt; Temporal's `RetryPolicy` handles retries

#### Scenario: GeminiChatResponse dataclass
- **WHEN** `generate_content` returns
- **THEN** it returns a `GeminiChatResponse` with: `text: str | None`, `function_calls: list[dict[str, Any]]`, `raw_parts: list[types.Part]`

#### Scenario: raw_parts preservation for thought signatures
- **WHEN** the Gemini response contains thought signature parts (Gemini 3)
- **THEN** `raw_parts` includes ALL parts from `response.candidates[0].content.parts` so that thought signatures are propagated correctly in multi-turn conversations

### Requirement: dynamic_tool_activity Temporal Activity
The system SHALL implement a `dynamic_tool_activity` dynamic Temporal Activity that executes any registered Jarvis tool by name.

#### Scenario: Dynamic activity registration
- **WHEN** `dynamic_tool_activity` is registered with the worker
- **THEN** it uses `@activity.defn(dynamic=True)` so it handles any activity type name not matched by named activities

#### Scenario: Tool name resolution
- **WHEN** `dynamic_tool_activity` is invoked with activity type `"get_weather_alerts"`
- **THEN** it calls `get_handler("get_weather_alerts")` from the Jarvis tool registry to get the async handler function

#### Scenario: Pydantic model argument parsing
- **WHEN** the tool handler's first parameter is a Pydantic `BaseModel` subclass
- **THEN** `dynamic_tool_activity` extracts nested args (e.g., `{"request": {"state": "CA"}}` → `GetWeatherAlertsRequest(state="CA")`)

#### Scenario: Zero-argument tool handling
- **WHEN** the tool handler has no parameters
- **THEN** `dynamic_tool_activity` calls it with no arguments: `await handler()`

#### Scenario: Result serialization
- **WHEN** the tool handler returns a result
- **THEN** `dynamic_tool_activity` returns it as a `dict` — serializable by Temporal's data converter

### Requirement: Temporal sandbox compatibility
The system SHALL configure Temporal's workflow sandbox to allow required third-party modules.

#### Scenario: Sandbox imports_passed_through
- **WHEN** `triforce/temporal/workflows.py` is loaded
- **THEN** it uses `workflow.unsafe.imports_passed_through()` to pass through: `pydantic_core`, `annotated_types`, `httpx`, `google.genai`

### Requirement: Worker registration
The system SHALL implement a Temporal Worker that registers all workflows and activities.

#### Scenario: Worker startup
- **WHEN** `python -m triforce.temporal.worker` is run
- **THEN** it connects to Temporal server at `TEMPORAL_HOST`, registers `AwakeWorkflow`, `DreamWorkflow`, `ConsolidationWorkflow`, and all activities, then starts polling `TEMPORAL_TASK_QUEUE`

#### Scenario: pydantic_data_converter
- **WHEN** the Temporal client is created
- **THEN** it uses `pydantic_data_converter` from `temporalio.contrib.pydantic` for proper Pydantic model serialization across workflow/activity boundaries
