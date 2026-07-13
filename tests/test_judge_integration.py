"""Tests for Judge/journal OKF integration and the reflection trigger.

Covers: belief supersede chains (append-only, never deleted), OKF Decision
doc emission from journal Judgment appends (without altering journal output),
importance accumulation (Execution defaults to weight 1), the
check_reflection_due()/reset_accumulator() threshold behavior, and the
write_reflection tool.
"""

import json
from pathlib import Path

import pytest

from triforce.config import Config
from triforce.memory import beliefs, journal
from triforce.memory.journal import (
    append_to_section,
    create_entry,
    entry_to_markdown,
)
from triforce.memory.okf import OKFBundle
from triforce.memory.schema import Execution, Judgment
from triforce.temporal.workflows import (
    check_reflection_due_activity,
    reset_accumulator_activity,
)
from triforce.tools.knowledge_tools import write_reflection

OLD_BELIEF = "Local caches beat network calls"
NEW_BELIEF = "Local caches beat network calls except for hot data"

JUDGMENT_PAYLOAD = {
    "timestamp": "2026-07-12T10:00:00",
    "action": "Deploy nightly build",
    "action_weight": 7,
    "verdict": "approved",
    "reasoning": "Low risk change with rollback available.",
}

EXECUTION_PAYLOAD = {
    "timestamp": "2026-07-12T10:05:00",
    "action": "Deploy nightly build",
    "status": "completed",
    "outcome": "Build deployed.",
}


@pytest.fixture(autouse=True)
def isolated_stores(tmp_path, monkeypatch):
    """Point every persistent store at a temp directory."""
    monkeypatch.setattr(Config, "JOURNAL_DIR", tmp_path / "journal")
    monkeypatch.setattr(Config, "KNOWLEDGE_DIR", tmp_path / "knowledge")
    monkeypatch.setattr(
        Config, "BELIEFS_PATH", tmp_path / "memory" / "judge_beliefs.json"
    )
    monkeypatch.setattr(Config, "REFLECTION_IMPORTANCE_THRESHOLD", 15)
    return tmp_path


# ----------------------------------------------------------------------
# Belief supersede chain
# ----------------------------------------------------------------------


