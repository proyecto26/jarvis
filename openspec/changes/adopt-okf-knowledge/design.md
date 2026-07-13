# Design — Adopt OKF Knowledge Base + LLM Consolidation

## Context

DANTE's memory system has three layers that matured at different speeds. Episodic retrieval (BM25 + embeddings + Grafeo, weighted RRF) is done. The journal (`triforce/memory/journal.py`) is done — daily Markdown+JSON pairs with typed sections and an `_atomic_write` helper. But semantic knowledge is immature: beliefs are a flat JSON blob mutated in place, reflections evaporate into agent state, and the two consolidation passes that were supposed to distill the journal into durable knowledge are stubs waiting for LLM access.

The LLM router landed on this branch (`triforce/llm/router.py`, policies in `triforce/llm/policies/`, providers in `triforce/llm/providers/`), unblocking the stubs. And the OKF spec (`examples/knowledge-catalog/okf/SPEC.md`, cloned locally) gives us a documented, minimal, tool-friendly target format instead of inventing one.

This design keeps the same values as the router change: **additive, declarative, and observable**. Additive: the journal and `judge_beliefs.json` keep their exact formats — OKF is a new layer beside them, not a migration. Declarative: the consolidation model choice is a YAML policy, not code. Observable: every knowledge write appends to `log.md`, every belief change leaves a supersede chain.

## Goals

- A knowledge base a human can open in Obsidian and an agent can maintain programmatically.
- OKF conformance so external tooling (the knowledge-catalog ecosystem) works on DANTE's bundle unmodified.
- Belief history that survives belief change — audit "what did the Judge believe on date X, and why did that change?"
- The two stubbed consolidation passes actually running, on cheap local models by default.
- Reflection that triggers on *significance*, not only on the clock.

## Non-Goals

- Graphiti/KuzuDB temporal graph (`temporal_beliefs.py` stays `NotImplemented` — this change borrows only the `valid_at`/`invalid_at` *idea* as frontmatter).
- Changing episodic retrieval (BM25/embeddings/Grafeo RRF untouched).
- Multi-process write safety — three agents share one process today; per-file advisory locking is deliberately out of scope and documented as such.
- Migrating existing journal history into OKF retroactively (consolidation will digest it forward from the 30-day boundary naturally).

## Architecture

```
 Judge appends Judgment ──▶ journal.append_to_section()
                                  │            │
                     (source of truth)   (additive emission)
                                  │            │
                                  ▼            ▼
                          journal/YYYY-MM-DD.{md,json}   knowledge/decisions/YYYY-MM-DD-<slug>.md
                                  │                                   │
                                  │ accumulate action_weight          │ links
                                  ▼                                   ▼
                     journal/.importance-accumulator.json    knowledge/beliefs/… (supersede chains)
                                  │                                   ▲
                    threshold crossed → reflection_due                │ invalidated_at stamped,
                                  │                                   │ new doc created
                                  ▼                                   │
                       reflective.py agent ── write_reflection ──▶ knowledge/reflections/…
                                                                      │
 ConsolidationWorker.run_nightly()                                    │
   pass 2: compress_old_episodes() ── _llm_summarize ──▶ knowledge/learnings/… (3-7 per week)
   pass 4: consolidate_journal_tier() ── _llm_summarize ──▶ journal/YYYY-Www-summary.md
                    │
                    ▼
        get_router().route(RouteRequest(agent="consolidation"))
                    → provider registry → provider.generate(...)
```

Every write into `knowledge/` goes through `OKFBundle.write()`: atomic file write, one appended line in root `log.md`, index marked dirty; `rebuild_indexes()` regenerates the per-directory `index.md` files.

## Key Decisions

### D1 — OKF conformance boundaries

We conform to the spec exactly where it constrains us and use its extension points everywhere else:

- **Only `type` is required frontmatter.** `title`, `description`, `tags`, `timestamp` (ISO 8601), `resource` are recommended and emitted when known, but the parser never rejects a document missing them.
- **Unknown frontmatter keys are preserved round-trip.** Parse → modify body → serialize must not drop keys the model doesn't know about. This is what lets our custom belief-chain keys (`valid_at`, `invalidated_at`, `supersedes`, `ssgm_score`) ride on standard OKF documents, and lets other tools' keys survive DANTE's edits. Implementation: pydantic `model_config = ConfigDict(extra="allow")` plus explicit extra-key serialization order (known keys first, unknown keys in original order).
- **`index.md` and `log.md` are reserved files**, never treated as knowledge documents: `index.md` per directory is *regenerated* (title + description per doc, safe to delete), root `log.md` is *append-only* (ISO-8601-dated chronological entries, never rewritten).
- **Custom `type` values** (`Decision`, `Reflection`, `Belief`, `Learning`, `Question`) are conformant — OKF types are open-ended strings.
- **Links are bundle-absolute** (`/decisions/2026-07-12-foo.md`), extracted by a helper so reflections/beliefs can be traversed without path arithmetic.

### D2 — Append-only belief supersede chains (bi-temporal-lite)

Graphiti's insight — facts have a validity interval, and new facts *invalidate* rather than erase old ones — is adopted as frontmatter, without the graph database:

- `valid_at`: when the belief became held (set at creation).
- `invalidated_at`: `null` while current; stamped (never removed) when superseded.
- `supersedes`: bundle-absolute link to the prior belief doc, forming a chain walkable in either direction.
- `ssgm_score`: the SSGM conflict score that gated the change, preserving the *evidence* for the revision.

