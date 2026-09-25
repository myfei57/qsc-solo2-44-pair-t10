"""The desulphurisation, compressor and membrane chain."""

from __future__ import annotations

import pytest

from bgs.errors import ArtifactExpiredError, OrderViolationError, OverLimitError, StaleGenerationError


def test_outlet_above_the_sulphur_ceiling_is_rejected(runtime):
    with pytest.raises(OverLimitError) as caught:
        runtime.dispatch("desul.check", {"sulfur_ppm": 40.0})

    assert caught.value.context["limit"] == 12.0


def test_compressor_start_before_the_outlet_is_verified_is_rejected(runtime):
    with pytest.raises(OrderViolationError) as caught:
        runtime.dispatch("compress.start", {})

    assert caught.value.context["required_phase"] == "desul_verified"


def test_pressure_ramp_before_the_valve_opens_is_rejected_as_out_of_order(runtime, compressing):
    compressing()

    with pytest.raises(OrderViolationError) as caught:
        runtime.dispatch("mem.ramp", {"pressure_kpa": 1500, "baseline_generation": 1})

    assert caught.value.context["required_phase"] == "valve_open"


def test_analysis_before_the_ramp_is_rejected_as_out_of_order(runtime, prime):
    prime()

    with pytest.raises(OrderViolationError):
        runtime.dispatch("mem.analyze", {"methane": 97.0})


def test_pressure_ramp_with_a_replaced_baseline_generation_is_rejected(runtime, prime):
    prime()
    runtime.dispatch("baseline.publish", {"name": "membrane_pressure", "value": 1500, "unit": "kPa"})
    runtime.dispatch("baseline.publish", {"name": "membrane_pressure", "value": 1520, "unit": "kPa"})

    with pytest.raises(StaleGenerationError) as caught:
        runtime.dispatch("mem.ramp", {"pressure_kpa": 1520, "baseline_generation": 1})

    assert caught.value.context["baseline_generation"] == 2
    assert caught.value.context["required_generation"] == 1


def test_pressure_ramp_with_an_expired_baseline_is_rejected(runtime, prime):
    prime()
    runtime.dispatch(
        "baseline.publish",
        {"name": "membrane_pressure", "value": 1500, "unit": "kPa", "ttl_ticks": 2},
    )
    runtime.advance_ticks(6)

    with pytest.raises(ArtifactExpiredError) as caught:
        runtime.dispatch("mem.ramp", {"pressure_kpa": 1500, "baseline_generation": 1})

    assert caught.value.context["valid_until"] == 2


def test_pressure_ramp_outside_the_calibrated_band_is_rejected(runtime, prime):
    prime()
    runtime.dispatch("baseline.publish", {"name": "membrane_pressure", "value": 1500, "unit": "kPa"})

    with pytest.raises(OverLimitError) as caught:
        runtime.dispatch("mem.ramp", {"pressure_kpa": 1506, "baseline_generation": 1})

    assert caught.value.context["baseline"] == 1500.0
    assert caught.value.context["band"] == 2.0


def test_pressure_ramp_above_the_hard_bound_is_rejected(runtime, prime):
    prime()
    runtime.dispatch("baseline.publish", {"name": "membrane_pressure", "value": 1600, "unit": "kPa"})

    with pytest.raises(OverLimitError) as caught:
        runtime.dispatch("mem.ramp", {"pressure_kpa": 1602, "baseline_generation": 1})

    assert caught.value.context["limit"] == 1600.0


def test_expired_outlet_confirmation_blocks_the_compressor(runtime):
    runtime.dispatch("stir.start", {})
    runtime.dispatch("stir.homogenize", {"level": 0.9})
    runtime.dispatch("stir.persist", {})
    runtime.dispatch("feed.batch", {"batch_id": "B-1", "quantity": 5.0})
    runtime.dispatch("feed.start", {})
    runtime.dispatch("desul.check", {"sulfur_ppm": 6.0})
    runtime.advance_ticks(20)

    with pytest.raises(ArtifactExpiredError) as caught:
        runtime.dispatch("compress.start", {})

    assert caught.value.context["subject"] == "desul"
    assert caught.value.context["valid_until"] == 12


def test_verifying_the_outlet_twice_replaces_the_generation(runtime):
    runtime.dispatch("desul.check", {"sulfur_ppm": 6.0})
    runtime.dispatch("desul.check", {"sulfur_ppm": 7.0})

    assert runtime.versions.current_generation("desul") == 2
    assert runtime.state()["subsystems"]["desul"]["sulfur_ppm"] == 7.0


def test_vessel_pressure_above_the_bound_is_rejected_and_latches(runtime):
    with pytest.raises(OverLimitError) as caught:
        runtime.dispatch("digester.pressure", {"kpa": 25.0})

    assert caught.value.context["limit"] == 18.0
    assert runtime.state()["subsystems"]["digester"]["latched"] is True
    assert runtime.health()["latched"]["digester"] is True


def test_vessel_pressure_recovery_clears_the_latch(runtime):
    with pytest.raises(OverLimitError):
        runtime.dispatch("digester.pressure", {"kpa": 25.0})

    runtime.dispatch("digester.pressure", {"kpa": 10.0})

    assert runtime.health()["latched"]["digester"] is False


def test_vessel_records_zones_and_sensor_mapping(runtime):
    runtime.dispatch("digester.zone", {"zone": "middle", "temperature_c": 38.0})
    runtime.dispatch("digester.sensor", {"sensor_id": "T-11", "zone": "middle", "kind": "temperature"})

    digester = runtime.view.current()["digester"]
    assert digester["zone"]["temperature_c"] == 38.0
    assert digester["sensor"]["sensor_id"] == "T-11"


def test_unknown_temperature_zone_is_rejected(runtime):
    with pytest.raises(Exception) as caught:
        runtime.dispatch("digester.zone", {"zone": "top", "temperature_c": 38.0})

    assert getattr(caught.value, "code", "") == "validation_error"


def test_valve_close_before_the_valve_opens_is_rejected(runtime):
    runtime.dispatch("stir.start", {})
    runtime.dispatch("stir.homogenize", {"level": 0.9})
    runtime.dispatch("stir.persist", {})
    runtime.dispatch("feed.batch", {"batch_id": "B-1", "quantity": 5.0})
    runtime.dispatch("feed.start", {})
    runtime.dispatch("desul.check", {"sulfur_ppm": 6.0})
    runtime.dispatch("compress.start", {})

    with pytest.raises(Exception) as caught:
        runtime.dispatch("mem.valve_close", {})

    assert getattr(caught.value, "code", "") in ("interlock_blocked", "order_violation")
