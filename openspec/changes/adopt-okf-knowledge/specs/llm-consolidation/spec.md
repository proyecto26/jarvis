# LLM Consolidation Spec

## ADDED Requirements

### Requirement: Single LLM Adapter via Router route()

All consolidation LLM traffic SHALL go through one adapter function, `_llm_summarize(prompt) -> str | None`, which resolves a model via `get_router().route(RouteRequest(agent="consolidation"))`, looks up the decided provider in the provider registry, and calls `provider.generate(...)`. The adapter SHALL NOT use `Router.for_agent()` (which resolves model-id strings for ADK constructors and does not execute completions). Calls SHALL be timeout-wrapped, and any failure SHALL return `None`.

#### Scenario: Successful summarization via a local provider

- **WHEN** the router decides an ollama model for the `consolidation` agent
- **THEN** the adapter resolves the `OllamaProvider` from the registry and calls its `generate(...)`
- **AND** the generated text is returned to the calling pass

#### Scenario: Router or provider failure yields None

- **WHEN** the router raises, no provider is healthy, or `generate(...)` times out
- **THEN** the adapter returns `None`
- **AND** no exception escapes to the consolidation pass

#### Scenario: Tests fake the adapter, never the network

- **WHEN** consolidation passes run under test
- **THEN** faking `_llm_summarize` alone suffices to exercise both passes end-to-end
- **AND** no network access occurs

### Requirement: Consolidation Routing Policy

A routing policy `triforce/llm/policies/consolidation.yaml` SHALL exist, conforming to `SCHEMA.md`, preferring cheap local (ollama) models with cloud fallback allowed for non-private summaries. As a batch job, latency SHALL NOT be a constraining factor in candidate selection.

#### Scenario: Local model preferred when available

- **WHEN** ollama is healthy and hosts a capable small model
- **THEN** the consolidation route decision selects it over cloud candidates

### Requirement: Episode Compression Pass

`compress_old_episodes()` SHALL group journal entries older than 30 days by ISO week and, for each uncompressed week, LLM-summarize its judgments and executions into 3-7 OKF `Learning` documents, marking the source entries compressed in a sidecar state file (`knowledge/.consolidation-state.json`). The pass SHALL preserve its existing return dict shape (`weeks_compressed`, `entries_compressed`, `high_load_preserved`) and SHALL never delete source journal entries.

#### Scenario: An old uncompressed week is compressed

- **WHEN** the journal holds entries from an ISO week more than 30 days old that the state file does not mark compressed
- **THEN** between 3 and 7 `Learning` documents are written to the bundle for that week
- **AND** the state file marks that week's entries compressed
- **AND** the source journal files remain on disk unmodified

#### Scenario: Re-running does not duplicate learnings

- **WHEN** `compress_old_episodes()` runs twice in a row
- **THEN** the second run produces no new `Learning` documents for already-compressed weeks

### Requirement: Journal Tier Summarization Pass

`consolidate_journal_tier()` SHALL, for each completed ISO week lacking a summary, LLM-write `journal/YYYY-Www-summary.md` from that week's daily entries and return `weeks_summarised`. Existing summaries SHALL never be overwritten.

#### Scenario: A completed week gains a summary

- **WHEN** ISO week 2026-W27 is complete and `journal/2026-W27-summary.md` does not exist
- **THEN** the pass writes that file from the week's dailies (atomic write)
- **AND** `weeks_summarised` counts it

#### Scenario: The current incomplete week is skipped

- **WHEN** the pass runs mid-week
- **THEN** no summary is written for the in-progress ISO week

### Requirement: Graceful Degradation Preserved

Both passes SHALL return `{"status": "deferred"}` — byte-identical to today's stub behavior — whenever the LLM adapter is unavailable or fails, so `ConsolidationWorker.run_nightly()` behaves exactly as before on a machine with no reachable model.

#### Scenario: Offline nightly run matches pre-change behavior

- **WHEN** `run_nightly()` executes with no ollama daemon and no cloud access
- **THEN** `compress_old_episodes()` and `consolidate_journal_tier()` each return `{"status": "deferred"}`
- **AND** the fade-decay and SSGM-audit passes run unchanged
