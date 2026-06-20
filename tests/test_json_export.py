import json
from datetime import datetime, timedelta, timezone

from blotter.errors import RunReport, SourceStatus
from blotter.pipeline import RunResult
from blotter.properties import Property
from blotter.report import json_export
from blotter.report.rollup import build_rollup
from blotter.schema import PROPERTY, VIOLENT, NormalizedIncident

NOW = datetime(2026, 6, 19, tzinfo=timezone.utc)


def _rollup():
    props = {
        "BEVCENTER": Property("BEVCENTER", "Beverly Center", "", "", 34.07533, -118.37738),
        "LENOX": Property("LENOX", "Lenox Square", "", "", 33.8467, -84.3624),
    }
    incidents = [
        NormalizedIncident("BEVCENTER", "s1", "1", NOW - timedelta(days=2), "ROBBERY",
                           VIOLENT, "robbery", "8500 Beverly", 34.0770, -118.3775, 180.0),
        NormalizedIncident("BEVCENTER", "s1", "2", NOW - timedelta(days=5), "BURGLARY",
                           PROPERTY, "burglary", "8400 La Cienega", 34.0760, -118.3780, 320.0),
    ]
    report = RunReport()
    report.sources.append(SourceStatus("BEVCENTER", "s1", "LAPD", "OK", fetched_count=2))
    report.note_coverage_gaps({"LENOX"})
    result = RunResult(incidents, report, NOW, 30, NOW - timedelta(days=30),
                       pilot_ids=["BEVCENTER", "LENOX"])
    rollup = build_rollup(result, props)
    rollup.metadata["radius_m"] = 1000
    return rollup


def test_payload_shape_and_totals():
    payload = json_export.build_payload(_rollup())
    assert payload["totals"]["incidents"] == 2
    assert payload["totals"]["violent"] == 1
    assert payload["totals"]["malls"] == 2
    assert payload["totals"]["coverage_gaps"] == 1
    assert payload["radius_m"] == 1000
    assert payload["coverage_gaps"] == ["LENOX"]
    # Incidents serialized with ISO datetimes (JSON-safe).
    assert len(payload["incidents"]) == 2
    assert payload["incidents"][0]["occurred_at"].startswith("2026-06-17")
    # Source status carried through.
    assert payload["sources"][0]["status"] == "OK"


def test_write_is_valid_json_and_appends_trend(tmp_path):
    out = tmp_path / "dashboard_data.json"
    log = tmp_path / "trend_log.jsonl"
    json_export.write(_rollup(), out, trend_log_path=log)

    data = json.loads(out.read_text())
    assert data["totals"]["incidents"] == 2
    assert len(data["trend"]) == 1
    assert data["trend"][0]["violent"] == 1
    assert data["trend"][0]["property"] == 1

    # A second run with the same timestamp replaces (not duplicates) the entry.
    json_export.write(_rollup(), out, trend_log_path=log)
    assert len(json.loads(out.read_text())["trend"]) == 1
    assert len(log.read_text().strip().splitlines()) == 1
