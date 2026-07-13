"""Tests for triforce.memory.okf — OKF documents and bundle management."""

import pytest

from triforce.memory.okf import (
    OKF_VERSION,
    SUBDIRS,
    OKFBundle,
    OKFDocument,
    extract_bundle_links,
    slugify,
)


def make_doc(**overrides) -> OKFDocument:
    fields = {
        "type": "Decision",
        "title": "Approve nightly consolidation",
        "description": "The Judge approved the nightly consolidation run.",
        "tags": ["judge", "consolidation"],
        "timestamp": "2026-07-12T03:00:00",
        "body": "# Reasoning\n\nLow risk, high value.\n",
    }
    fields.update(overrides)
    return OKFDocument(**fields)


# ----------------------------------------------------------------------
# Frontmatter round-trip
# ----------------------------------------------------------------------


class TestRoundTrip:
    def test_known_fields_round_trip(self):
        doc = make_doc(resource="file:///journal/2026-07-12.md")
        parsed = OKFDocument.from_markdown(doc.to_markdown())
        assert parsed.type == doc.type
        assert parsed.title == doc.title
        assert parsed.description == doc.description
        assert parsed.resource == doc.resource
        assert parsed.tags == doc.tags
        assert parsed.timestamp == doc.timestamp
        assert parsed.body.strip() == doc.body.strip()

    def test_unknown_frontmatter_keys_preserved(self):
        extras = {
            "valid_at": "2026-07-01T00:00:00",
            "invalidated_at": None,
            "supersedes": "/beliefs/2026-06-01-old-belief.md",
            "ssgm_score": 0.42,
        }
        doc = make_doc(type="Belief", extras=extras)
        parsed = OKFDocument.from_markdown(doc.to_markdown())
        assert parsed.extras == extras
        # Round-trip a second time to prove stability.
        reparsed = OKFDocument.from_markdown(parsed.to_markdown())
        assert reparsed.extras == extras

    def test_parse_handwritten_document_with_unknown_keys(self):
        text = (
            "---\n"
            "type: Playbook\n"
            "title: Incident response\n"
            "custom_key: custom value\n"
            "priority: 3\n"
            "---\n"
            "\n"
            "# Steps\n"
            "\n"
            "1. Check the dashboard.\n"
        )
        doc = OKFDocument.from_markdown(text)
        assert doc.type == "Playbook"
        assert doc.extras == {"custom_key": "custom value", "priority": 3}
        assert "# Steps" in doc.body
        # Unknown keys survive serialization.
        assert "custom_key: custom value" in doc.to_markdown()

    def test_type_is_required(self):
        with pytest.raises(Exception):
            OKFDocument.from_markdown("---\ntitle: No type here\n---\n\nBody.\n")

    def test_missing_frontmatter_fence_rejected(self):
        with pytest.raises(ValueError):
            OKFDocument.from_markdown("# Just markdown, no frontmatter\n")


# ----------------------------------------------------------------------
# Link extraction
# ----------------------------------------------------------------------


class TestLinkExtraction:
    def test_extracts_bundle_absolute_links_only(self):
        body = (
            "See [old belief](/beliefs/2026-06-01-old.md) and the\n"
            "[decision](/decisions/2026-07-12-approve.md).\n"
            "Relative [neighbor](./other.md) and external\n"
            "[docs](https://example.com/page.md) are ignored.\n"
            "Duplicate [again](/beliefs/2026-06-01-old.md).\n"
        )
        links = extract_bundle_links(body)
        assert links == [
            "/beliefs/2026-06-01-old.md",
            "/decisions/2026-07-12-approve.md",
        ]

    def test_document_bundle_links_helper(self):
        doc = make_doc(body="Links to [a](/learnings/2026-07-01-a.md).")
        assert doc.bundle_links() == ["/learnings/2026-07-01-a.md"]

    def test_no_links(self):
        assert extract_bundle_links("Plain prose without links.") == []


# ----------------------------------------------------------------------
# Bundle write + log.md
# ----------------------------------------------------------------------


