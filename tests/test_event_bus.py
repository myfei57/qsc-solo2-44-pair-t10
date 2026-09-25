"""Topic validation and subscriber delivery."""

from __future__ import annotations

import pytest

from bgs.errors import ValidationError
from bgs.event.bus import Event, EventBus
from bgs.event.topics import ALARM, STORE, TOPICS, topic_for


def test_origin_maps_onto_a_topic():
    assert topic_for("mem") == "membrane"
    assert topic_for("console") == STORE
    assert set(TOPICS) >= {"feed", "stir", "alarm", "store"}


def test_unknown_origin_has_no_topic():
    with pytest.raises(ValidationError):
        topic_for("nowhere")


def test_publish_delivers_to_every_subscriber_of_the_topic():
    bus = EventBus()
    seen: list[str] = []
    bus.subscribe(ALARM, lambda event: seen.append(event.name))
    bus.subscribe(ALARM, lambda event: seen.append(event.name))

    delivered = bus.publish(Event(topic=ALARM, name="mem.quality.low", origin="mem", tick=1))

    assert delivered == 2
    assert seen == ["mem.quality.low", "mem.quality.low"]
    assert bus.counts() == {ALARM: 1}
    assert bus.published() == ("mem.quality.low",)


def test_publish_reaches_wildcard_subscribers():
    bus = EventBus()
    seen: list[str] = []
    bus.subscribe_all(lambda event: seen.append(event.topic))

    bus.publish(Event(topic=STORE, name="version.baseline_published", origin="console", tick=2))

    assert seen == [STORE]


def test_publishing_to_an_unknown_topic_is_rejected():
    bus = EventBus()

    with pytest.raises(ValidationError):
        bus.publish(Event(topic="nowhere", name="x", origin="mem", tick=0))


def test_subscribing_to_an_unknown_topic_is_rejected():
    bus = EventBus()

    with pytest.raises(ValidationError):
        bus.subscribe("nowhere", lambda event: None)


def test_event_describe_includes_the_payload():
    event = Event(topic=ALARM, name="digester.overpressure", origin="digester", tick=3, payload={"kpa": 25.0})

    described = event.describe()

    assert described["payload"] == {"kpa": 25.0}
    assert described["topic"] == ALARM
