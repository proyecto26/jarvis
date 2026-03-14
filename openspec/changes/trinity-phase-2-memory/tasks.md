## 1. Dependencies & Configuration (~0.5 days)

- [ ] 1.1 Add memory dependencies to `pyproject.toml`: `mem0ai`, `chromadb`, `graphiti-core`, `kuzu`, `sentence-transformers`
- [ ] 1.2 Add embedding backend config to `triforce/config.py`: `EMBEDDING_BACKEND` (ollama|gemini), `OLLAMA_HOST`, `CHROMA_PATH`, `KUZU_PATH`
- [ ] 1.3 Update `.env.example` with new memory config variables and defaults
- [ ] 1.4 Create `triforce/memory/backends.py` — factory that returns configured Mem0 client and Graphiti client based on env vars

## 2. Episodic Memory — Mem0 + ChromaDB (~2 days)

- [ ] 2.1 Implement `triforce/memory/episodic.py` — `EpisodicMemory` class wrapping Mem0 with ChromaDB embedded backend
- [ ] 2.2 Add `index_journal_entry(entry: JournalEntry)` method — extracts text from each section (DreamCycle, Judgment, Execution, Learning), adds to Mem0 with metadata (date, section type, cognitive load score)
- [ ] 2.3 Add `recall_similar(query: str, top_k: int = 5) -> list[EpisodicResult]` method — Mem0 hybrid retrieval, returns results as ActMem-style reasoning chains (not flat facts)
- [ ] 2.4 Add `reinforce(entry_id: str)` method — resets FadeMem decay clock for a specific entry (called when an old memory is retrieved and found relevant)
- [ ] 2.5 Implement `EpisodicResult` Pydantic model: `episode_id`, `date`, `section`, `content`, `relevance_score`, `reasoning_chain`, `source_anchor`
- [ ] 2.6 Update `triforce/tools/journal_tools.py` — after `write_journal_entry` succeeds, async-schedule indexing to Mem0 via `episodic.index_journal_entry()`
- [ ] 2.7 Implement `recall_similar_decisions` ADK tool upgrade in `triforce/tools/memory_tools.py` — replaces flat JSON scan with `EpisodicMemory.recall_similar()`; formats output as reasoning chains
- [ ] 2.8 Verify Ollama embedding backend: run `nomic-embed-text` and confirm Mem0 indexes correctly
- [ ] 2.9 Verify Gemini embedding backend: confirm fallback path works with `EMBEDDING_BACKEND=gemini`

## 3. Temporal Beliefs — Graphiti + KuzuDB (~1 week)

- [ ] 3.1 Create `triforce/memory/temporal_beliefs.py` — `TemporalBeliefStore` class wrapping Graphiti with KuzuDB embedded backend
- [ ] 3.2 Implement `write_belief(belief: BeliefMutation) -> BeliefEdge` — creates temporal edge in graph with `valid_from=now`, automatically closes any superseded beliefs with `valid_until=now`
- [ ] 3.3 Implement `query_current(topic: str) -> list[BeliefEdge]` — returns all beliefs currently valid (valid_until is null), filtered by topic similarity
- [ ] 3.4 Implement `query_at(topic: str, at: datetime) -> list[BeliefEdge]` — point-in-time query: beliefs valid at a specific datetime (enables "what did Jarvis believe on Jan 15th?")
- [ ] 3.5 Implement `get_belief_history(belief_id: str) -> list[BeliefEdge]` — full lineage of a belief from origin through all mutations
- [ ] 3.6 Implement `BeliefEdge` Pydantic model: `id`, `content`, `strength`, `valid_from`, `valid_until`, `supersedes_id`, `source_episode_id`, `reasoning`, `tags`
- [ ] 3.7 Implement `migrate_from_json()` — one-time migration of `memory/judge_beliefs.json` to KuzuDB; sets `valid_from` to file modification date; preserves `reason` as `reasoning`
- [ ] 3.8 Upgrade `update_beliefs` ADK tool in `triforce/tools/memory_tools.py` — now calls `TemporalBeliefStore.write_belief()` instead of mutating JSON directly; passes through SSGM check first
- [ ] 3.9 Add `query_beliefs_at` ADK tool — allows Judge and Executor to query the belief graph at a specific point in time
- [ ] 3.10 Write integration test: create belief → supersede it → query at both timestamps → confirm correct values returned

