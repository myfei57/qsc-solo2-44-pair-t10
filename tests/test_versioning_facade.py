"""The facade that the services actually hold."""

from __future__ import annotations

import pytest

from bgs.errors import ArtifactExpiredError, ValidationError
from bgs.ids import SequenceIds
from bgs.versioning.facade import VersionedArtifacts


def test_confirmation_needs_an_issued_generation():
    versions = VersionedArtifacts.fresh(SequenceIds())

    with pytest.raises(ValidationError):
        versions.confirm("desul", tick=0, ttl_ticks=5, issuer="desul")


def test_facade_records_a_confirmation_against_the_newest_generation():
    versions = VersionedArtifacts.fresh(SequenceIds())
    versions.bump("desul", tick=2)

    confirmation = versions.confirm("desul", tick=2, ttl_ticks=6, issuer="desul")
    state = versions.confirmation_state("desul", now=4)

    assert confirmation.generation == 1
    assert state["confirmation_id"] == confirmation.confirmation_id
    assert state["expired"] is False


def test_confirmation_state_is_absent_before_any_confirmation():
    versions = VersionedArtifacts.fresh(SequenceIds())

    assert versions.confirmation_state("desul", now=0) is None


def test_publishing_a_baseline_bumps_its_own_generation():
    versions = VersionedArtifacts.fresh(SequenceIds())

    first = versions.publish_baseline("membrane_pressure", 1500.0, "kPa", tick=1, ttl_ticks=10)
    second = versions.publish_baseline("membrane_pressure", 1510.0, "kPa", tick=2, ttl_ticks=10)

    assert (first.generation, second.generation) == (1, 2)
    assert versions.baseline_value("membrane_pressure") == 1510.0


def test_adopted_baseline_keeps_its_original_validity():
    versions = VersionedArtifacts.fresh(SequenceIds())
    versions.adopt_baseline("mix_ratio", 1.4, "ratio", 3, validity=_validity())

    with pytest.raises(ArtifactExpiredError):
        versions.require_baseline("mix_ratio", generation=3, now=99)


def test_describe_lists_every_versioned_artifact():
    versions = VersionedArtifacts.fresh(SequenceIds())
    versions.publish_baseline("mix_ratio", 1.4, "ratio", tick=0, ttl_ticks=10)
    versions.bump("stir", tick=0)
    versions.confirm("stir", tick=0, ttl_ticks=5, issuer="stir")

    described = versions.describe(now=1)

    assert set(described) == {"generations", "baselines", "confirmations"}
    assert described["generations"]["stir"] == 1
    assert described["baselines"]["mix_ratio"]["expired"] is False
    assert described["confirmations"]["stir"]["expired"] is False


def _validity():
    from bgs.versioning.expiry import Validity

    return Validity.of(0, 4)
