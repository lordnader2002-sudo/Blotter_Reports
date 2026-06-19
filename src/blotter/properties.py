"""Load the mall properties CSV into ``Property`` objects keyed by property_id."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Property:
    property_id: str
    name: str
    address: str
    postal_code: str
    lat: float
    lon: float


def load_properties(path: str | Path) -> dict[str, Property]:
    """Read the properties CSV and return a dict property_id -> Property.

    Rows missing usable coordinates are skipped (some OCONUS rows lack a postal
    code but still have lat/lon; only lat/lon are required here).
    """
    props: dict[str, Property] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            pid = (row.get("property_id") or "").strip()
            if not pid:
                continue
            try:
                lat = float(row["lat"])
                lon = float(row["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            props[pid] = Property(
                property_id=pid,
                name=(row.get("name") or "").strip(),
                address=(row.get("address") or "").strip(),
                postal_code=(row.get("postal_code") or "").strip(),
                lat=lat,
                lon=lon,
            )
    return props
