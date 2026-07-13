"""Tests for the LLM consolidation passes in triforce.memory.consolidation.

The LLM adapter ``_llm_summarize`` is faked via monkeypatch — no router, no
network. Journal and knowledge directories are redirected into tmp_path.
"""

import json
from datetime import date, timedelta

import pytest

import triforce.memory.consolidation as consolidation
from triforce.config import Config
from triforce.memory.consolidation import ConsolidationWorker
from triforce.memory.journal import create_entry, save_entry
from triforce.memory.schema import Execution, Judgment

DEFERRED_COMPRESSION = {
    "status": "deferred",
    "reason": "requires DANTE_ROUTER=on with local compression model",
    "weeks_compressed": 0,
    "entries_compressed": 0,
    "high_load_preserved": 0,
}

DEFERRED_JOURNAL_TIER = {
    "status": "deferred",
    "reason": "requires DANTE_ROUTER=on with local summarization model",
    "weeks_summarised": 0,
}

FAKE_LEARNINGS = (
    "- Prefer local models for batch jobs\n"
    "- Persist state after every unit of work\n"
    "- Atomic writes prevent partial files"
)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Redirect journal + knowledge dirs into tmp_path."""
    monkeypatch.setattr(Config, "JOURNAL_DIR", tmp_path / "journal")
    monkeypatch.setattr(Config, "KNOWLEDGE_DIR", tmp_path / "knowledge")
    return tmp_path


def old_monday(weeks_back_extra: int = 0) -> date:
    """Monday of a fully-aged ISO week (well past the 30-day cutoff)."""
    d = date.today() - timedelta(days=60 + 7 * weeks_back_extra)
    return d - timedelta(days=d.isocalendar()[2] - 1)


def write_entry(entry_date: date, load: float = 0.5, action: str = "deploy"):
    entry = create_entry(entry_date.isoformat())
    entry.metadata.cognitive_load_score = load
    entry.judgments.append(
        Judgment(action=action, action_weight=3, reasoning="low risk, high value")
    )
    entry.executions.append(
        Execution(action=action, status="completed", outcome="success")
    )
    save_entry(entry)


def learning_docs(root):
    return [
        p for p in (root / "knowledge" / "learnings").glob("*.md")
        if p.name != "index.md"
    ]


# ----------------------------------------------------------------------
# Deferred shape when the LLM is unavailable
# ----------------------------------------------------------------------


class TestDeferredWhenLLMUnavailable:
    async def test_compress_returns_exact_deferred_dict(self, sandbox, monkeypatch):
        write_entry(old_monday())
        monkeypatch.setattr(consolidation, "_llm_summarize", lambda prompt: None)

        result = await ConsolidationWorker().compress_old_episodes()

        assert result == DEFERRED_COMPRESSION
        # Nothing was written or marked compressed.
        assert not (sandbox / "knowledge" / "learnings").exists()
        assert not (sandbox / "knowledge" / ".consolidation-state.json").exists()

    async def test_journal_tier_returns_exact_deferred_dict(self, sandbox, monkeypatch):
        write_entry(old_monday())
        monkeypatch.setattr(consolidation, "_llm_summarize", lambda prompt: None)

        result = await ConsolidationWorker().consolidate_journal_tier()

        assert result == DEFERRED_JOURNAL_TIER
        assert not list((sandbox / "journal").glob("*-summary.md"))

    async def test_llm_summarize_is_none_without_router(self, monkeypatch):
        # DANTE_ROUTER defaults to "off" — the real adapter must degrade to None.
        monkeypatch.setattr(Config, "DANTE_ROUTER", "off")
        assert consolidation._llm_summarize("anything") is None


# ----------------------------------------------------------------------
# Pass 2 — compress_old_episodes
# ----------------------------------------------------------------------


class TestCompressOldEpisodes:
    async def test_groups_by_iso_week_and_emits_learning_docs(
        self, sandbox, monkeypatch
    ):
        week1, week2 = old_monday(1), old_monday(0)
        write_entry(week1)
        write_entry(week1 + timedelta(days=2))
        write_entry(week2)

        prompts: list[str] = []

        def fake(prompt):
            prompts.append(prompt)
            return FAKE_LEARNINGS

        monkeypatch.setattr(consolidation, "_llm_summarize", fake)

        result = await ConsolidationWorker().compress_old_episodes()

        assert result["status"] == "ok"
        assert result["weeks_compressed"] == 2
        assert result["entries_compressed"] == 3
        assert result["high_load_preserved"] == 0
        # One LLM call per week; both days of week1 are in the same prompt.
        assert len(prompts) == 2
        assert week1.isoformat() in prompts[0]
        assert (week1 + timedelta(days=2)).isoformat() in prompts[0]
        assert week2.isoformat() in prompts[1]

        # 3 learnings per week -> 6 OKF docs, all typed Learning.
        docs = learning_docs(sandbox)
        assert len(docs) == 6
        assert all("type: Learning" in p.read_text(encoding="utf-8") for p in docs)

        # State sidecar tracks both weeks.
        state = json.loads(
            (sandbox / "knowledge" / ".consolidation-state.json").read_text()
        )
        w1 = f"{week1.isocalendar()[0]}-W{week1.isocalendar()[1]:02d}"
        w2 = f"{week2.isocalendar()[0]}-W{week2.isocalendar()[1]:02d}"
        assert state["compressed_weeks"] == sorted([w1, w2])

    async def test_second_run_is_idempotent(self, sandbox, monkeypatch):
        write_entry(old_monday())
        calls = []
        monkeypatch.setattr(
            consolidation,
            "_llm_summarize",
            lambda prompt: calls.append(prompt) or FAKE_LEARNINGS,
        )

        worker = ConsolidationWorker()
        first = await worker.compress_old_episodes()
        second = await worker.compress_old_episodes()

        assert first["weeks_compressed"] == 1
        assert second == {
            "status": "ok",
            "weeks_compressed": 0,
            "entries_compressed": 0,
            "high_load_preserved": 0,
        }
        assert len(calls) == 1  # no second LLM call
        assert len(learning_docs(sandbox)) == 3  # no duplicate docs

    async def test_recent_entries_are_not_compressed(self, sandbox, monkeypatch):
        write_entry(date.today() - timedelta(days=3))
        monkeypatch.setattr(
            consolidation,
            "_llm_summarize",
            lambda prompt: pytest.fail("LLM must not be called"),
        )

        result = await ConsolidationWorker().compress_old_episodes()
        assert result == {
            "status": "ok",
            "weeks_compressed": 0,
            "entries_compressed": 0,
            "high_load_preserved": 0,
        }

    async def test_high_load_days_are_preserved(self, sandbox, monkeypatch):
        monday = old_monday()
        write_entry(monday, load=0.5, action="routine-task")
        write_entry(monday + timedelta(days=1), load=0.9, action="crisis-response")

        prompts: list[str] = []
        monkeypatch.setattr(
            consolidation,
            "_llm_summarize",
            lambda prompt: prompts.append(prompt) or FAKE_LEARNINGS,
        )

        result = await ConsolidationWorker().compress_old_episodes()

        assert result["weeks_compressed"] == 1
        assert result["entries_compressed"] == 1
        assert result["high_load_preserved"] == 1
        # The high-load day never reaches the LLM.
        assert "crisis-response" not in prompts[0]
        assert "routine-task" in prompts[0]

    async def test_learnings_clamped_to_seven(self, sandbox, monkeypatch):
        write_entry(old_monday())
        ten_bullets = "\n".join(f"- Learning number {i}" for i in range(10))
        monkeypatch.setattr(consolidation, "_llm_summarize", lambda prompt: ten_bullets)

        result = await ConsolidationWorker().compress_old_episodes()

        assert result["weeks_compressed"] == 1
        assert len(learning_docs(sandbox)) == 7


# ----------------------------------------------------------------------
# Failure isolation + state safety
# ----------------------------------------------------------------------


class TestFailureIsolation:
    async def test_corrupt_state_skips_compression(self, sandbox, monkeypatch):
        # A corrupt sidecar must abort the pass, not "start fresh" and
        # re-compress every historical week into duplicate docs.
        write_entry(old_monday())
        state_path = sandbox / "knowledge" / ".consolidation-state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(
            consolidation,
            "_llm_summarize",
            lambda prompt: pytest.fail("LLM must not be called"),
        )

        result = await ConsolidationWorker().compress_old_episodes()

        assert result["status"] == "skipped"
        assert result["weeks_compressed"] == 0
        assert not learning_docs(sandbox)
        # The corrupt state was left untouched for inspection.
        assert state_path.read_text(encoding="utf-8") == "{not json"

    async def test_partial_week_retry_does_not_duplicate_docs(
        self, sandbox, monkeypatch
    ):
        from triforce.memory.okf import OKFBundle

        write_entry(old_monday())
        monkeypatch.setattr(
            consolidation, "_llm_summarize", lambda prompt: FAKE_LEARNINGS
        )

        real_write = OKFBundle.write
        calls = {"n": 0}

        def flaky_write(self, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("disk full")
            return real_write(self, *args, **kwargs)

        monkeypatch.setattr(OKFBundle, "write", flaky_write)
        worker = ConsolidationWorker()
        first = await worker.compress_old_episodes()

        # The failed week is NOT marked compressed; one doc landed first.
        assert first["status"] == "ok"
        assert first["weeks_compressed"] == 0
        assert len(learning_docs(sandbox)) == 1

        monkeypatch.setattr(OKFBundle, "write", real_write)
        second = await worker.compress_old_episodes()

        # Retry completes the week and skips the already-written learning.
        assert second["weeks_compressed"] == 1
        docs = learning_docs(sandbox)
        assert len(docs) == 3
        bodies = [p.read_text(encoding="utf-8") for p in docs]
        assert len(set(bodies)) == 3  # no duplicates

    async def test_one_failing_pass_does_not_abort_the_night(
        self, sandbox, monkeypatch
    ):
        write_entry(old_monday())
        monkeypatch.setattr(
            Config, "BELIEFS_PATH", sandbox / "memory" / "judge_beliefs.json"
        )
        monkeypatch.setattr(consolidation, "_llm_summarize", lambda prompt: "Summary.")

        async def boom(self):
            raise RuntimeError("pass exploded")

        monkeypatch.setattr(ConsolidationWorker, "run_fade_decay", boom)

        results = await ConsolidationWorker().run_nightly()

        assert results["fade_decay"] == {"status": "error", "error": "pass exploded"}
        assert results["compression"]["status"] == "ok"
        assert results["ssgm_audit"]["status"] == "ok"
        assert results["journal_tier"]["status"] == "ok"

    async def test_deferred_reports_preserved_high_load_weeks(
        self, sandbox, monkeypatch
    ):
        # An older, all-high-load week is consumed from state without the
        # LLM; when a later week then defers, the preserved count must not
        # be lost from the stats.
        write_entry(old_monday(1), load=0.9, action="crisis-response")
        write_entry(old_monday(0), load=0.5)
        monkeypatch.setattr(consolidation, "_llm_summarize", lambda prompt: None)

        result = await ConsolidationWorker().compress_old_episodes()

        assert result["status"] == "deferred"
        assert result["weeks_compressed"] == 0
        assert result["high_load_preserved"] == 1


# ----------------------------------------------------------------------
# Pass 4 — consolidate_journal_tier
# ----------------------------------------------------------------------


class TestConsolidateJournalTier:
    async def test_writes_summary_for_completed_weeks_only(self, sandbox, monkeypatch):
        monday = old_monday()
        write_entry(monday)
        write_entry(monday + timedelta(days=1))
        write_entry(date.today())  # current week — must not be summarised

        monkeypatch.setattr(
            consolidation, "_llm_summarize", lambda prompt: "A productive week."
        )

        result = await ConsolidationWorker().consolidate_journal_tier()

        assert result == {"status": "ok", "weeks_summarised": 1}
        iso = monday.isocalendar()
        summary = sandbox / "journal" / f"{iso[0]}-W{iso[1]:02d}-summary.md"
        assert summary.exists()
        text = summary.read_text(encoding="utf-8")
        assert text.startswith(f"# Weekly Summary — {iso[0]}-W{iso[1]:02d}")
        assert "A productive week." in text
        # No summary for the current (incomplete) week.
        today_iso = date.today().isocalendar()
        assert not (
            sandbox / "journal" / f"{today_iso[0]}-W{today_iso[1]:02d}-summary.md"
        ).exists()

    async def test_prompt_contains_daily_markdown(self, sandbox, monkeypatch):
        monday = old_monday()
        write_entry(monday, action="ship-feature")

        prompts: list[str] = []
        monkeypatch.setattr(
            consolidation,
            "_llm_summarize",
            lambda prompt: prompts.append(prompt) or "Summary.",
        )

        await ConsolidationWorker().consolidate_journal_tier()
        assert "ship-feature" in prompts[0]
        assert monday.isoformat() in prompts[0]

    async def test_second_run_is_idempotent(self, sandbox, monkeypatch):
        write_entry(old_monday())
        calls = []
        monkeypatch.setattr(
            consolidation,
            "_llm_summarize",
            lambda prompt: calls.append(prompt) or "Summary.",
        )

        worker = ConsolidationWorker()
        first = await worker.consolidate_journal_tier()
        second = await worker.consolidate_journal_tier()

        assert first == {"status": "ok", "weeks_summarised": 1}
        assert second == {"status": "ok", "weeks_summarised": 0}
        assert len(calls) == 1
