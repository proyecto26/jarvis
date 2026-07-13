"""Open Knowledge Format (OKF) documents and bundle management.

Implements the OKF v0.1 conventions (see the spec cloned at
``examples/knowledge-catalog/okf/SPEC.md``): markdown concept documents with
YAML frontmatter, per-directory ``index.md`` listings for progressive
disclosure, and a root ``log.md`` recording the update history.

The Judge's knowledge base lives in an :class:`OKFBundle` rooted at
``Config.KNOWLEDGE_DIR`` with typed subdirectories (decisions, reflections,
beliefs, learnings, questions). Unknown frontmatter keys are preserved
round-trip via ``OKFDocument.extras`` — spec conformance requires consumers
to keep keys they do not recognize.
"""

from __future__ import annotations

import logging
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from triforce.config import Config

logger = logging.getLogger(__name__)

OKF_VERSION = "0.1"

# Reserved filenames per SPEC.md §3.1 — never concept documents.
RESERVED_FILENAMES = ("index.md", "log.md")

# Bundle subdirectories used by DANTE (one per document type).
SUBDIRS = ("decisions", "reflections", "beliefs", "learnings", "questions")

_SUBDIR_DESCRIPTIONS = {
    "decisions": "Judge decisions with reasoning, action weight, and verdict.",
    "reflections": "Reflections evaluating past decisions and their outcomes.",
    "beliefs": "Belief documents with append-only supersede chains.",
    "learnings": "Learnings distilled from consolidated episodes.",
    "questions": "Open questions awaiting investigation.",
}

# Frontmatter keys mapped to explicit OKFDocument fields; everything else
# round-trips through ``extras`` (SPEC.md §4.1 Extensions).
_KNOWN_KEYS = ("type", "title", "description", "resource", "tags", "timestamp")

# Bundle-absolute markdown links: [text](/path/to/doc.md) — SPEC.md §5.1.
_BUNDLE_LINK_RE = re.compile(r"\[[^\]]*\]\((/[^)\s]+)\)")

_SLUG_RE = re.compile(r"[^a-z0-9]+")

_LOG_TITLE = "# Knowledge Update Log"

# Date section headings in log.md (``## YYYY-MM-DD``).
_LOG_DATE_HEADING_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})\b")


def _atomic_write(path: Path, content: str) -> None:
    """Write content to a file using atomic write (write-to-temp-then-rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mktemp(dir=path.parent, suffix=".tmp"))
    try:
        tmp.write_text(content, encoding="utf-8")
        # ``replace`` (not ``rename``) — atomically overwrites existing
        # targets on Windows (log.md / index.md are rewritten repeatedly).
        tmp.replace(path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def slugify(text: str) -> str:
    """Reduce text to a filesystem-safe slug (lowercase, hyphen-separated)."""
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    return slug or "untitled"


def extract_bundle_links(markdown: str) -> list[str]:
    """Extract bundle-absolute link targets (``/dir/doc.md``) from markdown.

    Relative links and external URLs are ignored. Order is preserved and
    duplicates are removed.
    """
    seen: dict[str, None] = {}
    for match in _BUNDLE_LINK_RE.finditer(markdown):
        seen.setdefault(match.group(1))
    return list(seen)


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Split an OKF document into (frontmatter_yaml, body)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("OKF document must start with a '---' frontmatter fence")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            frontmatter = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1 :]).lstrip("\n")
            return frontmatter, body
    raise ValueError("OKF frontmatter is missing its closing '---' fence")


class OKFDocument(BaseModel):
    """A single OKF concept document: YAML frontmatter + markdown body.

    ``type`` is the only required frontmatter field (SPEC.md §4.1). Unknown
    frontmatter keys are preserved in ``extras`` and re-emitted on
    serialization so documents round-trip losslessly.
    """

    type: str
    title: str | None = None
    description: str | None = None
    resource: str | None = None
    tags: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    extras: dict[str, Any] = Field(default_factory=dict)
    body: str = ""

    @field_validator("timestamp", mode="before")
    @classmethod
    def _coerce_timestamp(cls, value):
        # YAML parses ISO 8601 scalars into datetime/date objects — normalize
        # back to the ISO string form used throughout the journal schemas.
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value

    def frontmatter(self) -> dict[str, Any]:
        """Frontmatter mapping in canonical key order (known keys, then extras)."""
        data: dict[str, Any] = {"type": self.type}
        if self.title is not None:
            data["title"] = self.title
        if self.description is not None:
            data["description"] = self.description
        if self.resource is not None:
            data["resource"] = self.resource
        if self.tags:
            data["tags"] = list(self.tags)
        if self.timestamp:
            data["timestamp"] = self.timestamp
        for key, value in self.extras.items():
            if key not in data:
                data[key] = value
        return data

    def to_markdown(self) -> str:
        """Serialize to a markdown document with YAML frontmatter fences."""
        frontmatter = yaml.safe_dump(
            self.frontmatter(), sort_keys=False, allow_unicode=True
        ).strip()
        lines = ["---", frontmatter, "---", ""]
        body = self.body.strip("\n")
        if body:
            lines.extend([body, ""])
        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, text: str) -> "OKFDocument":
        """Parse a markdown document with YAML frontmatter fences."""
        frontmatter_raw, body = _split_frontmatter(text)
        data = yaml.safe_load(frontmatter_raw) if frontmatter_raw.strip() else {}
        if not isinstance(data, dict):
            raise ValueError("OKF frontmatter must be a YAML mapping")
        known = {key: data[key] for key in _KNOWN_KEYS if key in data}
        extras = {key: value for key, value in data.items() if key not in _KNOWN_KEYS}
        return cls(**known, extras=extras, body=body)

    def bundle_links(self) -> list[str]:
        """Bundle-absolute link targets referenced by this document's body."""
        return extract_bundle_links(self.body)

    def default_slug(self) -> str:
        """Slug derived from the title (or the type when untitled)."""
        return slugify(self.title or self.type)


