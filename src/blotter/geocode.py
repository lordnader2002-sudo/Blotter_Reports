"""Geocode block addresses via the US Census Bureau geocoder (free, no key).

Some portals (Norfolk, Honolulu) publish fresh incidents with block addresses
but no coordinates. This fills the gap: addresses are normalized ("100 BLOCK OF
GRANBY ST" -> "100 GRANBY ST"), geocoded once, and cached in a committed JSON
file — block addresses repeat constantly, so the cache converges after a few
runs and daily geocoding traffic drops to a trickle.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import requests

log = logging.getLogger("blotter.geocode")

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
_BLOCK_RE = re.compile(r"\bBLOCK\s+(?:OF\s+)?", re.IGNORECASE)
_XY_RE = re.compile(r"\s*/\s*")  # intersections: "A ST / B ST" -> use first street


def normalize_address(address: str) -> str:
    """Make a block-style address geocodable: drop BLOCK OF, intersections' tail."""
    addr = _BLOCK_RE.sub("", address or "").strip()
    addr = _XY_RE.split(addr)[0].strip()  # Census handles single streets better
    return re.sub(r"\s+", " ", addr)


class Geocoder:
    """Census geocoder with a persistent cache and a per-run request budget."""

    def __init__(self, cache_path: str | Path, session: requests.Session | None = None,
                 max_lookups_per_run: int = 500, timeout: int = 15):
        self.cache_path = Path(cache_path)
        self.session = session or requests.Session()
        self.max_lookups = max_lookups_per_run
        self.timeout = timeout
        self.lookups = 0
        self.cache: dict[str, list[float] | None] = {}
        if self.cache_path.exists():
            try:
                self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                log.warning("Geocode cache unreadable; starting fresh")

    def geocode(self, address: str, hint: str) -> tuple[float, float] | None:
        """Return (lat, lon) for an address, or None. ``hint`` is 'City, ST'."""
        if not address:
            return None
        key = f"{normalize_address(address)}, {hint}".upper()
        if key in self.cache:
            val = self.cache[key]
            return (val[0], val[1]) if val else None
        if self.lookups >= self.max_lookups:
            return None  # budget spent; uncached addresses wait for the next run
        self.lookups += 1
        try:
            resp = self.session.get(
                CENSUS_URL,
                params={"address": key, "benchmark": "Public_AR_Current", "format": "json"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            matches = resp.json().get("result", {}).get("addressMatches", [])
        except (requests.RequestException, ValueError) as ex:
            log.warning("Geocode failed for %r: %s", key, ex)
            return None  # transient: do NOT cache, retry next run
        if matches:
            coords = matches[0].get("coordinates", {})
            lat, lon = coords.get("y"), coords.get("x")
            if lat is not None and lon is not None:
                self.cache[key] = [float(lat), float(lon)]
                return float(lat), float(lon)
        self.cache[key] = None  # definitive miss: cache so we don't re-ask
        return None

    def save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, indent=0, sort_keys=True),
                                   encoding="utf-8")


def fill_coordinates(incidents, entry, geocoder: Geocoder,
                     per_source_lookups: int = 120) -> int:
    """Geocode incidents missing lat/lon for a geocode_hint source. Returns fill count.

    When the entry lists geocode_priority_streets, ONLY addresses on those
    streets are geocoded — high-volume citywide feeds (San Diego CFS) would
    otherwise burn the whole lookup budget far from the mall. Each source also
    gets its own lookup allotment so an early high-volume source (Honolulu)
    cannot starve the ones that run after it.
    """
    streets = [s.upper() for s in getattr(entry, "geocode_priority_streets", [])]
    start = geocoder.lookups
    filled = 0
    for inc in incidents:
        if geocoder.lookups - start >= per_source_lookups:
            break  # this source's slice is spent; cache resumes next run
        if inc.lat is not None or not inc.address:
            continue
        if streets and not any(s in inc.address.upper() for s in streets):
            continue
        result = geocoder.geocode(inc.address, entry.geocode_hint)
        if result:
            inc.lat, inc.lon = result
            filled += 1
    return filled
