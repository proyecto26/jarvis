## 1. Dependencies & Configuration (~0.5 days)

- [x] 1.1 Replace memory dependencies in `pyproject.toml`: `sentence-transformers` + `grafeo` (originally planned: `mem0ai` + `chromadb` + `graphiti-core` + `kuzu`). Keep `[memory-full]` extras with `graphiti-core` + `kuzu` for the opt-in fallback path.
- [x] 1.2 Add embedding backend config to `triforce/config.py`: `EMBEDDING_BACKEND` (sentence-transformers | ollama | gemini), `EPISODIC_DB_PATH`
- [x] 1.3 Update `.env.example` with memory config variables and defaults
- [ ] 1.4 Create `triforce/memory/backends.py` — factory that returns the configured embedding backend handle — *Deferred: episodic.py currently instantiates sentence-transformers directly. Factory becomes useful when a second backend (ollama, gemini) lands.*

## 2. Episodic Memory — BM25 + sentence-transformers + Grafeo (~2 days)

- [x] 2.1 Implement `triforce/memory/episodic.py` — `EpisodicMemory` class with 3-tier graceful degradation
- [x] 2.2 Add `index_journal_entry(entry: JournalEntry)` method — extracts text from each section, tokenizes for BM25 (with bigrams), creates Grafeo node when available, marks index dirty
- [x] 2.3 Add `recall_similar(query: str, top_k: int = 5) -> list[dict]` method — weighted Reciprocal Rank Fusion over BM25 + embeddings + graph rankers
- [x] 2.4 Add `reinforce(entry_id: str)` method — resets FadeMem decay clock for a specific entry
- [x] 2.5 Add `get_decay_strength(entry_id, decay_rate=0.02)` — exposes Ebbinghaus strength
- [x] 2.6 Wire `recall_episodic`, `check_belief_conflict`, `reinforce_memory` ADK tools in `triforce/tools/memory_tools.py`
- [x] 2.7 Register memory tools on the executor agent
- [ ] 2.8 Verify Ollama embedding backend as alternative — *Pending: only sentence-transformers backend implemented today. Ollama path is documented in `.env.example` but not coded.*
- [ ] 2.9 Verify Gemini embedding backend as alternative — *Pending: same reason as 2.8.*

## 3. Temporal Beliefs — Grafeo embedded graph (~1 week)

- [x] 3.1 Create `triforce/memory/temporal_beliefs.py` — `TemporalBeliefStore` class with graceful degradation
- [ ] 3.2 Implement `write_belief(...)` — *Stub: method exists with full signature and docstring; raises `NotImplementedError` until live Grafeo schema is finalized. The `triforce/memory/beliefs.py` flat-JSON store remains the default belief path today.*
- [ ] 3.3 Implement `query_current(topic)` — *Stub: same status as 3.2.*
- [ ] 3.4 Implement `query_at(topic, at: datetime)` — *Stub: same status as 3.2.*
- [ ] 3.5 Implement `get_belief_history(belief_id)` — *Stub: same status as 3.2.*
- [ ] 3.6 Define `BeliefEdge` Pydantic model — *Pending with 3.2.*
- [x] 3.7 Implement `migrate_from_json(dry_run: bool = True)` — read-only dry-run mode works without Grafeo; live mode raises until 3.2 lands
- [ ] 3.8 Upgrade `update_beliefs` ADK tool to call `write_belief()` — *Pending: depends on 3.2.*
- [ ] 3.9 Add `query_beliefs_at` ADK tool — *Pending: depends on 3.4.*
- [ ] 3.10 Write integration test for supersession + point-in-time query — *Pending: depends on 3.2–3.4.*

## 4. SSGM Memory Safety (~1 day)

- [x] 4.1 Implement `triforce/memory/ssgm.py` — `SSGMGuard` class with `check_conflict()`
- [x] 4.2 `check_conflict(new_belief)` — computes string similarity (SequenceMatcher) against `load_beliefs()` results; flags when both similarity and existing strength exceed 0.7
- [x] 4.3 Define `ConflictReport` dataclass with `has_conflict`, `conflicting_belief_id`, `conflicting_belief_text`, `similarity_score`, `recommendation`
- [x] 4.4 Wire SSGM guard into `update_beliefs` tool call path — implemented in `triforce/tools/memory_tools.py:update_beliefs`; on conflict, the tool returns `status: "conflict_detected"` with the full `ConflictReport` instead of writing
- [x] 4.5 Stability monitor (`check_stability`) — tracks belief mutation rate over rolling 7-day window with drift warning at >5 mutations and oscillation detection at >=3 repeats

