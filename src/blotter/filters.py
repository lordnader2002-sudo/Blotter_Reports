"""Centralized filtering: recency, exact radius, crime-category mapping, dedupe.

Kept separate from the adapters so it is pure and testable without any HTTP.
"""

from __future__ import annotations

from datetime import datetime

from .geo import haversine_m
from .schema import CATEGORIES, OTHER, NormalizedIncident


def map_category(crime_type: str | None, mapping: dict[str, list[str]]) -> str:
    """Map a raw crime-type string to a bucket via case-insensitive substring match.

    ``mapping`` is bucket -> list of substrings. First bucket with a hit wins;
    unknown types fall back to OTHER (never silently dropped here).
    """
    if not crime_type:
        return OTHER
    text = crime_type.lower()
    for bucket in CATEGORIES:  # deterministic precedence: VIOLENT, PROPERTY, ...
        for needle in mapping.get(bucket, []):
            if needle.lower() in text:
                return bucket
    return OTHER


def apply(
    incidents: list[NormalizedIncident],
    cutoff: datetime,
    settings,
    properties,
) -> list[NormalizedIncident]:
    """Annotate categories, then drop by recency, exact radius, and keep/drop lists."""
    keep = set(settings.keep_categories)
    drop = set(settings.drop_categories)
    out: list[NormalizedIncident] = []
    for inc in incidents:
        inc.crime_category = map_category(inc.crime_type, settings.crime_categories)

        if inc.occurred_at is not None and inc.occurred_at < cutoff:
            continue

        prop = properties.get(inc.property_id)
        if prop is not None and inc.lat is not None and inc.lon is not None:
            dist = haversine_m(prop.lat, prop.lon, inc.lat, inc.lon)
            inc.distance_m = dist
            radius = settings.radius_m
            if dist > radius:
                continue

        if keep and inc.crime_category not in keep:
            continue
        if inc.crime_category in drop:
            continue
        out.append(inc)
    return out


def dedupe(incidents: list[NormalizedIncident]) -> list[NormalizedIncident]:
    """Drop duplicate incidents, preferring the native id when present."""
    seen: set = set()
    out: list[NormalizedIncident] = []
    for inc in incidents:
        if inc.incident_id:
            key = (inc.source_id, inc.incident_id)
        else:
            occ = inc.occurred_at.isoformat() if inc.occurred_at else None
            key = (inc.property_id, occ, inc.crime_type, inc.lat, inc.lon)
        if key in seen:
            continue
        seen.add(key)
        out.append(inc)
    return out
