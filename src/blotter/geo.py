"""Geographic helpers: great-circle distance and bounding boxes.

These let us re-check radius membership exactly (portals' geo filters can be
approximate) and build lat/lon bounding-box queries for datasets that lack a
true point column usable by Socrata ``within_circle``.
"""

from __future__ import annotations

import math

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points, in meters."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bounding_box(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    """Return (min_lat, min_lon, max_lat, max_lon) enclosing the radius circle.

    Used for portals exposing only separate latitude/longitude columns. Slightly
    over-fetches (a box around the circle); callers re-filter with ``haversine_m``.
    """
    dlat = math.degrees(radius_m / EARTH_RADIUS_M)
    # Guard the cosine near the poles to avoid blowing up the longitude span.
    cos_lat = max(math.cos(math.radians(lat)), 1e-6)
    dlon = math.degrees(radius_m / (EARTH_RADIUS_M * cos_lat))
    return (lat - dlat, lon - dlon, lat + dlat, lon + dlon)


def annotate_distances(incidents, properties) -> None:
    """Fill ``distance_m`` on each incident from its mall's coordinates (in place).

    ``properties`` maps property_id -> object with ``.lat`` / ``.lon``.
    """
    for inc in incidents:
        if inc.lat is None or inc.lon is None:
            continue
        prop = properties.get(inc.property_id)
        if prop is None:
            continue
        inc.distance_m = haversine_m(prop.lat, prop.lon, inc.lat, inc.lon)
