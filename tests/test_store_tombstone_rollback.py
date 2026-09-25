"""Rollback is expressed as tombstones, never as deletion."""

from __future__ import annotations

import pytest

from bgs.errors import RecordError, UnknownRecordError
from bgs.store.tombstone import effective_records, hidden_sequences, rollback_targets


def test_tombstone_hides_the_target_record(repo_factory):
    repo, _, _ = repo_factory()
    first = repo.publish("stir.mixer", "stir", 0, {"active": True})
    second = repo.publish("stir.mix", "stir", 0, {"level": 0.9})

    repo.tombstone(first.seq, reason="faulty reading", origin="console", generation=0)

    assert [record.seq for record in repo.visible()] == [second.seq]
    assert "mixer" not in repo.state()["stir"]


def test_tombstone_of_an_unknown_sequence_is_rejected(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("stir.mixer", "stir", 0, {"active": True})

    with pytest.raises(UnknownRecordError):
        repo.tombstone(9, reason="typo", origin="console", generation=0)


def test_tombstone_of_an_uncommitted_record_is_rejected(repo_factory):
    repo, _, _ = repo_factory()
    repo.stage("stir.mixer", "stir", 0, {"active": True})
    repo.flush()

    with pytest.raises(RecordError):
        repo.tombstone(1, reason="too early", origin="console", generation=0)


def test_rollback_after_hides_every_later_record(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("feed.batch", "feed", 1, {"batch_id": "B-1"})
    repo.publish("feed.open", "feed", 1, {"active": True})
    repo.publish("feed.close", "feed", 1, {"active": False})

    tombstones = repo.rollback_after(1, reason="operator rollback", origin="console", generation=0)

    assert [record.tombstone_of for record in tombstones] == [2, 3]
    assert [record.seq for record in repo.visible()] == [1]
    assert "open" not in repo.state()["feed"]


def test_rollback_keeps_the_stream_append_only(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("feed.open", "feed", 0, {"active": True})
    repo.publish("feed.close", "feed", 0, {"active": False})
    before = repo.last_seq()

    repo.rollback_after(1, reason="rollback", origin="console", generation=0)

    assert repo.last_seq() > before
    assert len(repo.all_records()) == repo.last_seq()


def test_rollback_of_an_empty_tail_is_a_noop(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("feed.open", "feed", 0, {"active": True})

    assert repo.rollback_after(5, reason="nothing to do", origin="console", generation=0) == ()


def test_hidden_sequences_reports_every_tombstoned_target(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("feed.open", "feed", 0, {"active": True})
    repo.publish("feed.close", "feed", 0, {"active": False})
    repo.tombstone(1, reason="rollback", origin="console", generation=0)
    repo.tombstone(2, reason="rollback", origin="console", generation=0)

    records = repo.all_records()

    assert hidden_sequences(records) == frozenset({1, 2})
    assert effective_records(records) == ()
    assert rollback_targets(records, 0) == ()
