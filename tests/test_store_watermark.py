"""Commit watermark behaviour across the read and write paths."""

from __future__ import annotations

from bgs.clock import ManualClock
from bgs.ids import SequenceIds
from bgs.store.repository import RecordRepository


def test_watermark_uses_the_issue_tick(repo_factory):
    clock = ManualClock(start=4)
    repo, _, _ = repo_factory(clock=clock)

    repo.publish("stir.mixer", "stir", 0, {"active": True})

    assert repo.watermark().tick == 4


def test_state_ignores_records_past_the_commit_watermark(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("stir.mixer", "stir", 0, {"active": True})
    repo.stage("stir.mix", "stir", 0, {"level": 0.9})
    repo.flush()

    assert "mix" not in repo.state()["stir"]

    repo.commit()

    assert repo.state()["stir"]["mix"]["level"] == 0.9


def test_commit_through_zero_is_harmless(repo_factory):
    repo, _, _ = repo_factory()

    watermark = repo.commit_through(0)

    assert watermark.committed_seq == 0


def test_publish_commits_in_one_step(repo_factory):
    repo, _, _ = repo_factory()

    repo.publish("feed.open", "feed", 0, {"active": True})

    assert repo.watermark().committed_seq == 1
    assert repo.watermark().lag() == 0


def test_watermark_and_records_survive_a_restart(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("feed.open", "feed", 0, {"active": True})
    repo.publish("feed.close", "feed", 0, {"active": False})

    reopened, _, _ = repo_factory()

    assert reopened.watermark().committed_seq == 2
    assert reopened.state()["feed"]["open"]["active"] is True
    assert reopened.state()["feed"]["close"]["active"] is False


def test_uncommitted_records_survive_a_restart_without_becoming_visible(repo_factory):
    repo, _, _ = repo_factory()
    repo.stage("feed.open", "feed", 0, {"active": True})
    repo.flush()

    reopened, _, _ = repo_factory()

    assert reopened.last_seq() == 1
    assert reopened.watermark().committed_seq == 0
    assert reopened.visible() == ()

    reopened.commit()

    assert reopened.state()["feed"]["open"]["active"] is True


def test_in_memory_repository_keeps_the_same_visibility_rules():
    repo = RecordRepository.in_memory(ManualClock(), SequenceIds())
    repo.stage("feed.open", "feed", 0, {"active": True})

    assert repo.visible() == ()