class TestSupersedeChain:
    def test_add_belief_emits_okf_doc(self):
        beliefs.add_belief(OLD_BELIEF, strength=0.6, reason="observed")
        docs = OKFBundle().documents("beliefs")
        assert len(docs) == 1
        _, doc = docs[0]
        assert doc.type == "Belief"
        assert doc.title == OLD_BELIEF
        assert doc.extras["invalidated_at"] is None
        assert doc.extras["supersedes"] is None

    def test_supersede_updates_json_and_writes_chain(self):
        beliefs.add_belief(OLD_BELIEF, strength=0.6)
        bundle = OKFBundle()
        old_path = bundle.documents("beliefs")[0][0]

        result = beliefs.supersede_belief(
            OLD_BELIEF,
            NEW_BELIEF,
            reason="Observed stale-cache incidents",
            ssgm_score=0.42,
        )

        # JSON runtime store: updated in place, schema unchanged.
        stored = beliefs.load_beliefs()
        assert len(stored) == 1
        assert stored[0]["belief"] == NEW_BELIEF
        assert stored[0]["reason"] == "Observed stale-cache incidents"
        assert set(stored[0]) == {"belief", "strength", "reason", "created", "updated"}

        # OKF: two documents — the old one was invalidated, never deleted.
        docs = bundle.documents("beliefs")
        assert len(docs) == 2
        assert old_path.exists()

        old_doc = bundle.read(old_path)
        assert old_doc.extras["invalidated_at"] is not None

        new_path = result["okf_new_path"]
        assert result["okf_old_path"] == old_path
        new_doc = bundle.read(new_path)
        assert new_doc.title == NEW_BELIEF
        assert new_doc.extras["invalidated_at"] is None
        assert new_doc.extras["supersedes"] == f"/beliefs/{old_path.name}"
        assert new_doc.extras["ssgm_score"] == 0.42
        assert new_doc.extras["valid_at"] == old_doc.extras["invalidated_at"]

    def test_supersede_chain_survives_second_hop(self):
        beliefs.add_belief(OLD_BELIEF)
        beliefs.supersede_belief(OLD_BELIEF, NEW_BELIEF, reason="first")
        beliefs.supersede_belief(NEW_BELIEF, "Third generation belief", reason="second")

        bundle = OKFBundle()
        docs = bundle.documents("beliefs")
        assert len(docs) == 3
        current = [
            doc for _, doc in docs if not doc.extras.get("invalidated_at")
        ]
        assert [d.title for d in current] == ["Third generation belief"]
        assert beliefs.load_beliefs()[0]["belief"] == "Third generation belief"

    def test_supersede_missing_old_belief_adds_new(self):
        result = beliefs.supersede_belief("never existed", NEW_BELIEF, reason="new")
        stored = beliefs.load_beliefs()
        assert len(stored) == 1
        assert stored[0]["belief"] == NEW_BELIEF
        assert result["okf_old_path"] is None
        new_doc = OKFBundle().read(result["okf_new_path"])
        assert new_doc.extras["supersedes"] is None

    def test_okf_failure_does_not_break_json_store(self, monkeypatch):
        import triforce.memory.okf as okf

        def boom(self, *args, **kwargs):
            raise RuntimeError("okf down")

        monkeypatch.setattr(okf.OKFBundle, "write", boom)
        result = beliefs.supersede_belief(OLD_BELIEF, NEW_BELIEF, reason="r")
        assert beliefs.load_beliefs()[0]["belief"] == NEW_BELIEF
        assert result["okf_new_path"] is None
        assert result["okf_old_invalidated"] is False

    def test_partial_supersede_is_reported_not_hidden(self, monkeypatch):
        # New doc written, but invalidating the old doc fails (e.g. the file
        # is locked on Windows): the result must reflect the real state.
        import triforce.memory.okf as okf

        beliefs.add_belief(OLD_BELIEF, strength=0.6)
        old_path = OKFBundle().documents("beliefs")[0][0]
        real_write = okf._atomic_write

        def flaky(path, content):
            if path == old_path:
                raise PermissionError("file locked")
            real_write(path, content)

        monkeypatch.setattr(okf, "_atomic_write", flaky)
        result = beliefs.supersede_belief(OLD_BELIEF, NEW_BELIEF, reason="r")

        assert beliefs.load_beliefs()[0]["belief"] == NEW_BELIEF
        assert result["okf_new_path"] is not None  # the new doc IS on disk
        assert result["okf_old_path"] == old_path
        assert result["okf_old_invalidated"] is False
        assert OKFBundle().read(old_path).extras["invalidated_at"] is None

    def test_supersede_repairs_stale_current_docs(self, monkeypatch):
        # A straggler doc left "current" by an earlier partial failure is
        # invalidated by the next supersede of the same belief text.
        beliefs.add_belief(OLD_BELIEF, strength=0.6)
        beliefs._write_belief_doc(
            OLD_BELIEF, reason="duplicate from a crashed run",
            valid_at="2026-07-01T00:00:00", supersedes=None,
            ssgm_score=None, action="Creation",
        )

        result = beliefs.supersede_belief(OLD_BELIEF, NEW_BELIEF, reason="r")

        assert result["okf_old_invalidated"] is True
        bundle = OKFBundle()
        current = [
            doc for _, doc in bundle.documents("beliefs")
            if not doc.extras.get("invalidated_at")
        ]
        assert [d.title for d in current] == [NEW_BELIEF]

    def test_supersede_beliefs_tool_records_chain(self):
        from triforce.tools.memory_tools import supersede_beliefs

        beliefs.add_belief(OLD_BELIEF, strength=0.6)
        result = supersede_beliefs(
            OLD_BELIEF, NEW_BELIEF, reason="revised", strength=0.8,
            tool_context=None,
        )

        assert result["status"] == "superseded"
        assert result["belief"] == NEW_BELIEF
        assert result["okf_old_invalidated"] is True
        current = [
            doc for _, doc in OKFBundle().documents("beliefs")
            if not doc.extras.get("invalidated_at")
        ]
        assert [d.title for d in current] == [NEW_BELIEF]


# ----------------------------------------------------------------------
# Decision doc emission from journal appends
# ----------------------------------------------------------------------


