"""The stream only ever grows, and only committed records are readable."""

from __future__ import annotations

import pytest

from bgs.errors import NotDurableError, RecordError, ValidationError
from bgs.store.records import Record


def test_appended_record_stays_invisible_until_it_is_committed(repo_factory):
    repo, _, _ = repo_factory()

    repo.stage("stir.mixer", "stir", 0, {"active": True})

    assert repo.visible() == ()
    assert repo.watermark().committed_seq == 0


def test_flushed_record_is_durable_but_still_invisible_before_commit(repo_factory):
    repo, _, _ = repo_factory()

    repo.stage("stir.mixer", "stir", 0, {"active": True})
    watermark = repo.flush()

    assert watermark.durable_seq == 1
    assert watermark.committed_seq == 0
    assert repo.visible() == ()
    assert watermark.lag() == 1


def test_commit_beyond_the_durable_watermark_is_rejected_as_not_durable(repo_factory):
    repo, _, _ = repo_factory()

    repo.stage("stir.mixer", "stir", 0, {"active": True})

    with pytest.raises(NotDurableError) as caught:
        repo.commit_through(1)

    assert caught.value.context["durable"] == 0
    assert caught.value.code == "not_durable"


def test_commit_watermark_never_moves_backwards(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("stir.mixer", "stir", 0, {"active": True})
    repo.publish("stir.mix", "stir", 0, {"level": 0.9})

    with pytest.raises(RecordError):
        repo.commit_through(1)


def test_record_kind_must_be_a_group_and_a_leaf(repo_factory):
    repo, _, _ = repo_factory()

    with pytest.raises(ValidationError):
        repo.stage("mixer", "stir", 0, {"active": True})

    with pytest.raises(ValidationError):
        repo.stage("stir.mixer.extra", "stir", 0, {"active": True})


def test_sequence_numbers_continue_after_a_restart(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("stir.mixer", "stir", 0, {"active": True})
    repo.publish("stir.mix", "stir", 0, {"level": 0.9})

    reopened, _, _ = repo_factory()
    record = reopened.publish("stir.persisted", "stir", 1, {"active": True})

    assert record.seq == 3
    assert [entry.seq for entry in reopened.all_records()] == [1, 2, 3]


def test_staged_records_lists_only_unflushed_entries(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("stir.mixer", "stir", 0, {"active": True})
    repo.stage("stir.mix", "stir", 0, {"level": 0.9})
    repo.stage("stir.persisted", "stir", 1, {"active": True})

    assert [record.seq for record in repo.staged_records()] == [2, 3]


def test_record_payload_is_immutable(repo_factory):
    repo, _, _ = repo_factory()
    record = repo.publish("stir.mix", "stir", 0, {"level": 0.9})

    with pytest.raises(TypeError):
        record.payload["level"] = 0.4  # type: ignore[index]


def test_record_rejects_a_tombstone_pointing_at_itself():
    with pytest.raises(ValidationError):
        Record.create(
            seq=3,
            kind="store.tombstone",
            origin="console",
            generation=0,
            tick=0,
            payload={"reason": "self"},
            tombstone_of=3,
        )