## 4. SSGM Memory Safety (~1 day)

- [ ] 4.1 Implement `triforce/memory/ssgm.py` — `SSGMGuard` class with conflict detection logic
- [ ] 4.2 Add `check_conflict(new_belief: BeliefMutation, existing: list[BeliefEdge]) -> ConflictReport` — computes cosine similarity between new belief and existing beliefs with strength > 0.7; flags if similarity > 0.7
- [ ] 4.3 Implement `ConflictReport` Pydantic model: `has_conflict`, `conflicting_belief_id`, `similarity_score`, `recommendation` (merge|supersede|coexist|review)
- [ ] 4.4 Wire SSGM guard into `update_beliefs` tool: call `check_conflict` before writing; if `has_conflict`, include conflict report in tool output for Judge to resolve
- [ ] 4.5 Add stability monitor: track belief mutation rate over rolling 7-day window; if mutation rate > 5/day, emit warning to journal (potential belief drift)

## 5. Nightly Consolidation Worker (~1.5 days)

- [ ] 5.1 Implement `triforce/memory/consolidation.py` — `ConsolidationWorker` class
- [ ] 5.2 Add `run_fade_decay()` — applies FadeMem equation `strength × e^(−0.02 × days_since_last_access)` to all Mem0 entries; removes entries below `strength < 0.05`
- [ ] 5.3 Add `compress_old_episodes(threshold_days: int = 30)` — uses LLM to summarize groups of judgments older than threshold into single learning-summary entries; replaces originals in Mem0 index with compressed version
- [ ] 5.4 Add `run_ssgm_audit()` — scans all beliefs added in the last 24h for conflicts; generates conflict report appended to journal
- [ ] 5.5 Add `consolidate_journal_tier(date_range)` — TiMem-inspired: reads raw daily entries for a week, writes a weekly episode-summary entry to journal
- [ ] 5.6 Expose `consolidation.run_nightly()` as entry point callable from Sleep mode and from Temporal scheduler (Phase Temporal spec)

## 6. Agent Integration (~1 day)

- [ ] 6.1 Update `triforce/agents/dreamer/agent.py` — at session start, seed `dream_seeds` state key with top-5 episodic memories related to current context via `EpisodicMemory.recall_similar()`
- [ ] 6.2 Update `triforce/agents/executor/agent.py` — at session start, seed working context with top-3 recent episodic memories for task continuity
- [ ] 6.3 Update Judge filter and collaborator agents — `recall_similar_decisions` now calls Mem0; `update_beliefs` now calls Graphiti with SSGM check
- [ ] 6.4 Update `triforce/memory/schema.py` — add `cognitive_load_score: float` (0.0–1.0) to `JournalEntry`; add `source_episode_id: str | None` to `BeliefMutation`
- [ ] 6.5 Update Reflective mode instruction to include temporal belief query: "What did you believe at the time of this event? Has that belief changed since?"

## 7. Verification (~0.5 days)

- [ ] 7.1 Run Phase 1 smoke test end-to-end — confirm existing ADK agents still work with upgraded memory tools
- [ ] 7.2 Test episodic recall: write 3 journal entries → query for similar → confirm relevant results with reasoning chains
- [ ] 7.3 Test temporal beliefs: write belief → supersede it → `query_at(before)` returns old → `query_at(after)` returns new
- [ ] 7.4 Test SSGM: propose conflicting belief at strength 0.8 → confirm conflict report returned before write
- [ ] 7.5 Test FadeMem: create entry → simulate 60-day decay → confirm strength drops to ~0.30
- [ ] 7.6 Test JSON migration: run `migrate_from_json()` → confirm all existing beliefs appear in KuzuDB with correct timestamps