class TestDecisionEmission:
    def test_journal_output_byte_compatible(self):
        expected = create_entry("2026-07-12")
        expected.judgments.append(Judgment(**JUDGMENT_PAYLOAD))
        expected_md = entry_to_markdown(expected)
        expected_json = expected.model_dump_json(indent=2)

        append_to_section(
            "judgments", dict(JUDGMENT_PAYLOAD), entry_date="2026-07-12"
        )

        assert (
            (Config.JOURNAL_DIR / "2026-07-12.md").read_text(encoding="utf-8")
            == expected_md
        )
        assert (
            (Config.JOURNAL_DIR / "2026-07-12.json").read_text(encoding="utf-8")
            == expected_json
        )

    def test_decision_doc_emitted_with_metadata(self):
        append_to_section(
            "judgments", dict(JUDGMENT_PAYLOAD), entry_date="2026-07-12"
        )
        docs = OKFBundle().documents("decisions")
        assert len(docs) == 1
        _, doc = docs[0]
        assert doc.type == "Decision"
        assert doc.title == "Deploy nightly build"
        assert doc.extras["verdict"] == "approved"
        assert doc.extras["action_weight"] == 7
        assert doc.timestamp == JUDGMENT_PAYLOAD["timestamp"]
        assert "Low risk change with rollback available." in doc.body

    def test_decision_doc_links_related_beliefs(self):
        beliefs.add_belief(OLD_BELIEF)
        belief_path = OKFBundle().documents("beliefs")[0][0]

        payload = dict(JUDGMENT_PAYLOAD)
        payload["reasoning"] = (
            f"Approved because {OLD_BELIEF.lower()} in this scenario."
        )
        append_to_section("judgments", payload, entry_date="2026-07-12")

        _, doc = OKFBundle().documents("decisions")[0]
        assert doc.bundle_links() == [f"/beliefs/{belief_path.name}"]

    def test_invalidated_beliefs_not_linked(self):
        beliefs.add_belief(OLD_BELIEF)
        beliefs.supersede_belief(OLD_BELIEF, NEW_BELIEF)

        payload = dict(JUDGMENT_PAYLOAD)
        payload["reasoning"] = f"Because {OLD_BELIEF}."
        append_to_section("judgments", payload, entry_date="2026-07-12")

        _, doc = OKFBundle().documents("decisions")[0]
        # OLD_BELIEF doc is invalidated; NEW_BELIEF contains OLD_BELIEF as a
        # prefix and is current — only the current doc may be linked, and
        # here the reasoning does not contain the full new belief text.
        for link in doc.bundle_links():
            linked = OKFBundle().read(link)
            assert not linked.extras.get("invalidated_at")

    def test_okf_failure_does_not_break_journal_write(self, monkeypatch):
        import triforce.memory.okf as okf

        def boom(self, *args, **kwargs):
            raise RuntimeError("okf down")

        monkeypatch.setattr(okf.OKFBundle, "write", boom)
        path = append_to_section(
            "judgments", dict(JUDGMENT_PAYLOAD), entry_date="2026-07-12"
        )
        assert path.exists()
        entry = journal.load_entry("2026-07-12")
        assert len(entry.judgments) == 1
        # The accumulator hook still ran.
        assert journal.accumulated_importance() == 7

    def test_journal_files_round_trip_utf8(self):
        # Em dashes/accents/symbols must survive the write→read cycle even
        # on Windows (the platform default codec is cp1252 there).
        payload = dict(JUDGMENT_PAYLOAD, reasoning="café rollback — verified ✓")
        append_to_section("judgments", payload, entry_date="2026-07-12")

        md = (Config.JOURNAL_DIR / "2026-07-12.md").read_text(encoding="utf-8")
        assert "café rollback — verified ✓" in md
        entry = journal.load_entry("2026-07-12")
        assert entry.judgments[0].reasoning == "café rollback — verified ✓"

    def test_execution_append_emits_no_decision_doc(self):
        append_to_section(
            "executions", dict(EXECUTION_PAYLOAD), entry_date="2026-07-12"
        )
        assert OKFBundle().documents("decisions") == []


# ----------------------------------------------------------------------
# Importance accumulator + reflection trigger
# ----------------------------------------------------------------------


