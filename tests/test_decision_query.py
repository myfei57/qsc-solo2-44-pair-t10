"""Audit filtering over the committed stream."""

from __future__ import annotations

import pytest

from bgs.clock import ManualClock
from bgs.decision.query import RecordQuery, run_query
from bgs.errors import ValidationError


def test_query_matches_by_kind(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("mem.quality", "mem", 0, {"methane": 97.0})
    repo.publish("feed.open", "feed", 0, {"active": True})

    result = run_query(repo.visible(), RecordQuery(kinds=("mem.quality",)))

    assert result.total == 1
    assert result.records[0].kind == "mem.quality"


def test_query_matches_by_origin(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("mem.quality", "mem", 0, {"methane": 97.0})
    repo.publish("mem.quality", "vent", 0, {"methane": 96.0})

    result = run_query(repo.visible(), RecordQuery(origins=("vent",)))

    assert [record.origin for record in result.records] == ["vent"]


def test_query_honours_the_limit_from_the_end(repo_factory):
    repo, _, _ = repo_factory()
    for value in (97.0, 96.5, 96.2):
        repo.publish("mem.quality", "mem", 0, {"methane": value})

    result = run_query(repo.visible(), RecordQuery(limit=2))

    assert [record.payload["methane"] for record in result.records] == [96.5, 96.2]


def test_query_hides_tombstones_by_default(repo_factory):
    repo, _, _ = repo_factory()
    first = repo.publish("mem.quality", "mem", 0, {"methane": 97.0})
    repo.publish("mem.quality", "mem", 0, {"methane": 96.0})
    repo.tombstone(first.seq, reason="bad sample", origin="console", generation=0)

    hidden = run_query(repo.committed_records(), RecordQuery())
    shown = run_query(repo.committed_records(), RecordQuery(include_tombstones=True))

    assert hidden.total == 2
    assert shown.total == 3


def test_query_matches_a_sequence_range(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("mem.quality", "mem", 0, {"methane": 97.0})
    repo.publish("mem.quality", "mem", 0, {"methane": 96.5})
    repo.publish("mem.quality", "mem", 0, {"methane": 96.2})

    result = run_query(repo.visible(), RecordQuery(seq_from=2, seq_to=3))

    assert [record.seq for record in result.records] == [2, 3]


def test_query_matches_a_tick_range(repo_factory):
    clock = ManualClock()
    repo, _, _ = repo_factory(clock=clock)
    repo.publish("mem.quality", "mem", 0, {"methane": 97.0})
    clock.advance(4)
    repo.publish("mem.quality", "mem", 0, {"methane": 96.5})

    result = run_query(repo.visible(), RecordQuery(tick_from=3))

    assert [record.payload["methane"] for record in result.records] == [96.5]


def test_query_rejects_an_inverted_range():
    with pytest.raises(ValidationError):
        RecordQuery(seq_from=5, seq_to=1)

    with pytest.raises(ValidationError):
        RecordQuery(tick_from=5, tick_to=1)


def test_query_rejects_a_non_positive_limit():
    with pytest.raises(ValidationError):
        RecordQuery(limit=0)


def test_query_summarises_by_kind_and_origin(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("mem.quality", "mem", 0, {"methane": 97.0})
    repo.publish("mem.quality", "mem", 0, {"methane": 96.5})
    repo.publish("feed.open", "feed", 0, {"active": True})

    described = run_query(repo.visible(), RecordQuery()).describe()

    assert described["total"] == 3
    assert described["by_kind"] == {"mem.quality": 2, "feed.open": 1}
    assert described["by_origin"] == {"mem": 2, "feed": 1}
    assert described["query"]["limit"] is None
