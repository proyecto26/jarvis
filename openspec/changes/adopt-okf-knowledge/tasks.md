## 1. OKF Core Module (`triforce/memory/okf.py`)

- [ ] 1.1 Define `OKFDocument` pydantic model — required `type`; recommended `title`, `description`, `tags` (list), `timestamp` (ISO 8601), `resource`; `extra="allow"` so unknown frontmatter keys survive round-trip
- [ ] 1.2 Implement frontmatter parser/serializer — YAML between `---` fences + free Markdown body; serialization preserves unknown keys (known keys first, unknown keys in original order)
- [ ] 1.3 Implement bundle-absolute link extraction helper (`/decisions/foo.md` style links from the body)
- [ ] 1.4 Add `Config.KNOWLEDGE_DIR` (default `knowledge/` at repo root, sibling of `journal/`)
- [ ] 1.5 Implement `OKFBundle` — directories `decisions/`, `reflections/`, `beliefs/`, `learnings/`, `questions/`; slug-based filenames `YYYY-MM-DD-<slug>.md` with numeric-suffix collision handling
- [ ] 1.6 `OKFBundle.write(doc)` — atomic file write (reuse `_atomic_write` pattern from `journal.py`), append one ISO-8601-dated line to root `log.md`, mark index dirty
- [ ] 1.7 `OKFBundle.rebuild_indexes()` — regenerate per-directory `index.md` (title + description per doc); `index.md`/`log.md` never parsed as knowledge documents

## 2. Judge / Journal Integration

- [ ] 2.1 Emit an OKF `Decision` doc when a `Judgment` is appended to the journal — reasoning, weight, verdict, links to related beliefs; journal write path stays the source of truth (emission is additive, journal output byte-identical)
- [ ] 2.2 Implement `supersede_belief(old, new, reason, ssgm_score)` in `triforce/memory/beliefs.py` (or thin wrapper module) — updates `judge_beliefs.json` (unchanged schema) AND writes OKF `Belief` docs in one call
- [ ] 2.3 Belief doc frontmatter: `valid_at`, `invalidated_at` (null while current), `supersedes` (bundle-absolute link to prior doc), `ssgm_score`
- [ ] 2.4 Superseding stamps `invalidated_at` into the old doc's frontmatter and creates the new doc — never deletes
- [ ] 2.5 Add `write_reflection(...)` tool to `triforce/modes/reflective.py`'s agent (alongside `append_to_state`) — persists an OKF `Reflection` doc linking the `Decision` docs it evaluates

## 3. Consolidation LLM Passes (`triforce/memory/consolidation.py`)

- [ ] 3.1 Author `triforce/llm/policies/consolidation.yaml` per `SCHEMA.md` — prefer cheap local (ollama) models; cloud fallback allowed for non-private summaries; batch job (latency budget not a constraint)
- [ ] 3.2 Implement the single `_llm_summarize(prompt) -> str | None` adapter — `get_router().route(RouteRequest(agent="consolidation"))` → provider registry (`triforce/llm/providers/registry.py`) → `provider.generate(...)`; NOT `for_agent()` (model-id resolution only); timeout-wrapped; `None` on any failure
- [ ] 3.3 Implement `compress_old_episodes()` — group journal entries older than 30 days by ISO week; per uncompressed week, LLM-summarize judgments/executions into 3-7 `Learning` OKF docs; mark source entries compressed in `knowledge/.consolidation-state.json`; preserve return shape (`weeks_compressed`, `entries_compressed`, `high_load_preserved`)
- [ ] 3.4 Implement `consolidate_journal_tier()` — per completed ISO week without a summary, LLM-write `journal/YYYY-Www-summary.md` from that week's dailies; return `weeks_summarised`
- [ ] 3.5 Graceful degradation — router unavailable or erroring returns `{"status": "deferred"}` exactly as today; both passes idempotent (re-running never duplicates summaries)

## 4. Importance-Accumulation Reflection Trigger

- [ ] 4.1 Hook `journal.append_to_section()` — each `Judgment` append adds its `action_weight` to a running sum; `Execution` appends count at flat weight 1 (no new schema field)
- [ ] 4.2 Persist the accumulator in `journal/.importance-accumulator.json` (atomic writes)
- [ ] 4.3 Add `Config.REFLECTION_IMPORTANCE_THRESHOLD` (default ~15); crossing it sets `reflection_due`
- [ ] 4.4 Expose `check_reflection_due()` / `reset_accumulator()`
- [ ] 4.5 Wire `triforce/temporal/workflows.py`'s consolidation/reflection path to consult the flag; nightly schedule remains the fallback trigger

## 5. Tests + Verification

- [ ] 5.1 Create `tests/` at repo root (none exists); add `dev` extra (`pytest`, `pytest-asyncio`) to `[project.optional-dependencies]` and minimal `[tool.pytest.ini_options]` (asyncio mode) in `pyproject.toml`
- [ ] 5.2 Unit tests: OKF round-trip incl. unknown-frontmatter preservation; link extraction; index/log maintenance
- [ ] 5.3 Unit tests: belief supersede chain — old doc gains `invalidated_at`, chain walkable via `supersedes`, nothing ever deleted
- [ ] 5.4 Unit tests: consolidation passes with a faked `_llm_summarize` (no network); deferred path when the fake returns `None`; idempotency on re-run
- [ ] 5.5 Unit tests: importance accumulator — threshold crossing sets `reflection_due`, `reset_accumulator()` clears it
- [ ] 5.6 Unit tests: journal integration emits `Decision` docs without altering journal output
- [ ] 5.7 Verification: `pytest` green; `ConsolidationWorker.run_nightly()` offline (no ollama) → passes 2 & 4 return `deferred`, passes 1 & 3 unchanged
- [ ] 5.8 Verification: generate a sample bundle and validate `index.md`/`log.md` shape against `examples/knowledge-catalog/okf/SPEC.md` conventions (read-only reference — never modify `examples/`)