class OKFBundle:
    """A knowledge bundle rooted at ``Config.KNOWLEDGE_DIR``.

    Layout::

        knowledge/
        ├── index.md          # root listing (regenerated)
        ├── log.md            # append-only, date-grouped update history
        ├── decisions/        # + reflections/, beliefs/, learnings/, questions/
        │   ├── index.md      # per-directory listing (regenerated)
        │   └── YYYY-MM-DD-<slug>.md

    Single-process writer assumption — per-file advisory locking is out of
    scope. All writes are atomic (tempfile + rename).
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else Config.KNOWLEDGE_DIR
        self._dirty: set[str] = set()

    # ------------------------------------------------------------------
    # Paths / layout
    # ------------------------------------------------------------------

    @property
    def log_path(self) -> Path:
        return self.root / "log.md"

    def ensure_layout(self) -> None:
        """Create the bundle root and its typed subdirectories."""
        for subdir in SUBDIRS:
            (self.root / subdir).mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, subdir: str, slug: str, doc_date: str) -> Path:
        """Compute a collision-free ``YYYY-MM-DD-<slug>.md`` path."""
        if subdir not in SUBDIRS:
            raise ValueError(
                f"Unknown bundle subdir: {subdir!r} (expected one of {SUBDIRS})"
            )
        directory = self.root / subdir
        base = f"{doc_date}-{slug}"
        path = directory / f"{base}.md"
        counter = 2
        while path.exists():
            path = directory / f"{base}-{counter}.md"
            counter += 1
        return path

    # ------------------------------------------------------------------
    # Read / write
    # ------------------------------------------------------------------

    def write(
        self,
        doc: OKFDocument,
        subdir: str,
        slug: str | None = None,
        doc_date: str | None = None,
        action: str = "Creation",
    ) -> Path:
        """Persist a document, append a ``log.md`` entry, and mark indexes dirty.

        Filenames are ``YYYY-MM-DD-<slug>.md``; on collision a numeric suffix
        is appended (``-2``, ``-3``, …) — existing documents are never
        overwritten. ``doc_date`` defaults to today (ISO 8601).
        """
        self.ensure_layout()
        if doc_date is None:
            doc_date = date.today().isoformat()
        if slug is None:
            slug = doc.default_slug()
        path = self._resolve_path(subdir, slugify(slug), doc_date)
        _atomic_write(path, doc.to_markdown())

        title = doc.title or path.stem
        message = f"**{action}**: Added [{title}](/{subdir}/{path.name})"
        if doc.description:
            message += f" - {doc.description}"
        self._append_log(message, doc_date)
        self._dirty.add(subdir)
        # Refresh this subdir's index (and the root index) immediately —
        # production writers use short-lived bundles and never call
        # rebuild_indexes() themselves, so dirty-tracking alone would leave
        # index.md permanently missing. The dirty set is kept for explicit
        # batch rebuilds. Index files are derived data; a refresh failure is
        # logged but never fails the write.
        try:
            self._write_subdir_index(subdir)
            self._rebuild_root_index()
        except Exception as exc:
            logger.warning("OKF index refresh failed for %s: %s", subdir, exc)
        logger.debug("OKF write: %s", path)
        return path

    def read(self, ref: str | Path) -> OKFDocument:
        """Load a document by path, bundle-absolute link, or concept ID."""
        if isinstance(ref, Path):
            path = ref
        else:
            rel = ref.lstrip("/")
            if not rel.endswith(".md"):
                rel += ".md"
            path = self.root / rel
        return OKFDocument.from_markdown(path.read_text(encoding="utf-8"))

    def documents(self, subdir: str) -> list[tuple[Path, OKFDocument]]:
        """All parseable concept documents in a subdirectory, sorted by filename."""
        directory = self.root / subdir
        docs: list[tuple[Path, OKFDocument]] = []
        if not directory.exists():
            return docs
        for path in sorted(directory.glob("*.md")):
            if path.name in RESERVED_FILENAMES:
                continue
            try:
                docs.append(
                    (path, OKFDocument.from_markdown(path.read_text(encoding="utf-8")))
                )
            except Exception as exc:
                # Permissive consumption (SPEC.md §9) — skip, never crash.
                logger.warning("Skipping unparseable OKF doc %s: %s", path, exc)
        return docs

    # ------------------------------------------------------------------
    # log.md — SPEC.md §7: date-grouped entries, newest first
    # ------------------------------------------------------------------

    def _append_log(self, message: str, log_date: str) -> None:
        heading = f"## {log_date}"
        if self.log_path.exists():
            lines = self.log_path.read_text(encoding="utf-8").splitlines()
        else:
            lines = [_LOG_TITLE, ""]
        if heading in lines:
            # Newest first within the day's section.
            lines.insert(lines.index(heading) + 1, f"* {message}")
        else:
            insert_at = 1 if lines and lines[0].startswith("# ") else 0
            while insert_at < len(lines) and lines[insert_at] == "":
                insert_at += 1
            # Chronological placement, newest first: skip forward past every
            # section dated the same or newer, stopping at the first strictly
            # older heading. Backdated writes (e.g. consolidation compressing
            # month-old weeks) therefore land BELOW today's entries instead
            # of unconditionally at the top. ISO dates compare as strings.
            while insert_at < len(lines):
                match = _LOG_DATE_HEADING_RE.match(lines[insert_at])
                if match and match.group(1) < log_date:
                    break
                insert_at += 1
            lines[insert_at:insert_at] = [heading, f"* {message}", ""]
        _atomic_write(self.log_path, "\n".join(lines) + "\n")

    # ------------------------------------------------------------------
    # index.md — SPEC.md §6: title + description listings
    # ------------------------------------------------------------------

    def rebuild_indexes(self, only_dirty: bool = False) -> list[Path]:
        """Regenerate ``index.md`` files (per-subdir + root). Returns paths written."""
        self.ensure_layout()
        targets = sorted(self._dirty) if only_dirty else list(SUBDIRS)
        written: list[Path] = []
        for subdir in targets:
            written.append(self._write_subdir_index(subdir))
        written.append(self._rebuild_root_index())
        self._dirty -= set(targets)
        return written

    def _write_subdir_index(self, subdir: str) -> Path:
        """Regenerate one subdirectory's ``index.md``. Returns its path."""
        lines = [f"# {subdir.capitalize()}", ""]
        entries = self.documents(subdir)
        if entries:
            for path, doc in entries:
                title = doc.title or path.stem
                suffix = f" - {doc.description}" if doc.description else ""
                lines.append(f"* [{title}]({path.name}){suffix}")
        else:
            lines.append("*No documents yet.*")
        lines.append("")
        index_path = self.root / subdir / "index.md"
        _atomic_write(index_path, "\n".join(lines))
        return index_path

    def _rebuild_root_index(self) -> Path:
        # The bundle-root index.md is the only index permitted a frontmatter
        # block, used to declare the OKF version (SPEC.md §11).
        lines = [
            "---",
            f"okf_version: \"{OKF_VERSION}\"",
            "---",
            "",
            "# Knowledge Base",
            "",
        ]
        for subdir in SUBDIRS:
            lines.append(
                f"* [{subdir.capitalize()}]({subdir}/) - {_SUBDIR_DESCRIPTIONS[subdir]}"
            )
        lines.append("")
        path = self.root / "index.md"
        _atomic_write(path, "\n".join(lines))
        return path
