"""Bound comparisons and the rolling quality window."""

from __future__ import annotations

import pytest

from bgs.config import Limits
from bgs.decision.thresholds import Threshold, ThresholdSet
from bgs.decision.window import SampleWindow
from bgs.errors import BelowLimitError, OverLimitError, ValidationError


def test_threshold_accepts_a_value_inside_its_bounds():
    threshold = Threshold("methane", "%", minimum=96.0, maximum=100.0)

    verdict = threshold.evaluate(98.0)

    assert verdict.ok is True
    assert verdict.code == "ok"


def test_threshold_rejects_a_value_above_its_ceiling_as_over_limit():
    threshold_set = ThresholdSet.from_limits(Limits())

    with pytest.raises(OverLimitError) as caught:
        threshold_set.require("sulfur", 30.0)

    assert caught.value.context["limit"] == 12.0
    assert caught.value.code == "over_limit"


def test_threshold_rejects_a_value_below_its_floor():
    threshold_set = ThresholdSet.from_limits(Limits())

    with pytest.raises(BelowLimitError) as caught:
        threshold_set.require("methane", 90.0)

    assert caught.value.context["limit"] == 96.0
    assert caught.value.code == "below_limit"


def test_threshold_set_reports_the_configured_bounds():
    threshold_set = ThresholdSet.from_limits(Limits())

    described = threshold_set.describe()

    assert described["mix_level"]["minimum"] == 0.8
    assert described["storage_pressure"]["maximum"] == 24.0
    assert "membrane_pressure" in threshold_set.names()


def test_threshold_set_rejects_an_unknown_name():
    threshold_set = ThresholdSet.from_limits(Limits())

    with pytest.raises(ValidationError):
        threshold_set.get("pressure_of_nothing")


def test_threshold_needs_at_least_one_bound():
    with pytest.raises(ValidationError):
        Threshold("open", "x")


def test_threshold_range_must_be_ordered():
    with pytest.raises(ValidationError):
        Threshold("range", "x", minimum=10.0, maximum=1.0)


def test_threshold_set_can_add_and_replace_bounds():
    threshold_set = ThresholdSet()
    threshold_set.add(Threshold("custom", "x", maximum=5.0))

    assert threshold_set.evaluate("custom", 6.0).code == "above_max"


def test_window_drops_samples_that_left_the_span():
    window = SampleWindow(span_ticks=3, capacity=4)
    for tick in range(5):
        window.add(tick, 97.0 + tick)

    window.prune(now=6)

    assert [sample.tick for sample in window.samples()] == [3, 4]


def test_window_keeps_the_newest_samples_within_capacity():
    window = SampleWindow(span_ticks=10, capacity=3)
    for tick in range(6):
        window.add(tick, 96.0)

    assert [sample.tick for sample in window.samples()] == [3, 4, 5]
    assert window.is_full() is True


def test_window_rejects_out_of_order_samples():
    window = SampleWindow(span_ticks=4, capacity=4)
    window.add(5, 97.0)

    with pytest.raises(ValidationError):
        window.add(4, 96.0)


def test_window_all_at_least_needs_samples_above_the_floor():
    window = SampleWindow(span_ticks=2, capacity=3)

    assert window.all_at_least(96.0) is False

    window.add(0, 96.0)
    window.add(1, 95.5)

    assert window.all_at_least(96.0) is False

    window.prune(now=3)

    assert [sample.value for sample in window.samples()] == [95.5]

    window.add(3, 97.0)

    assert window.all_at_least(96.0) is False

    window.prune(now=5)

    assert window.all_at_least(96.0) is True


def test_window_statistics_and_clear():
    window = SampleWindow(span_ticks=5, capacity=5)
    window.add(0, 96.0)
    window.add(1, 98.0)

    assert window.minimum() == 96.0
    assert window.maximum() == 98.0
    assert window.mean() == 97.0
    assert window.values() == (96.0, 98.0)
    assert window.all_at_most(98.0) is True

    window.clear()

    assert window.size() == 0
    assert window.mean() is None
    assert window.minimum() is None


def test_window_rejects_an_unusable_size():
    with pytest.raises(ValidationError):
        SampleWindow(span_ticks=0, capacity=4)

    with pytest.raises(ValidationError):
        SampleWindow(span_ticks=4, capacity=0)