class TestImportanceAccumulator:
    def test_judgment_weights_accumulate(self):
        append_to_section(
            "judgments", dict(JUDGMENT_PAYLOAD), entry_date="2026-07-12"
        )
        assert journal.accumulated_importance() == 7
        payload = dict(JUDGMENT_PAYLOAD, action_weight=3)
        append_to_section("judgments", payload, entry_date="2026-07-12")
        assert journal.accumulated_importance() == 10

    def test_execution_counts_as_weight_one(self):
        # Execution has no weight field — verified against the schema.
        assert not hasattr(Execution(), "action_weight")
        append_to_section(
            "executions", dict(EXECUTION_PAYLOAD), entry_date="2026-07-12"
        )
        append_to_section(
            "executions", dict(EXECUTION_PAYLOAD), entry_date="2026-07-12"
        )
        assert journal.accumulated_importance() == 2

    def test_other_sections_do_not_accumulate(self):
        append_to_section(
            "learnings", {"content": "something"}, entry_date="2026-07-12"
        )
        assert journal.accumulated_importance() == 0

    def test_accumulator_persists_across_calls(self):
        journal.add_importance(4)
        state = json.loads(
            (Config.JOURNAL_DIR / ".importance-accumulator.json").read_text()
        )
        assert state["accumulated"] == 4
        assert journal.add_importance(2) == 6

    def test_threshold_and_reset(self, monkeypatch):
        monkeypatch.setattr(Config, "REFLECTION_IMPORTANCE_THRESHOLD", 5)
        assert not journal.check_reflection_due()
        journal.add_importance(4)
        assert not journal.check_reflection_due()
        journal.add_importance(1)
        assert journal.check_reflection_due()
        journal.reset_accumulator()
        assert journal.accumulated_importance() == 0
        assert not journal.check_reflection_due()

    def test_workflow_activity_wrappers(self, monkeypatch):
        monkeypatch.setattr(Config, "REFLECTION_IMPORTANCE_THRESHOLD", 3)
        journal.add_importance(5)
        assert check_reflection_due_activity() == {
            "reflection_due": True,
            "accumulated": 5,
        }
        assert reset_accumulator_activity() == {"status": "reset"}
        assert check_reflection_due_activity() == {
            "reflection_due": False,
            "accumulated": 0,
        }

    def test_reset_with_consumed_preserves_importance_accrued_meanwhile(self):
        # The workflow observes 16, consolidation runs for minutes, 12 more
        # accrue — resetting must only consume the observed 16.
        journal.add_importance(16)
        journal.add_importance(12)
        journal.reset_accumulator(consumed=16)
        assert journal.accumulated_importance() == 12
        # A plain reset still zeroes, and never goes negative.
        journal.reset_accumulator(consumed=99)
        assert journal.accumulated_importance() == 0

    def test_reset_activity_passes_consumed_through(self):
        journal.add_importance(10)
        assert reset_accumulator_activity(consumed=4) == {"status": "reset"}
        assert journal.accumulated_importance() == 6

    def test_reflection_tools_registered_for_dynamic_dispatch(self):
        from triforce.temporal.activities import get_handler
        from triforce.temporal.workflows import run_consolidation_activity

        assert get_handler("check_reflection_due") is check_reflection_due_activity
        assert get_handler("reset_accumulator") is reset_accumulator_activity
        # The nightly workflow invokes "run_consolidation" by name — it must
        # be registered or the dynamic dispatcher raises forever.
        assert get_handler("run_consolidation") is run_consolidation_activity


# ----------------------------------------------------------------------
# write_reflection tool
# ----------------------------------------------------------------------


class TestWriteReflection:
    def test_persists_reflection_linking_decisions(self):
        result = write_reflection(
            "The deploy went well and validated our rollback belief.",
            title="Deploy retro",
            decision_refs=[
                "2026-07-12-deploy-nightly-build.md",
                "/decisions/2026-07-11-other.md",
            ],
        )
        assert result["status"] == "written"
        doc = OKFBundle().read(Path(result["path"]))
        assert doc.type == "Reflection"
        assert doc.title == "Deploy retro"
        assert doc.bundle_links() == [
            "/decisions/2026-07-12-deploy-nightly-build.md",
            "/decisions/2026-07-11-other.md",
        ]

    def test_failure_returns_error_dict(self, monkeypatch):
        import triforce.memory.okf as okf

        def boom(self, *args, **kwargs):
            raise RuntimeError("okf down")

        monkeypatch.setattr(okf.OKFBundle, "write", boom)
        result = write_reflection("anything")
        assert result["status"] == "error"
