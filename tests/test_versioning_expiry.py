"""Confirmations and baselines expire, and expiry is enforced."""

from __future__ import annotations

import pytest

from bgs.errors import ArtifactExpiredError, NotFoundError, StaleGenerationError, ValidationError
from bgs.versioning.baseline import Baseline, BaselineRegistry
from bgs.versioning.confirmation import Confirmation, ConfirmationLedger
from bgs.versioning.expiry import Validity


def test_validity_reports_its_last_usable_tick():
    validity = Validity.of(issued_tick=5, ttl_ticks=4)

    assert validity.valid_until() == 9
    assert validity.remaining(now=7) == 2
    assert validity.age(now=7) == 2


def test_validity_expires_after_its_window():
    validity = Validity.of(issued_tick=5, ttl_ticks=4)

    assert validity.is_expired(9) is False
    assert validity.is_expired(10) is True


def test_validity_never_expires_when_it_is_unbounded():
    validity = Validity.never(issued_tick=5)

    assert validity.is_expired(10_000) is False
    assert validity.remaining(now=10_000) == -1


def test_require_raises_artifact_expired_with_the_original_window():
    validity = Validity.of(issued_tick=2, ttl_ticks=3)

    with pytest.raises(ArtifactExpiredError) as caught:
        validity.require(now=9, label="outlet verification")

    assert caught.value.context["valid_until"] == 5
    assert caught.value.context["now"] == 9


def test_validity_rejects_a_zero_tick_budget():
    with pytest.raises(ValidationError):
        Validity.of(issued_tick=0, ttl_ticks=0)


def _confirmation(generation: int, issued: int, ttl: int) -> Confirmation:
    return Confirmation(
        confirmation_id=f"conf-{generation:06d}",
        subject="desul",
        generation=generation,
        issuer="desul",
        validity=Validity.of(issued, ttl),
    )


def test_confirmation_ledger_returns_the_latest_confirmation():
    ledger = ConfirmationLedger()
    ledger.record(_confirmation(1, 0, 10))
    latest = _confirmation(2, 3, 10)
    ledger.record(latest)

    assert ledger.latest("desul") is latest
    assert len(ledger.history("desul")) == 2
    assert ledger.subjects() == ("desul",)


def test_confirmation_ledger_rejects_an_expired_confirmation():
    ledger = ConfirmationLedger()
    ledger.record(_confirmation(1, 0, 4))

    with pytest.raises(ArtifactExpiredError):
        ledger.require("desul", generation=1, now=9)


def test_confirmation_ledger_rejects_a_confirmation_from_another_generation():
    ledger = ConfirmationLedger()
    ledger.record(_confirmation(1, 0, 30))

    with pytest.raises(StaleGenerationError):
        ledger.require("desul", generation=2, now=1)


def test_confirmation_ledger_requires_a_recorded_confirmation():
    ledger = ConfirmationLedger()

    with pytest.raises(NotFoundError):
        ledger.require("desul", generation=1, now=0)


def test_confirmation_ledger_refuses_a_confirmation_without_a_generation():
    ledger = ConfirmationLedger()

    with pytest.raises(StaleGenerationError):
        ledger.record(_confirmation(0, 0, 10))


def _baseline(generation: int, issued: int, ttl: int, value: float = 1500.0) -> Baseline:
    return Baseline(
        name="membrane_pressure",
        value=value,
        unit="kPa",
        generation=generation,
        validity=Validity.of(issued, ttl),
    )


def test_baseline_registry_returns_the_current_calibration():
    registry = BaselineRegistry()
    registry.publish(_baseline(1, 0, 20))

    assert registry.current("membrane_pressure").value == 1500.0
    assert registry.names() == ("membrane_pressure",)
    assert len(registry.history("membrane_pressure")) == 1


def test_baseline_registry_rejects_an_expired_calibration():
    registry = BaselineRegistry()
    registry.publish(_baseline(1, 0, 3))

    with pytest.raises(ArtifactExpiredError):
        registry.require("membrane_pressure", generation=1, now=6)


def test_baseline_registry_rejects_a_stale_generation():
    registry = BaselineRegistry()
    registry.publish(_baseline(1, 0, 30))
    registry.publish(_baseline(2, 1, 30, value=1520.0))

    with pytest.raises(StaleGenerationError):
        registry.require("membrane_pressure", generation=1, now=2)


def test_baseline_registry_refuses_a_generation_that_moves_backwards():
    registry = BaselineRegistry()
    registry.publish(_baseline(3, 0, 30))

    with pytest.raises(StaleGenerationError):
        registry.publish(_baseline(2, 1, 30))


def test_baseline_registry_requires_a_published_calibration():
    registry = BaselineRegistry()

    with pytest.raises(NotFoundError):
        registry.require("mix_ratio", generation=1, now=0)


def test_baseline_deviation_uses_the_current_value():
    registry = BaselineRegistry()
    registry.publish(_baseline(1, 0, 30, value=1500.0))

    assert registry.deviation("membrane_pressure", 1506.0) == 6.0


def test_baseline_deviation_needs_a_published_calibration():
    registry = BaselineRegistry()

    with pytest.raises(ValidationError):
        registry.deviation("membrane_pressure", 1500.0)
