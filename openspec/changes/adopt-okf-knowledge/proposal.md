## Why

DANTE's Judge produces knowledge continuously — judgments, reflections, beliefs, learnings — but that knowledge is scattered across formats a human cannot browse and an agent cannot cross-link:

- The **journal** (`triforce/memory/journal.py`) stores daily Markdown + JSON pairs with typed sections. It is an excellent append-only log, but it is chronological, not topical: there is no way to follow a *belief* through its revisions or find every *decision* that touched a topic.
- **Beliefs** (`triforce/memory/beliefs.py`) live in a flat `judge_beliefs.json` that `update_belief()`/`remove_belief()` mutate **in place** — the history of *why* a belief changed is lost the moment it changes. The SSGM guard (`ssgm.py`) detects conflicts, but the resolution leaves no audit trail.
- Two of the four nightly consolidation passes (`triforce/memory/consolidation.py`) — `compress_old_episodes()` and `consolidate_journal_tier()` — are still `{"status": "deferred"}` stubs because they need LLM access, which only became available when the router landed on this branch (`triforce/llm/router.py`).

Research on 2026-07-12 identified Google's **Open Knowledge Format (OKF)** (`GoogleCloudPlatform/knowledge-catalog`, spec cloned at `examples/knowledge-catalog/okf/SPEC.md`) as the right target: typed Markdown documents with YAML frontmatter, bundle-absolute cross-links, and reserved `index.md`/`log.md` files. OKF documents are readable in Obsidian by a human and parseable/maintainable by agents — exactly the dual audience DANTE's knowledge base has.

The proposal: adopt OKF as the Judge's knowledge base, implement the two stubbed consolidation passes via the LLM router (writing their outputs as OKF documents), give beliefs an append-only supersede chain with bi-temporal-lite frontmatter (`valid_at`/`invalidated_at`, inspired by Graphiti), and add a Stanford-generative-agents-style importance-accumulation trigger so reflection fires when enough weighty judgments pile up — not only on the nightly schedule.

## What Changes

- Add `triforce/memory/okf.py` — OKF core module:
  - `OKFDocument` (pydantic, matching `triforce/memory/schema.py` style): required `type` frontmatter; recommended `title`, `description`, `tags`, `timestamp`, `resource`; **unknown frontmatter keys preserved round-trip**; free Markdown body; bundle-absolute link extraction.
  - `OKFBundle` rooted at new `Config.KNOWLEDGE_DIR` (default `knowledge/`, sibling of `journal/`): directories `decisions/`, `reflections/`, `beliefs/`, `learnings/`, `questions/`; regenerated `index.md` per directory; append-only root `log.md`; slug-based filenames (`YYYY-MM-DD-<slug>.md`); atomic writes reusing the `_atomic_write` pattern from `journal.py`.
- Modify `triforce/memory/journal.py` integration path — when a `Judgment` is appended, additionally emit an OKF `Decision` doc (reasoning, weight, verdict, belief links). The journal write path remains the source of truth; OKF emission is additive.
- Modify `triforce/memory/beliefs.py` — new `supersede_belief(old, new, reason, ssgm_score)`: `judge_beliefs.json` stays the unchanged fast runtime store; OKF `Belief` docs carry `valid_at`, `invalidated_at`, `supersedes`, `ssgm_score`; superseding stamps `invalidated_at` on the old doc and creates the new one — never deletes.
- Modify `triforce/modes/reflective.py` — new `write_reflection(...)` tool (alongside `append_to_state`) persisting an OKF `Reflection` doc that links the `Decision` docs it evaluates.
- Modify `triforce/memory/consolidation.py` — implement the two stubs:
  - One shared adapter `_llm_summarize(prompt) -> str | None` built on `get_router().route(RouteRequest(...))` → provider registry → `provider.generate(...)` (NOT `for_agent()`, which only resolves model-id strings for ADK constructors).
  - `compress_old_episodes()`: weekly LLM compression of >30-day-old journal entries into 3-7 `Learning` OKF docs, tracked in `knowledge/.consolidation-state.json`; return shape preserved.
  - `consolidate_journal_tier()`: LLM-written `journal/YYYY-Www-summary.md` per completed ISO week.
  - Router unavailable/error → `{"status": "deferred"}` exactly as today.
