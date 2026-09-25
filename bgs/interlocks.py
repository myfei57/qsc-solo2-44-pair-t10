"""The rule table every action is checked against."""

from __future__ import annotations

from .facts import (
    COMPRESS_RUNNING,
    DESUL_VERIFIED,
    DIGESTER_LATCHED,
    FEED_BATCH_DECLARED,
    FEED_OPEN,
    GAS_INLET_OPEN,
    HEAT_RUNNING,
    MEM_PRESSURISED,
    MEM_VALVE_OPEN,
    STIR_PERSISTED,
    STIR_RUNNING,
    VENT_FLARING,
    VENT_LATCHED,
)
from .statemachine.interlock import InterlockEngine, InterlockRule

DEFAULT_RULES: tuple[InterlockRule, ...] = (
    InterlockRule(
        name="stir-stop-needs-mixer",
        action="stir.stop",
        requires=(STIR_RUNNING,),
        message="the mixer can only be stopped while it runs",
    ),
    InterlockRule(
        name="stir-stop-forbidden-while-feeding",
        action="stir.stop",
        forbids=(FEED_OPEN,),
        message="the mixer must keep turning while the gate is open",
    ),
    InterlockRule(
        name="stir-homogenize-needs-mixer",
        action="stir.homogenize",
        requires=(STIR_RUNNING,),
        message="homogenisation needs the mixer running",
    ),
    InterlockRule(
        name="stir-persist-needs-mixer",
        action="stir.persist",
        requires=(STIR_RUNNING,),
        message="only a running mixer can be made durable",
    ),
    InterlockRule(
        name="feed-batch-needs-durable-mix",
        action="feed.batch",
        requires=(STIR_PERSISTED,),
        message="the mixer state must be durable before a batch is declared",
    ),
    InterlockRule(
        name="feed-start-needs-batch",
        action="feed.start",
        requires=(FEED_BATCH_DECLARED,),
        forbids=(DIGESTER_LATCHED,),
        message="the gate needs a declared batch and a vessel that is not latched",
    ),
    InterlockRule(
        name="feed-close-needs-open-gate",
        action="feed.close",
        requires=(FEED_OPEN,),
        message="only an open gate can be closed",
    ),
    InterlockRule(
        name="heat-ramp-needs-mixer",
        action="heat.ramp",
        requires=(STIR_RUNNING,),
        message="heating needs the mixer running",
    ),
    InterlockRule(
        name="heat-cool-needs-an-active-ramp",
        action="heat.cool",
        requires=(HEAT_RUNNING,),
        message="only an active ramp can be ended",
    ),
    InterlockRule(
        name="desul-check-forbidden-while-compressing",
        action="desul.check",
        forbids=(COMPRESS_RUNNING,),
        message="the outlet cannot be verified while the compressor runs",
    ),
    InterlockRule(
        name="compress-start-needs-verified-outlet",
        action="compress.start",
        requires=(DESUL_VERIFIED,),
        message="the compressor needs a verified outlet",
    ),
    InterlockRule(
        name="compress-stop-needs-running-compressor",
        action="compress.stop",
        requires=(COMPRESS_RUNNING,),
        message="only a running compressor can be stopped",
    ),
    InterlockRule(
        name="mem-valve-needs-compressor",
        action="mem.valve",
        requires=(COMPRESS_RUNNING,),
        message="the product valve needs the compressor running",
    ),
    InterlockRule(
        name="mem-valve-close-needs-open-valve",
        action="mem.valve_close",
        requires=(MEM_VALVE_OPEN,),
        message="only an open valve can be closed",
    ),
    InterlockRule(
        name="mem-ramp-needs-open-valve",
        action="mem.ramp",
        requires=(MEM_VALVE_OPEN,),
        message="the pressure ramp needs the product valve open",
    ),
    InterlockRule(
        name="mem-analyze-needs-ramp",
        action="mem.analyze",
        requires=(MEM_PRESSURISED,),
        message="the analyser needs a pressurised membrane",
    ),
    InterlockRule(
        name="vent-flare-needs-latch",
        action="vent.flare",
        requires=(VENT_LATCHED,),
        message="flaring needs the quality latch to be set",
    ),
    InterlockRule(
        name="vent-recover-needs-flaring",
        action="vent.recover",
        requires=(VENT_FLARING,),
        message="recovery needs the flare to be open",
    ),
    InterlockRule(
        name="gas-inlet-needs-ramp-and-clear-line",
        action="gas.inlet",
        requires=(MEM_PRESSURISED,),
        forbids=(VENT_LATCHED, DIGESTER_LATCHED),
        message="the inlet needs a pressurised membrane and a clear line",
    ),
    InterlockRule(
        name="gas-inlet-close-needs-open-inlet",
        action="gas.inlet_close",
        requires=(GAS_INLET_OPEN,),
        message="only an open inlet can be closed",
    ),
    InterlockRule(
        name="gas-store-needs-open-inlet",
        action="gas.store",
        requires=(GAS_INLET_OPEN,),
        message="gas can only be stored through an open inlet",
    ),
)


def build_engine(rules: tuple[InterlockRule, ...] | None = None) -> InterlockEngine:
    """Build the interlock engine, optionally with a replaced rule table."""

    return InterlockEngine(DEFAULT_RULES if rules is None else rules)
