# OKF Knowledge Bundle Spec

## ADDED Requirements

### Requirement: OKF Document Round-Trip Fidelity

The system SHALL parse and serialize OKF documents (YAML frontmatter between `---` fences + free Markdown body) such that only the `type` frontmatter key is required, recommended keys (`title`, `description`, `tags`, `timestamp`, `resource`) are optional, and unknown frontmatter keys are preserved byte-for-byte in value through a parse → modify → serialize cycle.

#### Scenario: Document with only a type parses successfully

- **WHEN** a document's frontmatter contains only `type: Decision`
- **THEN** parsing succeeds
- **AND** all recommended fields are `None`/empty on the resulting `OKFDocument`

#### Scenario: Unknown frontmatter keys survive round-trip

- **WHEN** a document carries frontmatter keys the model does not declare (e.g. `custom_tool_key: 42`)
- **AND** the document is parsed, its body modified, and re-serialized
- **THEN** `custom_tool_key: 42` is present in the output frontmatter
- **AND** known keys are emitted first, unknown keys in their original order

#### Scenario: Missing type is rejected

- **WHEN** a document's frontmatter lacks the `type` key
- **THEN** parsing raises a validation error naming the missing key

### Requirement: Bundle-Absolute Link Extraction

The system SHALL extract bundle-absolute links (paths beginning with `/`, e.g. `/decisions/2026-07-12-foo.md`) from a document body so cross-document traversal requires no path arithmetic.

#### Scenario: Decision links are extracted from a reflection body

- **WHEN** a `Reflection` body contains `[prior decision](/decisions/2026-07-10-rate-limit.md)`
- **THEN** the link helper returns `/decisions/2026-07-10-rate-limit.md`
- **AND** relative links and external URLs are not returned

### Requirement: Bundle Layout and Reserved Files

The bundle SHALL be rooted at `Config.KNOWLEDGE_DIR` (default `knowledge/`) with directories `decisions/`, `reflections/`, `beliefs/`, `learnings/`, `questions/`. Per OKF spec, `index.md` (per directory) and the root `log.md` are reserved files: they SHALL never be parsed as knowledge documents, `index.md` SHALL be regenerable from scratch, and `log.md` SHALL be append-only.

#### Scenario: Writing a document updates the log

- **WHEN** `OKFBundle.write(doc)` persists a new `Learning`
- **THEN** the file lands under `learnings/` with a `YYYY-MM-DD-<slug>.md` name
- **AND** exactly one ISO-8601-dated line is appended to the root `log.md`
- **AND** no existing `log.md` content is modified

#### Scenario: Index regeneration lists title and description

- **WHEN** `rebuild_indexes()` runs on a directory containing three documents
- **THEN** that directory's `index.md` is rewritten listing each document's title and description
- **AND** deleting `index.md` before the call produces the identical file (regenerable)

#### Scenario: Reserved files are excluded from document iteration

- **WHEN** the bundle enumerates the documents of a directory
- **THEN** `index.md` and `log.md` are never yielded

### Requirement: Atomic Writes

Every file the bundle persists (documents, `log.md`, `index.md`) SHALL be written atomically via the tempfile+rename pattern used by `journal.py`'s `_atomic_write`, on Windows and POSIX alike.

#### Scenario: Interrupted write leaves no partial document

- **WHEN** a write fails after the temp file is created but before rename
- **THEN** the target path contains either the previous complete content or nothing
- **AND** never a truncated document

### Requirement: Slug Collision Handling

Filenames SHALL be `YYYY-MM-DD-<slug>.md`; when two same-day documents produce the same slug, the bundle SHALL disambiguate with a numeric suffix rather than overwrite or fail.

#### Scenario: Two same-titled documents on one day

- **WHEN** two `Decision` docs titled "Rate limit" are written on 2026-07-12
- **THEN** both files exist (e.g. `2026-07-12-rate-limit.md` and `2026-07-12-rate-limit-2.md`)
- **AND** neither write overwrote the other
