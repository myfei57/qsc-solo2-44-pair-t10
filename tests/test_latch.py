"""Latch set and clear ordering."""

from __future__ import annotations

import pytest

from bgs.errors import OrderViolationError
from bgs.statemachine.latch import Latch


def test_latch_starts_released():
    latch = Latch("quality")

    assert latch.latched is False
    assert latch.step == 0
    assert latch.history() == ()


def test_latch_records_set_and_clear_transitions():
    latch = Latch("quality")

    raised = latch.set(tick=3, reason="methane low")
    dropped = latch.clear(tick=9, reason="window recovered")

    assert (raised.step, dropped.step) == (1, 2)
    assert latch.latched is False
    assert [event.latched for event in latch.history()] == [True, False]


def test_clearing_a_released_latch_is_an_order_violation():
    latch = Latch("quality")

    with pytest.raises(OrderViolationError) as caught:
        latch.clear(tick=1, reason="nothing to clear")

    assert caught.value.context["latch"] == "quality"


def test_setting_an_already_latched_latch_is_an_order_violation():
    latch = Latch("quality")
    latch.set(tick=1, reason="first")

    with pytest.raises(OrderViolationError):
        latch.set(tick=2, reason="again")


def test_sync_adopts_a_recorded_position():
    latch = Latch("quality")

    latch.sync(latched=True, step=4, reason="hydrated")

    assert latch.latched is True
    assert latch.describe()["step"] == 4
    latch.clear(tick=5, reason="recovered")
    assert latch.latched is False


def test_describe_reports_the_transition_count():
    latch = Latch("overpressure")
    latch.set(tick=1, reason="high")
    latch.clear(tick=2, reason="normal")
    latch.set(tick=3, reason="high again")

    assert latch.describe()["transitions"] == 3
