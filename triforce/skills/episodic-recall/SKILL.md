---
name: episodic-recall
description: >
  Queries episodic memory to find past experiences relevant to the current context.
  Use when any agent needs to recall past decisions, outcomes, or patterns from
  Jarvis's experience history. Currently a stub — full implementation pending Phase 2
  Mem0 integration. Falls back to recall_similar_decisions tool.
compatibility:
  - google-adk
metadata:
  scope: shared
  phase: 2
  status: stub
  triggers:
    - needing context from past experiences
    - looking for similar past decisions or outcomes
    - connecting current situation to historical patterns
  requires_tools:
    - recall_similar_decisions
---

# Episodic Recall (Phase 2 Stub)

> **STATUS: STUB** — This skill documents the Phase 2 episodic memory protocol.
> The full implementation requires `recall_episodic` tool backed by Mem0 + ChromaDB,
> which will be available in Phase 2. Until then, use the fallback below.

## What This Will Do (Phase 2)

When fully implemented, this skill enables natural-language queries against Jarvis's
episodic memory — all past journal entries, decisions, outcomes, and learnings
indexed for hybrid semantic + keyword retrieval.

**Phase 2 Protocol:**
1. Agent formulates a natural language query about past experience
2. Query is sent to Mem0 (hybrid semantic + BM25 retrieval)
3. Top-k results are returned with metadata (date, section, cognitive_load_score)
4. Results are formatted as ActMem-style reasoning chains:
   ```
   Context: <what was happening when this was stored>
   Implication: <what this means for the current situation>
   Confidence: <retrieval confidence score>
   ```
5. Agent uses these to inform current decision-making

## Current Fallback

Until Phase 2 is available, use `recall_similar_decisions` tool instead:

```
recall_similar_decisions(situation="<describe the current situation>")
```

This searches the Judge's accumulated beliefs (flat JSON) for relevant entries.
It's less powerful than the Phase 2 episodic memory but provides basic recall.

**Limitations of fallback:**
- Only searches beliefs, not full journal history
- No semantic search (exact/substring match only)
- No confidence scoring
- No temporal context (doesn't know WHEN beliefs were formed)

## How to Use Now

1. Describe the current situation or question
2. Call `recall_similar_decisions` with that description
3. Review returned beliefs for relevance
4. Note: results will be much richer after Phase 2 migration

## Phase 2 Prerequisites

- `mem0ai` package installed
- `chromadb` running (embedded mode)
- Journal entries indexed via `EpisodicMemory.index_journal_entry()`
- `recall_episodic` tool registered in agent tools
