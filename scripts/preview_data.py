#!/usr/bin/env python3
"""Generate a populated sample ``dashboard_data.json`` for local dashboard preview.

The live open-data portals require outbound network access, so this builds a
realistic synthetic dataset around the pilot malls and runs it through the *real*
rollup + JSON export — guaranteeing the file matches what ``blotter run`` emits.

    python scripts/preview_data.py            # writes ./dashboard_data.json
    python -m http.server                      # then open dashboard.html

This is SAMPLE data for UI preview only; CI overwrites it with real incidents.
"""

from __future__ import annotations

import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from blotter.errors import RunReport
from blotter.geo import haversine_m
from blotter.pipeline import RunResult
from blotter.properties import load_properties
from blotter.report import json_export
from blotter.report.rollup import build_rollup
from blotter.schema import CATEGORIES, NormalizedIncident

PILOT = {
    "BEVCENTER": [("ROBBERY", "VIOLENT"), ("BURGLARY FROM VEHICLE", "PROPERTY"),
                  ("THEFT OF IDENTITY", "PROPERTY"), ("BATTERY - SIMPLE ASSAULT", "VIOLENT"),
                  ("VANDALISM", "PROPERTY"), ("TRESPASSING", "QUALITY_OF_LIFE")],
    "THEDOMAIN": [("THEFT", "PROPERTY"), ("AGG ASSAULT", "VIOLENT"), ("DUI", "QUALITY_OF_LIFE"),
                  ("AUTO THEFT", "PROPERTY"), ("DISORDERLY CONDUCT", "QUALITY_OF_LIFE")],
    "OPRYMILLS": [("SHOPLIFTING", "PROPERTY"), ("ROBBERY", "VIOLENT"), ("VANDALISM", "PROPERTY")],
    "NORTHGATE": [("THEFT", "PROPERTY"), ("NARCOTICS", "QUALITY_OF_LIFE"),
                  ("ASSAULT", "VIOLENT"), ("FRAUD", "PROPERTY")],
    "CHERRYCREEK": [("LARCENY", "PROPERTY"), ("MOTOR VEHICLE THEFT", "PROPERTY"),
                    ("AGGRAVATED ASSAULT", "VIOLENT"), ("PUBLIC INTOXICATION", "QUALITY_OF_LIFE")],
    "LENOX": [("LARCENY-FROM VEHICLE", "PROPERTY"), ("ROBBERY", "VIOLENT"),
              ("SHOPLIFTING", "PROPERTY"), ("WEAPON LAW VIOLATION", "VIOLENT")],
}


def main() -> int:
    rng = random.Random(42)
    props = load_properties("data/properties.csv")
    now = datetime.now(UTC)
    incidents: list[NormalizedIncident] = []
    report = RunReport()

    for pid, kinds in PILOT.items():
        prop = props.get(pid)
        if prop is None:
            continue
        n = rng.randint(len(kinds), len(kinds) + 8)
        for i in range(n):
            ctype, cat = rng.choice(kinds)
            # Jitter a point within ~900 m of the mall.
            dlat = rng.uniform(-0.008, 0.008)
            dlon = rng.uniform(-0.008, 0.008)
            lat, lon = prop.lat + dlat, prop.lon + dlon
            dist = haversine_m(prop.lat, prop.lon, lat, lon)
            incidents.append(
                NormalizedIncident(
                    property_id=pid, source_id=f"{pid}:sample", incident_id=f"{pid}-{i}",
                    occurred_at=now - timedelta(days=rng.randint(0, 29), hours=rng.randint(0, 23)),
                    crime_type=ctype, crime_category=cat, description=ctype,
                    address=f"{rng.randint(100, 9999)} Sample St", lat=lat, lon=lon, distance_m=dist,
                    raw={
                        "Weapon_Description": rng.choice(["NONE", "HANDGUN", "KNIFE", "OTHER"]),
                        "Location_Description": rng.choice(
                            ["SPECIALTY STORE", "PARKING LOT", "DEPARTMENT STORE", "RESTAURANT"]),
                        "Incident_Status_Description": rng.choice(
                            ["OPEN", "CLEARED BY ARREST", "INACTIVE"]),
                        "Victim_Number": rng.randint(0, 2),
                    },
                )
            )
        report.record_success(
            type("E", (), {"property_id": pid, "dataset_id": "sample", "name": f"{pid} sample", "type": "socrata"})(),
            type("R", (), {"source_id": f"{pid}:sample", "fetched_count": n, "truncated": False})(),
        )

    # One mall with no source -> coverage gap, mirroring real runs.
    pilot_ids = set(PILOT) | {"SOUTHPARK"}
    report.note_coverage_gaps({"SOUTHPARK"})

    result = RunResult(incidents, report, now, 30, now - timedelta(days=30), pilot_ids=sorted(pilot_ids))
    rollup = build_rollup(result, props)
    rollup.metadata["radius_m"] = 1000
    payload = json_export.write(rollup, "dashboard_data.json", trend_log_path="reports/trend_log.jsonl")
    print(f"Wrote dashboard_data.json — {payload['totals']['incidents']} incidents, "
          f"{len(rollup.summary)} malls, categories={[c for c in CATEGORIES]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
