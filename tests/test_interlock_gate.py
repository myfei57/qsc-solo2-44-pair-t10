"""Interlock evaluation and the pre gate."""

from __future__ import annotations

import pytest

from bgs.errors import InterlockBlockedError, NotDurableError, OrderViolationError, ValidationError
from bgs.facts import DESUL_VERIFIED, STIR_PERSISTED, STIR_RUNNING, VENT_LATCHED
from bgs.interlocks import DEFAULT_RULES, build_engine
from bgs.statemachine.gate import PreGate
from bgs.statemachine.interlock import InterlockRule


def test_gate_allows_an_action_when_every_fact_holds():
    gate = PreGate(build_engine())
    facts = {STIR_RUNNING: True, STIR_PERSISTED: True, DESUL_VERIFIED: True, VENT_LATCHED: False}

    result = gate.require("stir.homogenize", facts=facts)

    assert result.allowed is True


def test_gate_blocks_an_action_when_a_required_fact_is_missing():
    gate = PreGate(build_engine())

    with pytest.raises(InterlockBlockedError) as caught:
        gate.require("heat.ramp", facts={STIR_RUNNING: False})

    assert STIR_RUNNING in caught.value.context["missing"]
    assert caught.value.code == "interlock_blocked"


def test_gate_reports_a_missing_durable_state_as_not_durable():
    gate = PreGate(build_engine())

    with pytest.raises(NotDurableError) as caught:
        gate.require("feed.batch", facts={STIR_PERSISTED: False})

    assert caught.value.code == "not_durable"
    assert STIR_PERSISTED in caught.value.context["missing"]


def test_gate_reports_a_forbidden_latch_as_interlock_blocked():
    engine = build_engine()
    facts = {DESUL_VERIFIED: True, VENT_LATCHED: True}

    decision = engine.evaluate("gas.inlet", facts)

    assert decision.allowed is False
    assert VENT_LATCHED in decision.missing


def test_gate_refuses_when_the_line_has_not_reached_the_required_stage():
    from bgs.statemachine.machine import SequenceMachine

    gate = PreGate(build_engine())
    machine = SequenceMachine("upgrade")

    with pytest.raises(OrderViolationError) as caught:
        gate.require("mem.ramp", facts={}, machine=machine, required_phase="valve_open")

    assert caught.value.context["required_phase"] == "valve_open"


def test_evaluate_reports_the_stage_block_without_raising():
    from bgs.statemachine.machine import SequenceMachine

    gate = PreGate(build_engine())
    result = gate.evaluate("mem.ramp", facts={}, machine=SequenceMachine("upgrade"), required_phase="valve_open")

    assert result.allowed is False
    assert result.decision.blocking[0] == "stage:valve_open"


def test_rules_for_returns_only_the_bound_rules():
    engine = build_engine()

    actions = engine.rules_for("gas.inlet")

    assert [rule.name for rule in actions] == ["gas-inlet-needs-ramp-and-clear-line"]
    assert "gas.inlet" in engine.actions()


def test_duplicate_rule_names_are_rejected():
    rule = InterlockRule(name="dup", action="a")

    with pytest.raises(ValidationError):
        build_engine((rule, rule))


def test_unknown_action_has_no_rules():
    engine = build_engine()

    decision = engine.evaluate("nothing.here", {})

    assert decision.allowed is True
    assert decision.checks == ()


def test_default_rule_table_covers_every_gated_action():
    actions = {rule.action for rule in DEFAULT_RULES}

    assert {"feed.batch", "feed.start", "heat.ramp", "compress.start", "mem.ramp", "vent.recover"} <= actions
