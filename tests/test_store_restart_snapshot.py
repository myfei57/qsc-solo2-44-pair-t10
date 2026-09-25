"""Restart recovery, snapshot selection and snapshot expiry."""

from __future__ import annotations

from bgs.store.snapshot import Snapshot, SnapshotStore
from bgs.versioning.expiry import Validity


def test_restart_replays_the_tail_when_no_snapshot_exists(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("feed.open", "feed", 0, {"active": True})
    repo.publish("feed.close", "feed", 0, {"active": True})

    reopened, _, _ = repo_factory()
    report = reopened.restore(now=0)

    assert report.used_snapshot_id is None
    assert report.replayed_records == 2
    assert report.state["feed"]["close"]["active"] is True


def test_restart_uses_the_newest_valid_snapshot(repo_factory):
    repo, clock, _ = repo_factory()
    repo.publish("feed.open", "feed", 0, {"active": True})
    snapshot = repo.snapshot(generation=1, validity=Validity.of(clock.now(), 30))
    repo.publish("feed.close", "feed", 0, {"active": True})

    reopened, _, _ = repo_factory()
    report = reopened.restore(now=clock.now())

    assert report.used_snapshot_id == snapshot.snapshot_id
    assert report.replayed_records == 1
    assert report.state["feed"]["close"]["active"] is True


def test_expired_snapshot_is_rejected(repo_factory):
    repo, clock, _ = repo_factory()
    repo.publish("feed.open", "feed", 0, {"active": True})
    snapshot = repo.snapshot(generation=1, validity=Validity.of(clock.now(), 3))
    clock.advance(5)

    reopened, _, _ = repo_factory()
    report = reopened.restore(now=clock.now())

    assert report.used_snapshot_id is None
    assert report.rejected_snapshots[0]["snapshot_id"] == snapshot.snapshot_id
    assert report.rejected_snapshots[0]["reject"] == "expired"
    assert report.state["feed"]["open"]["active"] is True


def test_restart_refuses_to_fall_back_to_an_older_snapshot(repo_factory):
    repo, clock, _ = repo_factory()
    repo.publish("feed.open", "feed", 0, {"active": True})
    repo.snapshot(generation=1, validity=Validity.of(clock.now(), 60))
    repo.publish("feed.close", "feed", 0, {"active": True})
    newest = repo.snapshot(generation=2, validity=Validity.of(clock.now(), 2))
    clock.advance(9)

    reopened, _, _ = repo_factory()
    report = reopened.restore(now=clock.now())

    assert report.used_snapshot_id is None
    rejects = {item["snapshot_id"]: item["reject"] for item in report.rejected_snapshots}
    assert rejects[newest.snapshot_id] == "expired"
    assert set(rejects.values()) == {"expired", "superseded_by_expired_newer"}


def test_snapshot_beyond_the_commit_watermark_is_rejected(repo_factory):
    repo, clock, _ = repo_factory()
    repo.publish("feed.open", "feed", 0, {"active": True})
    store = SnapshotStore(repo.snapshots.directory)
    forged = Snapshot(
        snapshot_id="snap-000099",
        watermark_seq=99,
        generation=1,
        tick=clock.now(),
        state={"feed": {"open": {"active": True}}},
        validity=Validity.of(clock.now(), 30),
    )
    store.save(forged)

    report = repo.restore(now=clock.now())

    assert report.used_snapshot_id is None
    assert report.rejected_snapshots[0]["reject"] == "beyond_watermark"
    assert report.replayed_records == 1


def test_restore_reports_superseded_snapshots(repo_factory):
    repo, clock, _ = repo_factory()
    repo.publish("feed.open", "feed", 0, {"active": True})
    older = repo.snapshot(generation=1, validity=Validity.of(clock.now(), 30))
    repo.publish("feed.close", "feed", 0, {"active": True})
    newer = repo.snapshot(generation=2, validity=Validity.of(clock.now(), 30))

    report = repo.restore(now=clock.now())

    assert report.used_snapshot_id == newer.snapshot_id
    assert [item["snapshot_id"] for item in report.rejected_snapshots] == [older.snapshot_id]
    assert report.rejected_snapshots[0]["reject"] == "superseded"


def test_snapshot_round_trips_through_the_file(repo_factory):
    repo, clock, _ = repo_factory()
    repo.publish("stir.mix", "stir", 2, {"level": 0.88})

    snapshot = repo.snapshot(generation=3, validity=Validity.of(clock.now(), 10))
    loaded = repo.snapshots.load_all()

    assert [item.snapshot_id for item in loaded] == [snapshot.snapshot_id]
    assert loaded[0].state["stir"]["mix"]["level"] == 0.88
    assert loaded[0].generation == 3


def test_sequence_continues_after_restoring_from_a_snapshot(repo_factory):
    repo, clock, _ = repo_factory()
    repo.publish("feed.open", "feed", 0, {"active": True})
    repo.snapshot(generation=1, validity=Validity.of(clock.now(), 30))

    reopened, _, _ = repo_factory()
    reopened.restore(now=clock.now())
    record = reopened.publish("feed.close", "feed", 0, {"active": True})

    assert record.seq == 2


def test_restore_keeps_the_commit_watermark_of_the_original_run(repo_factory):
    repo, clock, _ = repo_factory()
    repo.publish("feed.open", "feed", 0, {"active": True})
    repo.stage("feed.close", "feed", 0, {"active": True})
    repo.flush()

    reopened, _, _ = repo_factory()
    report = reopened.restore(now=clock.now())

    assert report.watermark.committed_seq == 1
    assert report.watermark.durable_seq == 2
    assert "close" not in report.state["feed"]
