"""Generations move forward only, and stale ones are refused."""

from __future__ import annotations

import pytest

from bgs.errors import StaleGenerationError, ValidationError
from bgs.versioning.generation import GenerationRegistry


def test_current_generation_starts_at_zero():
    registry = GenerationRegistry()

    assert registry.current("stir") == 0


def test_bump_issues_the_next_generation():
    registry = GenerationRegistry()

    first = registry.bump("stir", tick=3)
    second = registry.bump("stir", tick=7)

    assert (first.value, second.value) == (1, 2)
    assert second.issued_tick == 7
    assert registry.current("stir") == 2
    assert registry.issued_count("stir") == 2


def test_require_accepts_the_current_generation():
    registry = GenerationRegistry()
    token = registry.bump("desul", tick=1)

    registry.require(token, now=2)


def test_require_rejects_a_replaced_generation_as_stale():
    registry = GenerationRegistry()
    first = registry.bump("desul", tick=1)
    registry.bump("desul", tick=2)

    with pytest.raises(StaleGenerationError) as caught:
        registry.require(first, now=3)

    assert caught.value.context["claimed"] == 1
    assert caught.value.context["current"] == 2


def test_require_rejects_a_generation_that_was_never_issued():
    registry = GenerationRegistry()
    registry.bump("desul", tick=1)
    token = registry.bump("desul", tick=1)

    with pytest.raises(ValidationError):
        registry.require(
            type(token)(subject=token.subject, value=9, issued_tick=0),
            now=1,
        )


def test_observe_refuses_to_move_a_generation_backwards():
    registry = GenerationRegistry()
    registry.observe("feed", 4)

    with pytest.raises(StaleGenerationError):
        registry.observe("feed", 2)


def test_observe_adopts_a_forward_generation():
    registry = GenerationRegistry()

    registry.observe("feed", 3)

    assert registry.current("feed") == 3
    assert registry.snapshot() == {"feed": 3}


def test_bump_rejects_an_unnamed_subject():
    registry = GenerationRegistry()

    with pytest.raises(ValidationError):
        registry.bump("", tick=0)
