"""Declared stage order and the refusal of misplaced stages."""

from __future__ import annotations

import pytest

from bgs.errors import OrderViolationError, ValidationError
from bgs.statemachine.machine import SequenceMachine
from bgs.statemachine.phases import FeedPhase, phase_names, sequence_for


def test_line_starts_at_its_first_stage():
    machine = SequenceMachine("feed")

    assert machine.phase == "idle"
    assert machine.index == 0
    assert machine.next_phase() == "stir_confirmed"


def test_advance_moves_to_the_next_declared_stage():
    machine = SequenceMachine("feed")

    step = machine.advance(FeedPhase.STIR_CONFIRMED.value, tick=4, reason="batch declared")

    assert step.step == 1
    assert machine.phase == "stir_confirmed"
    assert machine.last_step.reason == "batch declared"


def test_stage_requested_out_of_order_is_rejected():
    machine = SequenceMachine("feed")

    with pytest.raises(OrderViolationError) as caught:
        machine.advance(FeedPhase.FEEDING.value, tick=1, reason="skip ahead")

    assert caught.value.context["expected"] == "stir_confirmed"
    assert caught.value.code == "order_violation"


def test_repeating_the_current_stage_is_rejected_as_out_of_order():
    machine = SequenceMachine("feed")
    machine.advance(FeedPhase.STIR_CONFIRMED.value, tick=1, reason="first")

    with pytest.raises(OrderViolationError):
        machine.advance(FeedPhase.STIR_CONFIRMED.value, tick=2, reason="again")


def test_final_stage_refuses_further_moves():
    machine = SequenceMachine("upgrade")
    for phase in ("desul_verified", "compressing", "valve_open", "pressure_ramp"):
        machine.advance(phase, tick=1, reason="step")

    with pytest.raises(OrderViolationError):
        machine.advance("pressure_ramp", tick=2, reason="beyond the end")


def test_require_at_least_refuses_an_earlier_stage():
    machine = SequenceMachine("upgrade")

    with pytest.raises(OrderViolationError) as caught:
        machine.require_at_least("valve_open", action="mem.ramp")

    assert caught.value.context["required"] == "valve_open"
    assert machine.is_at_least("idle") is True


def test_rewind_cannot_move_a_line_forwards():
    machine = SequenceMachine("vent")

    with pytest.raises(OrderViolationError):
        machine.rewind_to("flaring", tick=1, reason="skip")


def test_rewind_records_the_earlier_stage():
    machine = SequenceMachine("vent")
    machine.advance("quality_alarm", tick=1, reason="alarm")
    machine.advance("flaring", tick=2, reason="flare")
    machine.advance("recovered", tick=3, reason="recovered")

    machine.rewind_to("quality_alarm", tick=9, reason="quality dropped again")

    assert machine.phase == "quality_alarm"
    assert machine.last_step.tick == 9


def test_hydrate_adopts_a_recorded_stage():
    machine = SequenceMachine("upgrade")

    machine.hydrate("compressing", step=2, tick=7)

    assert machine.phase == "compressing"
    assert machine.next_phase() == "valve_open"


def test_hydrate_rejects_a_step_behind_the_named_stage():
    machine = SequenceMachine("upgrade")

    with pytest.raises(OrderViolationError):
        machine.hydrate("pressure_ramp", step=1, tick=1)


def test_unknown_stage_is_rejected():
    machine = SequenceMachine("vent")

    with pytest.raises(ValidationError):
        machine.is_at_least("nowhere")


def test_unknown_line_is_rejected():
    with pytest.raises(ValidationError):
        sequence_for("pressurised-water")

    with pytest.raises(ValidationError):
        phase_names("pressurised-water")


def test_phase_names_lists_the_declared_order():
    assert phase_names("gas") == ["idle", "open", "sealed"]
    assert SequenceMachine("gas").order() == ("idle", "open", "sealed")
