# Autoresearch: Jarvis Memory System Optimization

## Goal
Optimize the Jarvis Trinity memory system to be fully **local-first** (no external APIs for storage/retrieval) while maximizing recall quality, write/read latency, and contradiction detection accuracy.

## Primary Metric
- **Name:** `composite_score`
- **Unit:** normalized 0-100
- **Direction:** `higher` is better
- **Formula:** `0.40 * recall_precision_at_5 + 0.20 * (1 - norm_write_latency) + 0.20 * (1 - norm_read_latency) + 0.20 * contradiction_f1`

## Secondary Metrics
| Metric | Unit | Direction |
|--------|------|-----------|
| `recall_precision_at_5` | ratio 0-1 | higher |
| `write_latency_ms` | milliseconds | lower |
| `read_latency_ms` | milliseconds | lower |
| `contradiction_f1` | ratio 0-1 | higher |
| `memory_usage_mb` | MB | lower |

## Files in Scope
- `triforce/memory/episodic.py` — Episodic memory backend (currently stub)
- `triforce/memory/beliefs.py` — Beliefs persistence
- `triforce/memory/temporal_beliefs.py` — Temporal belief store (currently stub)
- `triforce/memory/ssgm.py` — SSGM conflict detection
- `triforce/memory/consolidation.py` — Nightly consolidation
- `benchmarks/memory_bench.py` — Benchmark harness
- `benchmarks/backends/*.py` — Backend implementations
- `benchmarks/synthetic_data.py` — Test data generator

## Constraints
- **Local-first only** — no external API calls for storage, retrieval, or embeddings
- Must work offline (Docker-based services OK since they run locally)
- Must integrate with the existing ADK agent architecture
- Python 3.11+ compatible
- Memory footprint < 500MB for 10K entries

## Experiment Plan

### Baseline
Current JSON-based system (beliefs.py + journal.py + SSGM string matching).
Expected: fast writes, zero semantic recall, basic string-match contradictions.

### Experiment 1: Grafeo (graph + vector + BM25)
- Docker: `grafeo/grafeo-server`
- Embedded Python bindings
- HNSW vector search + BM25 full-text + Cypher graph queries
- CDC for temporal tracking

### Experiment 2: RuVector (self-learning vector DB)
- Built-in GGUF LLM runtime for local embeddings
- Temporal learning (connection decay, association strengthening)
- GNN overlay for adaptive retrieval

### Experiment 3: HelixDB (graph + vector + built-in embeddings)
- CLI install, local endpoint
- HelixQL for type-safe queries
- Built-in text embedding via `Embed` function

### Experiment 4: PageIndex-local (hierarchical tree + BM25)
- Pure Python implementation, no external APIs
- Hierarchical tree navigation inspired by PageIndex
- TF-IDF/BM25 for local scoring (replaces GPT-4o calls)
- Tree search using beam search with local similarity scoring

### Experiment 5: Hybrid winner + Supermemory patterns
- Take the best backend from experiments 1-4
- Add Supermemory design patterns: fact extraction, contradiction resolution, automatic forgetting
- Implement locally using the chosen backend

## Current Best
**Unified backend: 89.28/100** (BM25 + Grafeo graph + sentence-transformers embeddings)
- Recall P@5: 0.76 (handles both keyword and semantic/synonym queries)
- Contradiction F1: 1.00 (TF-IDF cosine, threshold 0.6)
- Write latency: 0.02ms/op
- Read latency: 5.6ms/op
- Memory: 0.15MB for 100 entries

## Results Summary

| Backend | Composite | P@5 | F1 | Write (ms) | Read (ms) |
|---------|-----------|-----|-----|-----------|----------|
| json-baseline | 73.97 | 0.44 | 0.87 | 0.25 | 4.87 |
| pageindex-local | 82.67 | 0.57 | 1.00 | 0.01 | 0.61 |
| hybrid-embeddings | 80.32 | 0.64 | 0.80 | 0.02 | 6.37 |
| grafeo | 87.64 | 0.82 | 0.80 | 0.02 | 5.79 |
| **unified** | **89.28** | **0.76** | **1.00** | 0.02 | 5.57 |

## Learnings

1. **Keyword-only recall caps at ~57% on semantic queries.** BM25/TF-IDF cannot bridge
   the synonym gap ("authentication" vs "login security"). Embeddings are essential.

2. **PMI co-occurrence expansion hurts more than helps.** Corpus-derived co-occurrence
   terms dilute the query signal with noise (P@5 dropped from 0.57 to 0.55).

3. **Stemming adds overhead without improving precision** on this corpus. The synthetic
   data uses consistent terminology, so suffix stripping wasn't beneficial.

4. **Lazy index rebuilding gives 9x read speedup.** Rebuilding BM25/TF-IDF indexes on
   every query is wasteful — dirty-flag pattern reduces read latency from 5.8ms to 0.6ms.

5. **Embedding query inference dominates read latency.** sentence-transformers encode()
   takes ~5ms per query regardless of corpus size. This is the fundamental floor.

6. **Weighted RRF beats equal-weight RRF.** Giving embeddings 3x weight and demoting
   graph to 0.3x improved P@5 from 0.66 to 0.76.

7. **TF-IDF cosine similarity outperforms embeddings for contradiction detection.**
   F1=1.0 vs 0.80 — because TF-IDF captures structural similarity (same sentence
   pattern, different pattern names) better than semantic embeddings.

8. **Graph adds marginal value for recall but enables future relational queries.**
   Disabling graph only dropped score from 89.28 to 89.22 — but it provides the
   foundation for temporal belief lineage, topic traversal, and knowledge graphs.

9. **Grafeo embeds locally in Python with zero server overhead.** No Docker needed
   for the graph component — the `grafeo` pip package includes a Rust-backed
   embedded database that runs in-process.

10. **Graceful degradation is key.** The tiered architecture (BM25 → +embeddings →
    +graph) means the memory system works with zero optional dependencies and
    progressively improves as components are installed.
