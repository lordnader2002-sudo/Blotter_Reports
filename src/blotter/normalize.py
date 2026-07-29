"""Shared helpers used by adapters to map raw portal rows into the common schema."""

from __future__ import annotations

from datetime import UTC, datetime


def parse_datetime(value) -> datetime | None:
    """Parse a portal timestamp into a tz-aware UTC datetime, or None.

    Handles Socrata floating timestamps ("2024-06-01T00:00:00.000"), ISO strings
    with offsets, and ArcGIS epoch milliseconds (int/float).
    """
    if value is None or value == "":
        return None
    # ArcGIS returns epoch milliseconds.
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000.0, tz=UTC)
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Last resort: date-only or space-separated.
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
            try:
                dt = datetime.strptime(s, fmt)  # noqa: DTZ007 — UTC attached on return
                break
            except ValueError:
                continue
        else:
            return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def socrata_point(row: dict, point_field: str | None, lon_field: str | None):
    """Extract (lat, lon) from a Socrata row.

    Supports either a true Point column ({"coordinates": [lon, lat]}) when
    ``lon_field`` is None, or a pair of separate numeric columns otherwise.
    """
    if point_field and lon_field:
        return to_float(row.get(point_field)), to_float(row.get(lon_field))
    if point_field:
        val = row.get(point_field)
        if isinstance(val, dict) and "coordinates" in val:
            coords = val["coordinates"]
            if isinstance(coords, list) and len(coords) >= 2:
                return to_float(coords[1]), to_float(coords[0])  # [lon, lat]
        # Some datasets expose latitude/longitude attributes on the location object.
        if isinstance(val, dict):
            return to_float(val.get("latitude")), to_float(val.get("longitude"))
    return None, None
