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
**Pending** — awaiting baseline measurement.

## Learnings
*(Updated after each experiment)*
