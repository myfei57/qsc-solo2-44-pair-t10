"""Restart recovery of every derived artifact."""

from __future__ import annotations

import pytest

from bgs.errors import ArtifactExpiredError, DuplicateError
from bgs.runtime import LineControlRuntime


def test_restart_recovers_the_line_state(runtime, drive, boot):
    drive()

    reopened = boot()
    state = reopened.state()

    assert state["lines"]["upgrade"]["phase"] == "pressure_ramp"
    assert state["lines"]["gas"]["phase"] == "open"
    assert state["subsystems"]["mem"]["pressure_kpa"] == 1500.0
    assert state["subsystems"]["gas"]["inlet_open"] is True


def test_restart_keeps_the_quality_latch_set(runtime, drive, boot):
    drive()
    runtime.dispatch("mem.analyze", {"methane": 90.0})

    reopened = boot()

    assert reopened.health()["latched"]["vent"] is True
    assert reopened.state()["lines"]["vent"]["phase"] == "quality_alarm"


def test_restart_rebuilds_generations_baselines_and_confirmations(runtime, drive, boot):
    drive()

    reopened = boot()

    assert reopened.versions.current_generation("stir") == 1
    assert reopened.versions.current_generation("desul") == 1
    assert reopened.versions.current_generation("feed") == 1
    assert reopened.versions.baseline_value("membrane_pressure") == 1500.0
    assert reopened.versions.confirmation_state("desul", now=reopened.clock.now()) is not None


def test_restart_keeps_an_expired_confirmation_expired(runtime, boot):
    runtime.dispatch("desul.check", {"sulfur_ppm": 6.0})
    runtime.advance_ticks(20)

    reopened = boot()

    assert reopened.clock.now() == 20
    with pytest.raises(ArtifactExpiredError):
        reopened.dispatch("compress.start", {})


def test_restart_keeps_batch_uniqueness(runtime, boot):
    runtime.dispatch("stir.start", {})
    runtime.dispatch("stir.homogenize", {"level": 0.9})
    runtime.dispatch("stir.persist", {})
    runtime.dispatch("feed.batch", {"batch_id": "B-5", "quantity": 5.0})

    reopened = boot()

    with pytest.raises(DuplicateError):
        reopened.dispatch("feed.batch", {"batch_id": "B-5", "quantity": 5.0})


def test_restart_uses_a_snapshot_when_one_was_taken(runtime, drive, boot):
    drive()
    runtime.dispatch("snapshot.take", {})

    reopened = boot()

    assert reopened.boot_report.used_snapshot_id is not None
    assert reopened.state()["lines"]["gas"]["phase"] == "open"


def test_restart_continues_the_tick_from_the_stream(runtime, drive, boot):
    drive()
    runtime.advance_ticks(7)

    reopened = boot()

    assert reopened.clock.now() == 7


def test_rollback_hides_records_from_the_derived_state(runtime, drive):
    drive()
    inlet = runtime.view.latest("gas.inlet")

    runtime.rollback(inlet.seq - 1, reason="unverified storage")

    assert "inlet" not in runtime.view.current().get("gas", {})
    assert runtime.view.latest("gas.inlet") is None


def test_rollback_is_visible_after_a_restart(runtime, drive, boot):
    drive()
    inlet = runtime.view.latest("gas.inlet")
    runtime.rollback(inlet.seq - 1, reason="unverified storage")

    reopened = boot()

    assert "inlet" not in reopened.view.current().get("gas", {})


def test_health_is_identical_for_the_same_command_sequence(config, tmp_path):
    first = LineControlRuntime(config)
    second = LineControlRuntime(config.with_overrides(data_dir=tmp_path / "mirror"))
    try:
        for line in (first, second):
            line.bootstrap()
            line.dispatch("stir.start", {})
            line.dispatch("stir.homogenize", {"level": 0.9})
            line.dispatch("stir.persist", {})
            line.dispatch("feed.batch", {"batch_id": "B-1", "quantity": 5.0})
            line.dispatch("feed.start", {})
            line.dispatch("desul.check", {"sulfur_ppm": 6.0})

        assert first.health() == second.health()
        assert first.state()["subsystems"]["feed"] == second.state()["subsystems"]["feed"]
    finally:
        first.close()
        second.close()


def test_stream_records_are_identical_for_the_same_command_sequence(config, tmp_path):
    paths = []
    for name in ("a", "b"):
        line = LineControlRuntime(config.with_overrides(data_dir=tmp_path / name))
        try:
            line.bootstrap()
            line.dispatch("stir.start", {})
            line.dispatch("stir.homogenize", {"level": 0.9})
            line.dispatch("stir.persist", {})
        finally:
            line.close()
        paths.append((tmp_path / name / "journal.jsonl").read_text(encoding="utf-8"))

    assert paths[0] == paths[1]