`supersede_belief(old, new, reason, ssgm_score)` does three things in one call: updates `judge_beliefs.json` (unchanged schema — it remains the fast runtime store), stamps `invalidated_at` into the old OKF doc, and writes the new OKF doc. Single call = the only defense against dual-store divergence, so it is the *only* sanctioned path for belief revision. Deletion does not exist at the OKF layer; `remove_belief` on the JSON side corresponds to invalidation-without-successor.

### D3 — Consolidation LLM path: `route()` → `provider.generate()`, one adapter

The tempting API is wrong: `Router.for_agent()` returns a model-id *string* for ADK `Agent(model=...)` constructors — it never executes a completion. The correct path is:

1. `get_router().route(RouteRequest(agent="consolidation"))` → `RouteDecision`
2. resolve the decision's provider via `triforce/llm/providers/registry.py`
3. `provider.generate(...)` (abstract on `Provider`, `providers/base.py`; implemented by e.g. `OllamaProvider.generate`)

All of this lives behind **one** module-level adapter in `consolidation.py`:

```
_llm_summarize(prompt: str) -> str | None   # None = LLM unavailable → caller returns {"status": "deferred"}
```

Rationale: (a) tests fake exactly one function, no network ever; (b) both passes share timeout/error handling; (c) if the router API drifts again, one call site changes. The `consolidation.yaml` policy prefers cheap local (ollama) models with cloud fallback allowed for non-private summaries — latency budget is irrelevant for a batch job, so the policy trades latency for cost aggressively.

Both passes are idempotent via `knowledge/.consolidation-state.json` (compressed-week bookkeeping) and by checking for existing `journal/YYYY-Www-summary.md` files — re-running never duplicates output. Graceful degradation is preserved *exactly*: router unreachable or erroring returns `{"status": "deferred"}` byte-identically to today's stubs.

### D4 — Importance-accumulation reflection trigger

Stanford's generative-agents pattern: reflect when accumulated importance since the last reflection crosses a threshold, not on a fixed cadence.

- Hook point: `journal.append_to_section()` — the single choke point through which all typed journal writes flow.
- Weight source: `Judgment.action_weight` (`schema.py`, default 1). `Execution` has no weight field and *does not get one* — executions count at a flat 1. Adding a field would churn the schema for no signal gain.
- State: `journal/.importance-accumulator.json` (atomic writes), holding running sum + last-reset timestamp.
- Threshold: `Config.REFLECTION_IMPORTANCE_THRESHOLD`, default ~15.
- Consumption: `check_reflection_due()` / `reset_accumulator()` exposed for `triforce/temporal/workflows.py`'s consolidation/reflection path. The trigger *raises a flag*; Temporal decides when to act. The nightly schedule remains the fallback so a quiet week still gets reflected on.

### D5 — Atomic writes everywhere

Every persisted file in this change — OKF docs, `log.md` appends, `index.md` regeneration, both state files, weekly summaries — uses the tempfile+rename pattern already proven in `journal.py`'s `_atomic_write`. Windows is a first-class target; rename-over-existing semantics are handled the same way `journal.py` already does.

## Tradeoffs

- **Dual store for beliefs.** Two representations of the same belief can theoretically diverge. We accept this because migrating `judge_beliefs.json` consumers in the same change would balloon the risk surface; the single-call `supersede_belief` and the cache-vs-audit-trail framing bound the damage. A follow-up change may make OKF the source of truth and regenerate the JSON.
- **Regenerated indexes are eventually consistent.** `index.md` can lag between `write()` and `rebuild_indexes()`. Acceptable: indexes are a human convenience, `log.md` is the authoritative record, and the nightly worker rebuilds.
- **LLM-written learnings are lossy.** Compressing a week of judgments into 3-7 `Learning` docs discards detail by design. Mitigation: source journal entries are *marked* compressed in the state file, never deleted — the raw material remains.
- **Flat weight for executions.** Underweights heavy executions, but avoids schema churn; if reflection triggers prove miscalibrated, tune the threshold before adding fields.

## Risks We Accept

- **Single-process assumption.** Three agents writing the bundle concurrently from separate processes could interleave `log.md` appends. Documented, not solved — Temporal serializes the writers that matter today.
- **Slug collisions within a day** are possible for identically-titled docs; `OKFBundle` disambiguates with a numeric suffix rather than failing.
- **Local model quality for summarization.** A small ollama model may write mediocre learnings. The policy's cloud fallback for non-private content is the pressure valve; the SSGM audit pass (already implemented) is downstream quality control.

## Open Questions

- **Q1:** Should `Question` docs be produced automatically (e.g. when SSGM detects an unresolved conflict) or only by the reflective agent? *Initial answer: reflective agent only.* Automatic question generation without curation risks a junk drawer; revisit after observing reflection output.
- **Q2:** Should `log.md` be size-capped/rotated? *Not yet.* Append-only per spec; at DANTE's write volume it will take years to matter. Revisit if it exceeds a few MB.
- **Q3:** Should retrieval (BM25/embeddings) index the `knowledge/` bundle too? *Out of scope here* — but the bundle's plain-Markdown format makes it trivially indexable later, which is part of why OKF was chosen.

## Related Work in the Repo

- **`add-specialized-llm-router`** — provides the `route()`/policy/provider machinery this change consumes; `consolidation.yaml` follows its `SCHEMA.md`.
- **`triforce/memory/journal.py`** — `_atomic_write` and the typed-section append path are the idioms this change extends.
- **`triforce/memory/ssgm.py`** — `SSGMGuard.check_conflict()` scores feed straight into belief-doc frontmatter.
- **`examples/knowledge-catalog/okf/SPEC.md`** — the conformance target (read-only reference; `examples/` is never modified).