## 5. Nightly Consolidation Worker (~1.5 days)

- [x] 5.1 Implement `triforce/memory/consolidation.py` — `ConsolidationWorker` class with `run_nightly()` entry point
- [ ] 5.2 Implement `run_fade_decay()` — *Stub: returns zero counts. Needs to walk `EpisodicMemory._last_access` and remove entries below the threshold.*
- [ ] 5.3 Implement `compress_old_episodes(threshold_days=30)` — *Stub: depends on an LLM call path. Defer until `add-specialized-llm-router` is in place so we can pick a cheap local model for compression.*
- [ ] 5.4 Implement `run_ssgm_audit()` — *Stub: needs to iterate recent beliefs and call `SSGMGuard.check_conflict()` per belief, then write findings to today's journal under `open_questions`.*
- [ ] 5.5 Implement `consolidate_journal_tier(date_range)` — *Stub: TiMem-style weekly summaries; deferred with 5.3 (same LLM dependency).*
- [x] 5.6 Expose `run_nightly()` as entry point callable from `ConsolidationWorkflow` (already invoked via Temporal in `triforce/temporal/workflows.py`)

## 6. Agent Integration (~1 day)

- [ ] 6.1 Update Dreamer agent — seed `dream_seeds` state key with top-5 episodic memories at session start — *Pending: needs a startup hook in `dreamer/agent.py`.*
- [ ] 6.2 Update Executor agent — seed working context with top-3 recent episodic memories at session start — *Pending: needs a startup hook in `executor/agent.py`. Note: the recall TOOL is wired (executor can call `recall_episodic` mid-turn); the missing piece is the implicit pre-load.*
- [x] 6.3 Update Judge filter and collaborator — `recall_similar_decisions` now uses `EpisodicMemory.recall_similar()` (with flat-JSON fallback when index empty); `update_beliefs` runs SSGM check before writing
- [x] 6.4 Extend `triforce/memory/schema.py` — added `cognitive_load_score: float` (0.0–1.0, default 0.5) to `JournalMetadata` and `source_episode_id: Optional[str]` to `BeliefMutation`
- [ ] 6.5 Update Reflective mode instruction to include temporal belief query — *Pending: depends on 3.4 (`query_at`).*

## 7. Verification (~0.5 days)

- [x] 7.1 Smoke test: end-to-end episodic recall on synthetic data (`benchmarks/memory_bench.py` — 17 experiments logged in `autoresearch.jsonl`)
- [x] 7.2 Test episodic recall: P@5 = 0.76 on mixed keyword/semantic queries, F1 = 1.00 for contradiction detection
- [ ] 7.3 Test temporal beliefs: write belief → supersede → `query_at(before)`/`query_at(after)` — *Pending: depends on §3.*
- [ ] 7.4 Test SSGM live: propose conflicting belief at strength 0.8 → confirm conflict report — *Pending: depends on §4.4 wiring.*
- [ ] 7.5 Test FadeMem: simulate 60-day decay → confirm strength ≈ 0.30 — *Pending: depends on §5.2.*
- [ ] 7.6 Test JSON migration: run `migrate_from_json(dry_run=False)` — *Pending: depends on §3.2.*

## Implementation Notes

This plan was originally drafted in March 2026 specifying **Mem0 + ChromaDB + Graphiti + KuzuDB**. In May 2026, an autoresearch experiment loop (16 successful experiments, 1 baseline; full log in `autoresearch.jsonl`) benchmarked 6 candidate architectures and identified a winner that beats the originally-planned stack on composite score, write latency, AND memory footprint. The winner — **BM25 + sentence-transformers (all-MiniLM-L6-v2) + Grafeo** with weighted Reciprocal Rank Fusion — is now reflected in §2.

**What's complete:**
- Episodic memory recall (Tier 0/1/2 with graceful degradation)
- SSGM conflict detection (string-similarity baseline)
- Stability monitor with drift + oscillation detection
- ADK memory tools wired into the executor agent
- Benchmark harness with reproducible measurements

**What's deferred (in priority order):**
1. **`TemporalBeliefStore` live writes (§3.2–3.6)** — design is locked, implementation needs Grafeo schema finalization
2. **Agent session-start seeding (§6.1, §6.2)** — small but architecturally meaningful change
3. **`ConsolidationWorker` real implementations (§5.2–5.5)** — gated on either local LLM access (§5.3, §5.5) or completion of episodic decay tracking integration (§5.2, §5.4)
4. **Schema extensions (§6.4)** — `cognitive_load_score` and `source_episode_id` are useful but no current consumer requires them

These deferred items are now individually trackable line items rather than vague "Phase 2 future work."
