## Why

Phase 1 gives DANTE a running Trinity (Dreamer, Judge, Executor) with a file-based daily journal as its only memory. But memory is not just storage — it is the mechanism by which DANTE learns, evolves, and becomes itself over time. Phase 1's flat journal is read linearly; it cannot answer "what did I experience in similar situations?" or "what did the Judge believe on January 15th?" without reading every file.

### Plan Update (May 2026)

This proposal was originally drafted in March 2026 specifying **Mem0 + ChromaDB + Graphiti + KuzuDB**. Between March and May, an autoresearch experiment loop (`autoresearch.md`, `autoresearch.jsonl` — 17 logged experiments) benchmarked six candidate architectures against a synthetic 100-day journal corpus:

| Backend | Composite | P@5 | F1 | Write (ms) | Read (ms) |
|---------|-----------|-----|-----|-----------|----------|
| json-baseline | 73.97 | 0.44 | 0.87 | 0.25 | 4.87 |
| pageindex-local (BM25+tree) | 82.67 | 0.57 | 1.00 | 0.01 | 0.61 |
| hybrid-embeddings | 80.32 | 0.64 | 0.80 | 0.02 | 6.37 |
| grafeo (graph+vector) | 87.64 | 0.82 | 0.80 | 0.02 | 5.79 |
| **unified (BM25 + Grafeo + embeddings)** | **89.28** | **0.76** | **1.00** | 0.02 | 5.57 |

The unified backend — **BM25 + sentence-transformers (all-MiniLM-L6-v2) + Grafeo embedded graph, fused via weighted Reciprocal Rank Fusion** — beat the originally-planned Mem0+Graphiti stack on composite score, write latency, and memory footprint while preserving the temporal-graph capability the original plan called for. Crucially, Grafeo is a pure-Rust embedded graph DB (no separate KuzuDB process, no Mem0 dependency, no ChromaDB process), keeping everything local-first.

Phase 2 is therefore re-scoped: same capabilities (episodic recall, temporal beliefs, SSGM safety, consolidation) but a different backend stack. The original Mem0/ChromaDB/Graphiti/KuzuDB plan is superseded.

## What Changes

- Implement `triforce/memory/episodic.py` — local-first episodic memory using **3-tier graceful degradation**:
  - **Tier 0** (always): BM25 keyword recall + TF-IDF cosine for contradiction detection
  - **Tier 1** (`pip install sentence-transformers`): sentence-transformers MiniLM-L6-v2 embeddings for semantic recall
  - **Tier 2** (`pip install grafeo`): Grafeo embedded graph for relational topic/theme queries
- Implement `triforce/memory/temporal_beliefs.py` — Grafeo-backed temporal belief graph; replaces the flat `judge_beliefs.json`; supports point-in-time queries
- Implement `triforce/memory/ssgm.py` — Stability-Safety-Governed-Memory conflict detection (string-similarity baseline; embedding-based upgrade lands with Tier 1)
- Implement `triforce/memory/consolidation.py` — nightly consolidation: FadeMem decay, episode compression, SSGM audit, weekly tier summaries
- Wire memory tools (`recall_episodic`, `check_belief_conflict`, `reinforce_memory`) into the executor agent via `triforce/tools/memory_tools.py`
- Replace `pyproject.toml` `[memory]` extras: `sentence-transformers` + `grafeo` (was `mem0ai` + `chromadb` + `graphiti-core` + `kuzu`)
- Preserve `[memory-full]` extras with `graphiti-core` + `kuzu` for users who prefer that stack (opt-in fallback path)

## Capabilities

### New Capabilities

- **`episodic-memory`** — Hybrid BM25 + embedding + graph episodic recall over the daily journal. Three-tier graceful degradation means the system works with zero optional dependencies and progressively improves. Weighted Reciprocal Rank Fusion combines the three rankers (BM25 weight 1.0, embeddings 3.0, graph 0.3).
- **`temporal-beliefs`** — Grafeo embedded graph stores each `BeliefMutation` as a temporal edge with validity window. Supports `query_current(topic)` and `query_at(topic, datetime)` for point-in-time recall. Migrating from flat JSON is implemented in `migrate_from_json(dry_run=False)`.
- **`memory-consolidation`** — Nightly worker applies FadeMem decay (`strength × e^(−0.02 × days_since_last_access)`), compresses old episodes, runs SSGM audits, and produces weekly tier summaries.
- **`ssgm-safety`** — Conflict detection before belief overwrites: cosine similarity > 0.7 with strength > 0.7 raises a `ConflictReport`. Stability monitor tracks belief mutation rate over 7-day rolling window.

### Modified Capabilities

- **`journal-schema`** — Adds `cognitive_load_score` (0.0–1.0) per entry for FadeMem decay weighting; adds `source_episode_id` traceability to `BeliefMutation`.
- **`judge-agent`** — `recall_similar_decisions` upgraded from flat JSON scan to weighted-RRF hybrid retrieval; `update_beliefs` writes to the Grafeo temporal graph with pre-write SSGM check.
- **`dreamer-agent`** — At session start, seeds `dream_seeds` state key with top-5 episodic memories related to current context.
- **`executor-agent`** — At session start, seeds working context with top-3 recent episodic memories for task continuity. Gains the `recall_episodic`, `check_belief_conflict`, and `reinforce_memory` ADK tools.

## Impact

- **New code**: `triforce/memory/{episodic.py, temporal_beliefs.py, ssgm.py, consolidation.py}` (~600 lines) + `triforce/tools/memory_tools.py` (~80 lines).
- **Dependencies** (revised): `sentence-transformers` (~80 MB model on first download), `grafeo` (~5 MB pure Rust wheel). Both are local-first with no external API calls.
- **Removed dependencies vs original plan**: `mem0ai`, `chromadb`, `graphiti-core`, `kuzu`. Of these, `graphiti-core` and `kuzu` are preserved in the `[memory-full]` extras group for users who prefer that stack.
- **Data migration**: `memory/judge_beliefs.json` is read by `TemporalBeliefStore.migrate_from_json(dry_run=False)` and translated to Grafeo edges. Dry-run mode shows the plan before commit.
- **Backward compatibility**: File-based journal (`.md` files) remains the primary human-readable store; episodic/temporal indexes are queryable layers over it, not replacements.
- **Local-first guarantee**: All memory operations work 100% offline. There is no opt-in cloud embedding path — sentence-transformers ships and runs locally. (A future `add-specialized-llm-router` change will introduce optional cloud embedding for users who prefer it.)
- **Deployment**: No new servers. Grafeo runs in-process as a Rust extension.
- **Benchmark provenance**: All measurements in this proposal are reproducible via `python -m benchmarks.memory_bench --backend <name>`; raw results in `autoresearch.jsonl`.
