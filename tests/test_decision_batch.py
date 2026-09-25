"""Batch identity stays unique, including across a restart."""

from __future__ import annotations

import pytest

from bgs.decision.batch import Batch, BatchRegistry
from bgs.errors import DuplicateError, NotFoundError, ValidationError


def test_declaring_a_batch_registers_it():
    registry = BatchRegistry()

    batch = registry.declare("B-1", tick=2, generation=1, quantity=12.5)

    assert batch.batch_id == "B-1"
    assert registry.has("B-1") is True
    assert registry.count() == 1
    assert [item.batch_id for item in registry.all()] == ["B-1"]


def test_duplicate_batch_identifier_is_rejected():
    registry = BatchRegistry()
    registry.declare("B-1", tick=2, generation=1, quantity=12.5)

    with pytest.raises(DuplicateError) as caught:
        registry.declare("B-1", tick=9, generation=2, quantity=3.0)

    assert caught.value.context["first_declared_tick"] == 2


def test_batch_quantity_must_be_positive():
    registry = BatchRegistry()

    with pytest.raises(ValidationError):
        registry.declare("B-2", tick=1, generation=1, quantity=0.0)


def test_batch_identifier_must_not_be_blank():
    registry = BatchRegistry()

    with pytest.raises(ValidationError):
        registry.declare("", tick=1, generation=1, quantity=1.0)


def test_unknown_batch_lookup_is_rejected():
    registry = BatchRegistry()

    with pytest.raises(NotFoundError):
        registry.get("B-9")


def test_adopt_refuses_a_repeated_batch():
    registry = BatchRegistry()
    batch = Batch(batch_id="B-1", generation=1, tick=1, quantity=4.0)
    registry.adopt(batch)

    with pytest.raises(DuplicateError):
        registry.adopt(batch)


def test_duplicate_batch_is_rejected_after_a_restart(runtime, boot):
    runtime.dispatch("stir.start", {})
    runtime.dispatch("stir.homogenize", {"level": 0.9})
    runtime.dispatch("stir.persist", {})
    runtime.dispatch("feed.batch", {"batch_id": "B-7", "quantity": 4.0})

    reopened = boot()

    assert reopened.batches.has("B-7") is True
    with pytest.raises(DuplicateError):
        reopened.dispatch("feed.batch", {"batch_id": "B-7", "quantity": 4.0})


def test_batch_generation_is_recorded_with_the_batch(runtime):
    runtime.dispatch("stir.start", {})
    runtime.dispatch("stir.homogenize", {"level": 0.9})
    runtime.dispatch("stir.persist", {})

    runtime.dispatch("feed.batch", {"batch_id": "B-3", "quantity": 5.0})

    batch = runtime.batches.get("B-3")
    assert batch.generation == runtime.versions.current_generation("feed")
