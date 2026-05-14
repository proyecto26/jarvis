## ADDED Requirements

### Requirement: EpisodicMemory class with tiered backends

The system SHALL implement an `EpisodicMemory` class in `triforce/memory/episodic.py` that combines BM25, sentence-transformer embeddings, and Grafeo graph queries via weighted Reciprocal Rank Fusion.

#### Scenario: Tier 0 — BM25-only (no optional deps installed)

- **WHEN** `EpisodicMemory()` is instantiated and neither `sentence-transformers` nor `grafeo` is importable
- **THEN** the instance initializes successfully
- **AND** logs that it is running in BM25-only mode
- **AND** `recall_similar()` returns BM25 keyword matches against tokenized journal text

#### Scenario: Tier 1 — BM25 + embeddings

- **WHEN** `sentence-transformers` is importable
- **THEN** the constructor loads `all-MiniLM-L6-v2` and logs Tier 1 readiness
- **AND** `recall_similar()` fuses BM25 ranks with embedding cosine ranks via weighted RRF

#### Scenario: Tier 2 — BM25 + embeddings + graph

- **WHEN** both `sentence-transformers` and `grafeo` are importable
- **THEN** the constructor creates an embedded Grafeo database at `EPISODIC_DB_PATH`
- **AND** `recall_similar()` adds a third graph-traversal ranker to the RRF fusion

### Requirement: Journal entry indexing

The system SHALL index each `JournalEntry` into the BM25 corpus, the embedding store, and the Grafeo graph (when available).

#### Scenario: Indexing flattens entry sections to searchable text

- **WHEN** `index_journal_entry(entry)` is called
- **THEN** the entry's `dominant_theme`, all `judgments.action` + `judgments.reasoning`, all `executions.action` + `executions.outcome`, all `learnings.content`, all `dreams.seed` + `dreams.breakthrough`, and all `belief_mutations.belief` are concatenated and tokenized
- **AND** appended to the BM25 corpus with bigrams
- **AND** the index is marked dirty for lazy rebuild on next query

#### Scenario: Graph node creation when Grafeo is available

- **WHEN** `index_journal_entry(entry)` is called AND Grafeo is loaded
- **THEN** an `(:Entry {date, theme})` node is created in the embedded graph
- **AND** the node persists across process restarts at `EPISODIC_DB_PATH`

### Requirement: Hybrid retrieval via Weighted Reciprocal Rank Fusion

The system SHALL combine ranker outputs using weighted RRF: `score(d) = Σ w_i / (k + rank_i(d))` with `k=60`.

#### Scenario: Weights favor semantic recall

- **WHEN** all three rankers (BM25, embeddings, graph) return candidate entries for a query
- **THEN** embedding rank contributes weight `3.0`
- **AND** BM25 rank contributes weight `1.0`
- **AND** graph rank contributes weight `0.3`

#### Scenario: Top-k results normalized to 0–1

- **WHEN** `recall_similar(query, top_k=5)` is called
- **THEN** it returns up to 5 dicts with `date`, `score` (normalized 0–1), and `content` (truncated to 300 chars)

### Requirement: FadeMem reinforcement and decay tracking

The system SHALL track per-entry last-access timestamps and expose a strength function based on the Ebbinghaus decay curve.

#### Scenario: Reinforcement resets the decay clock

- **WHEN** `reinforce(entry_id)` is called
- **THEN** the entry's `_last_access` timestamp is set to `datetime.utcnow()`
- **AND** `get_decay_strength(entry_id)` returns 1.0

#### Scenario: Decay formula matches the Ebbinghaus curve

- **WHEN** `get_decay_strength(entry_id, decay_rate=0.02)` is called
- **THEN** it returns `math.exp(-decay_rate * days_since_last_access)`

#### Scenario: Recall implicitly reinforces

- **WHEN** an entry appears in a `recall_similar()` result
- **THEN** that entry's `_last_access` is updated to the current UTC time

### Requirement: Lazy index rebuilding

The system SHALL rebuild BM25, TF-IDF, and embedding indexes only when the underlying corpus has changed.

#### Scenario: Repeated queries skip rebuild

- **WHEN** `recall_similar()` is called twice with no intervening `index_journal_entry()`
- **THEN** the second call reuses the existing indexes without recomputing

#### Scenario: Indexing marks state dirty

- **WHEN** `index_journal_entry()` is called
- **THEN** the next `recall_similar()` rebuilds BM25 + TF-IDF + embedding tensor (and Grafeo node insert was already eager)

### Requirement: ADK tool wiring

The `recall_episodic`, `check_belief_conflict`, and `reinforce_memory` ADK tools SHALL be registered on the executor agent.

#### Scenario: Executor lists memory tools

- **WHEN** the executor agent is constructed
- **THEN** `executor_agent.tools` includes `recall_episodic`, `check_belief_conflict`, `reinforce_memory` alongside `append_to_state` and `write_journal_entry`

#### Scenario: recall_episodic returns structured results

- **WHEN** the Executor calls `recall_episodic(query="...")` during awake mode
- **THEN** the tool returns `{status: "ok", query, results: [...], count}` where each result has `date`, `score`, `content`
