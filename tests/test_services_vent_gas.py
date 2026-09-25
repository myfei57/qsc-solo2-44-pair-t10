"""Quality latch, flare line and storage inlet."""

from __future__ import annotations

import pytest

from bgs.errors import InterlockBlockedError, OrderViolationError, OverLimitError


def test_low_methane_sets_the_quality_latch(runtime, drive):
    drive()

    runtime.dispatch("mem.analyze", {"methane": 90.0})

    assert runtime.health()["latched"]["vent"] is True
    assert runtime.state()["lines"]["vent"]["phase"] == "quality_alarm"
    assert runtime.alarms.count() == 1


def test_flare_opens_the_line_after_the_latch(runtime, drive):
    drive()
    runtime.dispatch("mem.analyze", {"methane": 90.0})

    runtime.dispatch("vent.flare", {"reason": "methane low"})

    state = runtime.state()
    assert state["lines"]["vent"]["phase"] == "flaring"
    assert state["subsystems"]["vent"]["flaring"] is True


def test_flare_before_the_latch_is_rejected_as_out_of_order(runtime, drive):
    drive()

    with pytest.raises(OrderViolationError) as caught:
        runtime.dispatch("vent.flare", {"reason": "no alarm"})

    assert caught.value.context["required_phase"] == "quality_alarm"


def test_recovery_before_flaring_is_rejected_as_out_of_order(runtime, drive):
    drive()
    runtime.dispatch("mem.analyze", {"methane": 90.0})

    with pytest.raises(OrderViolationError):
        runtime.dispatch("vent.recover", {})


def test_latch_clears_only_after_the_quality_window_recovers(runtime, drive):
    drive()
    runtime.dispatch("mem.analyze", {"methane": 90.0})
    runtime.dispatch("vent.flare", {"reason": "methane low"})

    with pytest.raises(InterlockBlockedError) as caught:
        runtime.dispatch("vent.recover", {})

    assert caught.value.context["ready"] is False

    for _ in range(8):
        runtime.advance_ticks(1)
        runtime.dispatch("mem.analyze", {"methane": 97.0})

    runtime.dispatch("vent.recover", {})

    assert runtime.health()["latched"]["vent"] is False
    assert runtime.state()["lines"]["vent"]["phase"] == "recovered"


def test_gas_inlet_is_blocked_while_the_quality_latch_is_set(runtime, drive):
    drive(inlet=False)
    runtime.dispatch("mem.analyze", {"methane": 90.0})

    with pytest.raises(InterlockBlockedError) as caught:
        runtime.dispatch("gas.inlet_open", {})

    assert "vent.latched" in caught.value.context["missing"]


def test_gas_inlet_is_blocked_while_the_vessel_latch_is_set(runtime, drive):
    drive(inlet=False)
    with pytest.raises(OverLimitError):
        runtime.dispatch("digester.pressure", {"kpa": 30.0})

    with pytest.raises(InterlockBlockedError) as caught:
        runtime.dispatch("gas.inlet_open", {})

    assert "digester.latched" in caught.value.context["missing"]


def test_storage_above_the_pressure_bound_is_rejected(runtime, drive):
    drive()

    with pytest.raises(OverLimitError) as caught:
        runtime.dispatch("gas.store", {"volume_m3": 120.0, "pressure_kpa": 30.0})

    assert caught.value.context["limit"] == 24.0


def test_storing_before_the_inlet_opens_is_rejected_as_out_of_order(runtime, drive):
    drive(inlet=False)

    with pytest.raises(OrderViolationError):
        runtime.dispatch("gas.store", {"volume_m3": 120.0, "pressure_kpa": 20.0})


def test_reopening_the_inlet_without_closing_it_is_rejected(runtime, drive):
    drive()

    with pytest.raises(OrderViolationError):
        runtime.dispatch("gas.inlet_open", {})


def test_inlet_can_be_closed_and_sealed(runtime, drive):
    drive()

    runtime.dispatch("gas.inlet_close", {})

    state = runtime.state()
    assert state["lines"]["gas"]["phase"] == "sealed"
    assert state["subsystems"]["gas"]["inlet_open"] is False


def test_closing_an_inlet_that_never_opened_is_blocked(runtime):
    with pytest.raises(Exception) as caught:
        runtime.dispatch("gas.inlet_close", {})

    assert getattr(caught.value, "code", "") in ("interlock_blocked", "order_violation")
