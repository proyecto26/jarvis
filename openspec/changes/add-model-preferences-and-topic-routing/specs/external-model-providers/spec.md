# Spec: external-model-providers

## ADDED Requirements

### Requirement: Anthropic Provider

The system SHALL provide an Anthropic provider implementing the `Provider` ABC (`generate`, `health`, `capabilities`) against the Anthropic Messages API using `httpx` directly (no vendor SDK). The provider SHALL read its API key from `ANTHROPIC_API_KEY`.

#### Scenario: Generate via Anthropic

- **WHEN** the router decides on a registry model with `provider: anthropic` and calls `generate()`
- **THEN** the provider sends a Messages API request and returns a `ProviderResponse` with the completion text

#### Scenario: Missing API key degrades gracefully

- **WHEN** `ANTHROPIC_API_KEY` is not set
- **THEN** `health()` returns `False` without raising
- **AND** the router skips all Anthropic-backed candidates instead of failing the route

### Requirement: OpenAI-Compatible Provider

The system SHALL provide an OpenAI-compatible provider (Chat Completions API over `httpx`) configurable with a base URL, so OpenAI, OpenRouter, and self-hosted compatible servers (vLLM, LM Studio) are all served by one provider class. The API key env var SHALL be configurable per registry entry, defaulting to `OPENAI_API_KEY`.

#### Scenario: OpenRouter through the same provider

- **WHEN** a registry model declares `provider: openai_compat` with `base_url: https://openrouter.ai/api/v1`
- **THEN** `generate()` targets that base URL with the entry's configured key

#### Scenario: Provider outage marks candidates unhealthy

- **WHEN** the configured endpoint is unreachable within the health-check timeout
- **THEN** `health()` returns `False` and routing falls through to the next candidate or precedence level

### Requirement: External Models Registered Declaratively

External frontier models (Claude, GPT, Gemini, OpenRouter-served) SHALL be declared in `models.yaml` like any other registry entry, including capabilities, context window, and tags. Cloud-backed entries SHALL only be eligible when the request's effective privacy class permits cloud.

#### Scenario: local-only request never reaches external providers

- **WHEN** a request carries privacy class `local-only`
- **THEN** no Anthropic or OpenAI-compatible candidate is considered at any precedence level, including user preferences