class TestBundleWrite:
    def test_write_creates_file_and_log_line(self, tmp_path):
        bundle = OKFBundle(root=tmp_path)
        doc = make_doc()
        path = bundle.write(doc, "decisions", doc_date="2026-07-12")

        assert path.exists()
        assert path.parent == tmp_path / "decisions"
        assert path.name == "2026-07-12-approve-nightly-consolidation.md"

        # File parses back to an equivalent document.
        loaded = bundle.read(path)
        assert loaded.title == doc.title

        # log.md exists with a date heading + entry linking the new doc.
        log_text = bundle.log_path.read_text(encoding="utf-8")
        assert "## 2026-07-12" in log_text
        assert (
            "[Approve nightly consolidation]"
            "(/decisions/2026-07-12-approve-nightly-consolidation.md)" in log_text
        )
        assert doc.description in log_text

    def test_write_groups_log_entries_by_date(self, tmp_path):
        bundle = OKFBundle(root=tmp_path)
        bundle.write(make_doc(title="First"), "decisions", doc_date="2026-07-12")
        bundle.write(make_doc(title="Second"), "decisions", doc_date="2026-07-12")
        bundle.write(make_doc(title="Earlier"), "decisions", doc_date="2026-07-11")

        log_text = bundle.log_path.read_text(encoding="utf-8")
        assert log_text.count("## 2026-07-12") == 1
        assert log_text.count("## 2026-07-11") == 1
        assert "[First]" in log_text and "[Second]" in log_text

    def test_backdated_write_lands_below_newer_sections(self, tmp_path):
        # Consolidation backdates Learning docs to the compressed week's
        # Sunday — the log must stay newest-first anyway (SPEC.md §7).
        bundle = OKFBundle(root=tmp_path)
        bundle.write(make_doc(title="Today"), "decisions", doc_date="2026-07-13")
        bundle.write(
            make_doc(type="Learning", title="Old week"),
            "learnings",
            doc_date="2026-06-07",
        )
        bundle.write(make_doc(title="Newer"), "decisions", doc_date="2026-07-14")

        log_lines = bundle.log_path.read_text(encoding="utf-8").splitlines()
        headings = [line for line in log_lines if line.startswith("## ")]
        assert headings == ["## 2026-07-14", "## 2026-07-13", "## 2026-06-07"]

    def test_write_refreshes_indexes_without_explicit_rebuild(self, tmp_path):
        # Production writers use throwaway bundles and never call
        # rebuild_indexes() — index.md must be maintained by write() itself.
        bundle = OKFBundle(root=tmp_path)
        bundle.write(make_doc(), "decisions", doc_date="2026-07-12")

        decisions_index = (tmp_path / "decisions" / "index.md").read_text(
            encoding="utf-8"
        )
        assert (
            "[Approve nightly consolidation]"
            "(2026-07-12-approve-nightly-consolidation.md)" in decisions_index
        )
        assert (tmp_path / "index.md").exists()

    def test_read_accepts_bundle_absolute_link(self, tmp_path):
        bundle = OKFBundle(root=tmp_path)
        path = bundle.write(make_doc(), "decisions", doc_date="2026-07-12")
        loaded = bundle.read(f"/decisions/{path.name}")
        assert loaded.type == "Decision"

    def test_write_rejects_unknown_subdir(self, tmp_path):
        bundle = OKFBundle(root=tmp_path)
        with pytest.raises(ValueError):
            bundle.write(make_doc(), "not-a-subdir", doc_date="2026-07-12")


# ----------------------------------------------------------------------
# Slug collisions
# ----------------------------------------------------------------------


class TestSlugCollision:
    def test_same_slug_same_date_gets_numeric_suffix(self, tmp_path):
        bundle = OKFBundle(root=tmp_path)
        first = bundle.write(make_doc(), "decisions", doc_date="2026-07-12")
        second = bundle.write(make_doc(), "decisions", doc_date="2026-07-12")
        third = bundle.write(make_doc(), "decisions", doc_date="2026-07-12")

        assert first.name == "2026-07-12-approve-nightly-consolidation.md"
        assert second.name == "2026-07-12-approve-nightly-consolidation-2.md"
        assert third.name == "2026-07-12-approve-nightly-consolidation-3.md"
        # Never overwrites — all three files exist.
        assert first.exists() and second.exists() and third.exists()

    def test_slugify(self):
        assert slugify("Approve Nightly Consolidation!") == (
            "approve-nightly-consolidation"
        )
        assert slugify("  --  ") == "untitled"


# ----------------------------------------------------------------------
# Index rebuilding
# ----------------------------------------------------------------------


class TestRebuildIndexes:
    def test_rebuild_indexes_output_shape(self, tmp_path):
        bundle = OKFBundle(root=tmp_path)
        bundle.write(make_doc(), "decisions", doc_date="2026-07-12")
        bundle.write(
            make_doc(
                type="Learning",
                title="Cache locally",
                description="Local caches beat network calls.",
            ),
            "learnings",
            doc_date="2026-07-10",
        )

        written = bundle.rebuild_indexes()
        # One index per subdir + the root index.
        assert len(written) == len(SUBDIRS) + 1

        decisions_index = (tmp_path / "decisions" / "index.md").read_text(
            encoding="utf-8"
        )
        assert decisions_index.startswith("# Decisions")
        assert (
            "* [Approve nightly consolidation]"
            "(2026-07-12-approve-nightly-consolidation.md)"
            " - The Judge approved the nightly consolidation run." in decisions_index
        )

        learnings_index = (tmp_path / "learnings" / "index.md").read_text(
            encoding="utf-8"
        )
        assert "* [Cache locally](2026-07-10-cache-locally.md)" in learnings_index

        # Empty subdirs still get an index with a placeholder.
        beliefs_index = (tmp_path / "beliefs" / "index.md").read_text(encoding="utf-8")
        assert "*No documents yet.*" in beliefs_index

        # Root index declares the OKF version and links every subdir.
        root_index = (tmp_path / "index.md").read_text(encoding="utf-8")
        assert f'okf_version: "{OKF_VERSION}"' in root_index
        for subdir in SUBDIRS:
            assert f"({subdir}/)" in root_index

    def test_rebuild_indexes_only_dirty(self, tmp_path):
        bundle = OKFBundle(root=tmp_path)
        bundle.write(make_doc(), "decisions", doc_date="2026-07-12")
        written = bundle.rebuild_indexes(only_dirty=True)
        # Only decisions/ was dirty, plus the root index.
        assert [p.parent.name for p in written[:-1]] == ["decisions"]
        # Dirty set is cleared — nothing but the root index next time.
        written_again = bundle.rebuild_indexes(only_dirty=True)
        assert [p for p in written_again if p.parent.name in SUBDIRS] == []

    def test_index_skips_reserved_and_unparseable_files(self, tmp_path):
        bundle = OKFBundle(root=tmp_path)
        bundle.write(make_doc(), "decisions", doc_date="2026-07-12")
        # A stray non-OKF file must not break index generation (SPEC §9).
        (tmp_path / "decisions" / "broken.md").write_text(
            "no frontmatter here", encoding="utf-8"
        )
        bundle.rebuild_indexes()
        decisions_index = (tmp_path / "decisions" / "index.md").read_text(
            encoding="utf-8"
        )
        assert "broken.md" not in decisions_index
        assert "(index.md)" not in decisions_index
