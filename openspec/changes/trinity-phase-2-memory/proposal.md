## Why

Phase 1 gives Jarvis a running Trinity (Dreamer, Judge, Executor) with a file-based daily journal as its only memory. But memory is not just storage — it is the mechanism by which Jarvis learns, evolves, and becomes itself over time. Phase 1's flat journal is read linearly; it cannot answer "what did I experience in similar situations?" or "what did the Judge believe on January 15th?" without reading every file.

Research conducted in March 2026 (RESEARCH_MEMORY.md) surveyed 20+ papers on AI agent memory systems and identified a decisive winner: **Mem0 + Graphiti** — complementary systems that together cover the full spectrum of memory Jarvis needs. This phase implements the 3-layer memory architecture that emerged from that research and was validated against the SSGM framework for memory safety.

The verdict: Mem0 for *what happened* (episodic/semantic retrieval over the journal), Graphiti + KuzuDB for *what is believed and when* (temporal belief graph with validity windows), and ADK session state as the fast working memory layer that already exists.

## What Changes

- Implement `triforce/memory/episodic.py` — Mem0-based episodic index over the daily journal; works with Ollama (100% local) or Gemini API
- Implement `triforce/memory/temporal_beliefs.py` — Graphiti + KuzuDB embedded temporal belief graph replacing the flat `judge_beliefs.json`; enables queries like "what did Jarvis believe on date X?"
- Add `triforce/memory/consolidation.py` — nightly consolidation worker that runs the FadeMem decay loop, compresses old journal entries to episode summaries, and runs SSGM conflict detection on new beliefs
- Upgrade Judge tools: `recall_similar_decisions` now uses Mem0 hybrid retrieval (semantic + BM25); `update_beliefs` now writes temporal edges to Graphiti instead of flat JSON mutations
- Update Executor and Dreamer to query episodic memory at session start — working memory is seeded with relevant past experiences
- Add SSGM conflict detection: when a new belief contradicts an existing one with strength > 0.7, flag it for Judge review instead of silently overwriting

## Capabilities

### New Capabilities

- `episodic-memory`: Mem0-based index over the daily journal — semantic + BM25 hybrid retrieval; each journal entry (DreamCycle, Judgment, Execution, Learning) is indexed after write; queries return ranked episodes with source traceability
- `temporal-beliefs`: Graphiti + KuzuDB embedded temporal belief graph — each BeliefMutation creates a new temporal edge with validity window; supports point-in-time queries ("what did Judge believe on date X?"); hybrid retrieval: semantic + BM25 + graph traversal
- `memory-consolidation`: Nightly consolidation worker — FadeMem decay on episodic entries (Ebbinghaus curve: strength decays unless reinforced), compression of 30-day-old judgments to learning summaries, SSGM conflict detection on new belief mutations
- `ssgm-safety`: Stability and Safety Governed Memory checks — conflict detection before belief overwrites, stability monitor for belief drift, safety flagging for high-stakes mutations

### Modified Capabilities

- `journal-schema`: Extended with cognitive load scores per entry (for FadeMem decay) and traceability anchors connecting beliefs to source episodes
- `judge-agent`: `recall_similar_decisions` upgraded from flat JSON scan to Mem0 hybrid retrieval; `update_beliefs` now writes to Graphiti temporal graph; receives SSGM conflict flags before self-mutation
- `dreamer-agent`: Seeds `dream_seeds` from episodic memory at session start — dreams informed by relevant past experiences
- `executor-agent`: Seeds working context from recent Mem0 episodic retrieval before acting

## Impact

- **New code**: `triforce/memory/episodic.py`, `triforce/memory/temporal_beliefs.py`, `triforce/memory/consolidation.py` (~600 lines)
- **Dependencies**: `mem0ai`, `chromadb`, `graphiti-core`, `kuzu`, `sentence-transformers` (or Gemini embeddings); all run embedded (no external servers)
- **Data migration**: `memory/judge_beliefs.json` migrated to KuzuDB embedded graph at first run
- **Backward compatibility**: File-based journal (`.md` files) remains the primary human-readable store; Mem0/Graphiti are indexes over it, not replacements
- **Local-first**: All memory operations work 100% locally with Ollama — Gemini API is opt-in for embeddings
- **Deployment**: No new servers; ChromaDB and KuzuDB run embedded in the same Python process
