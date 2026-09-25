"""Current state, historical state and the difference between them."""

from __future__ import annotations

from bgs.clock import ManualClock
from bgs.decision.stateview import StateView
from bgs.facts import DIGESTER_LATCHED, VENT_LATCHED


def test_current_state_folds_the_committed_records(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("stir.mix", "stir", 0, {"level": 0.9})
    repo.publish("feed.open", "feed", 0, {"active": True})

    view = StateView(repo)

    assert view.current()["stir"]["mix"]["level"] == 0.9
    assert view.current()["feed"]["open"]["active"] is True


def test_as_of_returns_the_state_of_that_tick(repo_factory):
    clock = ManualClock()
    repo, _, _ = repo_factory(clock=clock)
    repo.publish("feed.open", "feed", 0, {"active": True})
    clock.advance(5)
    repo.publish("feed.close", "feed", 0, {"active": True})

    view = StateView(repo)

    assert "close" not in view.as_of(2)["feed"]
    assert view.as_of(9)["feed"]["close"]["active"] is True


def test_delta_reports_added_keys(repo_factory):
    clock = ManualClock()
    repo, _, _ = repo_factory(clock=clock)
    repo.publish("feed.open", "feed", 0, {"active": True})
    clock.advance(3)
    repo.publish("mem.quality", "mem", 0, {"methane": 97.0})

    delta = StateView(repo).delta(0)

    assert delta.added == ("mem.quality",)
    assert delta.touched == ("mem.quality",)


def test_delta_reports_removed_keys_after_a_tombstone(repo_factory):
    clock = ManualClock()
    repo, _, _ = repo_factory(clock=clock)
    first = repo.publish("mem.quality", "mem", 0, {"methane": 97.0})
    clock.advance(2)
    repo.tombstone(first.seq, reason="bad sample", origin="console", generation=0)

    delta = StateView(repo).delta(0)

    assert delta.removed == ("mem.quality",)


def test_delta_reports_changed_keys(repo_factory):
    clock = ManualClock()
    repo, _, _ = repo_factory(clock=clock)
    repo.publish("mem.quality", "mem", 0, {"methane": 97.0})
    clock.advance(2)
    repo.publish("mem.quality", "mem", 0, {"methane": 91.0})

    delta = StateView(repo).delta(0)

    assert delta.changed == ("mem.quality",)


def test_history_returns_every_record_of_one_kind(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("mem.quality", "mem", 0, {"methane": 97.0})
    repo.publish("mem.quality", "mem", 0, {"methane": 96.5})
    repo.publish("feed.open", "feed", 0, {"active": True})

    view = StateView(repo)

    assert [record.payload["methane"] for record in view.history("mem.quality")] == [97.0, 96.5]
    assert view.latest("feed.open").payload["active"] is True
    assert view.latest("nothing.here") is None


def test_facts_follow_the_latch_history(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("vent.latch", "vent", 0, {"active": True, "step": 1})
    repo.publish("digester.latch", "digester", 0, {"active": True, "step": 1})

    view = StateView(repo)

    assert view.facts()[VENT_LATCHED] is True
    assert view.facts()[DIGESTER_LATCHED] is True

    repo.publish("vent.clear", "vent", 0, {"active": False, "step": 2})

    assert view.facts()[VENT_LATCHED] is False
    assert view.facts()[DIGESTER_LATCHED] is True


def test_fold_reuses_the_stream_reduction(repo_factory):
    repo, _, _ = repo_factory()
    repo.publish("stir.mixer", "stir", 0, {"active": True})
    view = StateView(repo)

    folded = view.fold(view.history("stir.mixer"))

    assert folded["stir"]["mixer"]["active"] is True