- Add `triforce/llm/policies/consolidation.yaml` — cheap-local-preferred policy per `SCHEMA.md`, cloud fallback allowed for non-private summaries.
- Add importance accumulator — `journal.append_to_section()` adds each `Judgment.action_weight` (executions count as 1) to `journal/.importance-accumulator.json`; crossing `Config.REFLECTION_IMPORTANCE_THRESHOLD` (default ~15) sets a `reflection_due` flag exposed via `check_reflection_due()` / `reset_accumulator()`; Temporal's consolidation/reflection path consults it (schedule remains the fallback trigger).
- Add `tests/` at repo root (none exists today) with a `dev` extra (`pytest`, `pytest-asyncio`) in `pyproject.toml`.

## Capabilities

### New Capabilities

- **`okf-knowledge-bundle`**: OKF-conformant document parse/serialize (type-only required frontmatter, unknown-key preservation, round-trip fidelity) and bundle maintenance (per-directory `index.md`, append-only `log.md`, atomic writes, slug filenames). Document types: `Decision`, `Reflection`, `Belief`, `Learning`, `Question`.
- **`belief-evolution`**: Append-only belief supersede chains with `valid_at`/`invalidated_at`/`supersedes` frontmatter. The JSON store stays the runtime cache; OKF docs are the audit trail; one call keeps both in sync.
- **`llm-consolidation`**: The two deferred consolidation passes implemented through the router's `route()` → `provider.generate()` path via a single fakeable adapter; idempotent, timeout-wrapped, degrading to `deferred` when no LLM is reachable.
- **`reflection-trigger`**: Importance accumulation over journal appends that raises a `reflection_due` flag for the Temporal layer, complementing (not replacing) the nightly schedule.

### Modified Capabilities

- **`judge-agent`**: Judgments additionally emit OKF `Decision` docs; belief mutations flow through `supersede_belief` so SSGM-ratified changes leave a chain.
- **`operating-modes`**: Reflective mode gains the `write_reflection` tool; reflection can now be triggered by accumulated importance, not just schedule.
- **`memory-consolidation`**: `run_nightly()` passes 2 and 4 go from stubs to real LLM-backed passes with unchanged return shapes and unchanged graceful degradation.

## Impact

- **New code**: `triforce/memory/okf.py` (~350 lines), consolidation pass bodies + adapter (~200 lines), belief supersede (~80 lines), accumulator (~60 lines), `consolidation.yaml`, `tests/` from scratch.
- **Dependencies**: none new at runtime — `pyyaml` and `pydantic` are already required; `pytest`/`pytest-asyncio` go in a new `dev` extra only.
- **Storage**: new `knowledge/` directory at repo root (gitignore treatment mirrors `journal/`); two small state files (`knowledge/.consolidation-state.json`, `journal/.importance-accumulator.json`).
- **Backward compatibility**: journal format, `judge_beliefs.json` schema, and consolidation return shapes are all unchanged. With no ollama/cloud reachable, `run_nightly()` behaves byte-identically to today (passes 2 & 4 return `deferred`).
- **Local-first invariant preserved**: no external services; everything degrades gracefully; the consolidation policy prefers local models and only falls back to cloud for non-private summaries.
- **Out of scope**: `temporal_beliefs.py` (Graphiti/KuzuDB) stays a stub; episodic retrieval backend (BM25/embeddings/Grafeo RRF) untouched; per-file advisory locking for concurrent agent writers deferred (single-process assumption documented).
- **Risk: dual-store divergence** between `judge_beliefs.json` and OKF `Belief` docs. Mitigation: `supersede_belief` writes both in one call; the JSON is explicitly the cache, OKF the audit trail.
- **Risk: router API drift.** `for_agent()` returns a model-id string only — it does not execute completions. All consolidation LLM traffic goes through the single `_llm_summarize` adapter so the call path is corrected (or faked in tests) in exactly one place.
