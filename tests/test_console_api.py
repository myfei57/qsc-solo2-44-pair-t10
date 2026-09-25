"""The HTTP console: reads, commands and error reporting."""

from __future__ import annotations

from bgs.console.handlers import COMMAND_ROUTES


def test_health_endpoint_reports_ok(console):
    status, payload = console.get("/api/health")

    assert status == 200
    assert payload["status"] == "ok"
    assert payload["line"] == "line-test"
    assert payload["watermark"]["committed_seq"] > 0


def test_state_endpoint_exposes_lines_subsystems_and_interlocks(console):
    status, payload = console.get("/api/state")

    assert status == 200
    assert set(payload["subsystems"]) == {
        "stir",
        "feed",
        "heat",
        "digester",
        "desul",
        "compress",
        "mem",
        "vent",
        "gas",
    }
    assert set(payload["lines"]) == {"feed", "upgrade", "vent", "gas"}
    assert "stir.persist" in payload["interlocks"]["actions"]
    assert payload["facts"]["stir.running"] is False
    assert payload["config"]["line"] == "line-test"


def test_command_endpoint_runs_the_feed_chain(console):
    assert console.post("/api/stir/start")[0] == 200
    assert console.post("/api/stir/homogenize", {"level": 0.9})[0] == 200
    assert console.post("/api/stir/persist")[0] == 200
    assert console.post("/api/feed/batch", {"batch_id": "B-1", "quantity": 5.0})[0] == 200
    assert console.post("/api/feed/start")[0] == 200

    status, payload = console.post("/api/feed/close")

    assert status == 200
    assert payload["result"]["phase"] == "fermenting"
    assert payload["command"] == "feed.close"


def test_command_endpoint_reports_a_missing_durable_state(console):
    status, payload = console.post("/api/feed/batch", {"batch_id": "B-1", "quantity": 5.0})

    assert status == 409
    assert payload["code"] == "not_durable"
    assert "stir.persisted" in payload["context"]["missing"]


def test_command_endpoint_reports_a_missing_field(console):
    status, payload = console.post("/api/mem/press", {})

    assert status == 400
    assert payload["code"] == "validation_error"
    assert payload["context"]["field"] == "pressure_kpa"


def test_unknown_route_returns_not_found(console):
    status, payload = console.get("/api/nothing")

    assert status == 404
    assert payload["code"] == "not_found"


def test_method_not_allowed_is_reported(console):
    status, payload = console.post("/api/health")

    assert status == 405
    assert payload["code"] == "method_not_allowed"


def test_records_endpoint_filters_by_kind(console):
    console.post("/api/stir/start")
    console.post("/api/stir/homogenize", {"level": 0.9})

    status, payload = console.get("/api/records?kind=stir.mixer&limit=5")

    assert status == 200
    assert payload["total"] >= 1
    assert set(payload["by_kind"]) == {"stir.mixer"}


def test_records_endpoint_hides_tombstones_until_asked(console):
    console.post("/api/stir/start")
    console.post("/api/stir/homogenize", {"level": 0.9})
    status, rollback = console.post("/api/rollback", {"seq": 1})
    assert status == 200
    assert rollback["result"]["tombstones"]

    hidden = console.get("/api/records?limit=50")[1]
    shown = console.get("/api/records?limit=50&include_tombstones=true")[1]

    assert shown["total"] > hidden["total"]


def test_history_endpoint_needs_a_tick(console):
    status, payload = console.get("/api/history")

    assert status == 400
    assert payload["code"] == "validation_error"


def test_history_endpoint_compares_with_an_earlier_tick(console):
    console.post("/api/stir/start")
    console.post("/api/clock/advance", {"ticks": 4})
    console.post("/api/stir/homogenize", {"level": 0.9})

    status, payload = console.get("/api/history?tick=0")

    assert status == 200
    assert set(payload["delta"]["added"]) == {"stir.mix", "store.clock"}
    assert payload["state"]["stir"]["mixer"]["active"] is True
    assert "mix" not in payload["state"]["stir"]


def test_clock_endpoint_advances_the_deterministic_tick(console):
    console.post("/api/clock/advance", {"ticks": 3})

    status, payload = console.get("/api/health")

    assert status == 200
    assert payload["tick"] == 3


def test_alarms_endpoint_lists_recorded_alarms(console, runtime, drive):
    drive()
    console.post("/api/mem/analyze", {"methane": 90.0})

    status, payload = console.get("/api/alarms")

    assert status == 200
    assert payload["alarms"][0]["name"] == "mem.quality.low"
    assert runtime.alarms.count() == 1


def test_feed_timeline_endpoint_lists_the_batch(console):
    console.post("/api/stir/start")
    console.post("/api/stir/homogenize", {"level": 0.9})
    console.post("/api/stir/persist")
    console.post("/api/feed/batch", {"batch_id": "B-4", "quantity": 5.0})

    status, payload = console.get("/api/feed/timeline")

    assert status == 200
    assert payload["timeline"][0]["batch_id"] == "B-4"


def test_overview_page_is_html(console):
    status, body = console.get("/")

    assert status == 200
    assert body.lstrip().lower().startswith("<!doctype html")
    assert "Overview" in body


def test_operations_and_records_pages_render(console):
    assert console.get("/operations")[0] == 200
    status, body = console.get("/records")

    assert status == 200
    assert "Records" in body


def test_every_command_has_a_unique_route(runtime):
    routed = [command for _, _, command in COMMAND_ROUTES]

    assert len(routed) == len(set(routed))
    assert set(routed) == set(runtime.commands())


def test_baseline_and_snapshot_endpoints_answer(console):
    status, payload = console.post(
        "/api/baseline",
        {"name": "mix_ratio", "value": 1.4, "unit": "ratio", "ttl_ticks": 5},
    )

    assert status == 200
    assert payload["result"]["baseline"]["generation"] == 1

    status, payload = console.post("/api/snapshot")

    assert status == 200
    assert payload["result"]["snapshot"]["watermark_seq"] >= 1


def test_digester_pressure_endpoint_reports_the_bound(console):
    status, payload = console.post("/api/digester/pressure", {"kpa": 25.0})

    assert status == 409
    assert payload["code"] == "over_limit"
    assert payload["context"]["limit"] == 18.0
