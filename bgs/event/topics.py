"""Topic names and the origin to topic mapping."""

from __future__ import annotations

from ..errors import ValidationError

FEED = "feed"
STIR = "stir"
HEAT = "heat"
DIGESTER = "digester"
COMPRESS = "compress"
DESUL = "desul"
MEMBRANE = "membrane"
VENT = "vent"
GAS = "gas"
STORE = "store"
ALARM = "alarm"

TOPICS: tuple[str, ...] = (
    FEED,
    STIR,
    HEAT,
    DIGESTER,
    COMPRESS,
    DESUL,
    MEMBRANE,
    VENT,
    GAS,
    STORE,
    ALARM,
)

_ORIGIN_TOPICS = {
    "feed": FEED,
    "stir": STIR,
    "heat": HEAT,
    "digester": DIGESTER,
    "compress": COMPRESS,
    "desul": DESUL,
    "mem": MEMBRANE,
    "vent": VENT,
    "gas": GAS,
    "store": STORE,
    "console": STORE,
}


def topic_for(origin: str) -> str:
    """Return the topic that belongs to ``origin``."""

    topic = _ORIGIN_TOPICS.get(origin)
    if topic is None:
        raise ValidationError("origin has no topic", origin=origin)
    return topic
