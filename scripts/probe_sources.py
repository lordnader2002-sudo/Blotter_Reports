#!/usr/bin/env python3
"""Probe open-data portals from CI to discover/validate registry endpoints.

Round 15 — wave-4 follow-ups:
- Bloomington IN: columns + latest sample for Calls for Service (t5xf-ggw6),
  fresh as of today per round 14.
- The dead Socrata domains (City of Las Vegas, Nassau, Westchester) likely
  moved to ArcGIS Hubs — search AGOL for their current services (never swept
  in earlier waves).
"""

from __future__ import annotations

import json
import sys

import requests

S = requests.Session()
S.headers["User-Agent"] = "blotter-reports-probe/0.15"

ARCGIS = [
    ("VEGAS cluster/City of Las Vegas", ['las vegas crime type:"Feature Service"',
                                         'city of las vegas police type:"Feature Service"'],
     36.1632062, -115.1587666, "lasvegas|las vegas|lvmpd|clark"),
    ("ROOSEVELT/Nassau County NY", ['nassau county police type:"Feature Service"'],
     40.7383205, -73.61396, "nassau"),
    ("WESTCHESTER/Westchester NY", ['westchester county police type:"Feature Service"'],
     41.0312752, -73.7591855, "westchester"),
]

OFFICIAL = ("city", "county", "gov", "gis", "police", "sheriff", "opendata", "pd")


def section(title):
    print(f"\n{'=' * 70}\n== {title}\n{'=' * 70}")


def get(url, params=None, timeout=45):
    try:
        return S.get(url, params=params or {}, timeout=timeout)
    except requests.RequestException as ex:
        print(f"  !! request failed: {ex}")
        return None


def jsafe(r):
    if r is None:
        return None
    try:
        return r.json()
    except ValueError:
        print(f"  !! non-JSON (HTTP {r.status_code}): {' '.join(r.text[:150].split())}")
        return None


def bloomington():
    section("BLOOMINGTON IN: t5xf-ggw6 (Calls for Service) columns + sample")
    for ds in ("t5xf-ggw6", "vq37-rm9u"):
        cols = jsafe(get(f"https://data.bloomington.in.gov/api/views/{ds}/columns.json")) or []
        pairs = [(c.get("fieldName"), c.get("dataTypeName")) for c in cols]
        print(f"  [{ds}] cols: {pairs}")
        r = get(f"https://data.bloomington.in.gov/resource/{ds}.json",
                {"$limit": 1, "$order": ":id DESC"})
        rows = jsafe(r) if r is not None and r.status_code == 200 else None
        if rows:
            print(f"  [{ds}] sample: {json.dumps(rows[0], default=str)[:330]}")


def probe_layer(url, lat, lon):
    meta = jsafe(get(url, {"f": "json"})) or {}
    if "error" in meta:
        print(f"    !! layer error: {meta['error']}")
        return
    fields = [(f["name"], f["type"].replace("esriFieldType", ""))
              for f in meta.get("fields", [])]
    print(f"    layer: {meta.get('name')} fields({len(fields)}): {fields[:25]}")
    q = {"f": "json", "where": "1=1", "geometry": f"{lon},{lat}",
         "geometryType": "esriGeometryPoint", "inSR": 4326,
         "spatialRel": "esriSpatialRelIntersects", "distance": 1600,
         "units": "esriSRUnit_Meter", "outFields": "*", "returnGeometry": "true",
         "outSR": 4326, "resultRecordCount": 1}
    data = jsafe(get(url.rstrip("/") + "/query", q)) or {}
    if "error" in data:
        print(f"    !! query error: {data['error']}")
        return
    feats = data.get("features", [])
    print(f"    radius query OK — {len(feats)} feature(s)")
    if feats:
        print(f"    geometry: {feats[0].get('geometry')}")
        print(f"    sample: {json.dumps(feats[0].get('attributes', {}), default=str)[:300]}")


def arcgis_city(label, queries, lat, lon, own_hint):
    section(f"ARCGIS: {label}")
    seen, probed = set(), 0
    hints = tuple(own_hint.split("|")) + OFFICIAL
    for q in queries:
        data = jsafe(get("https://www.arcgis.com/sharing/rest/search",
                         {"f": "json", "q": q, "num": 6})) or {}
        for it in data.get("results", []):
            url = it.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            owner = (it.get("owner") or "").lower()
            print(f"  - {it.get('title')!r} owner={it.get('owner')} url={url}")
            if probed < 2 and any(h in owner for h in hints):
                probed += 1
                root = url.rstrip("/")
                meta = jsafe(get(root, {"f": "json"})) or {}
                layers = [(la.get("id"), la.get("name")) for la in (meta.get("layers") or [])]
                if layers:
                    print(f"    layers: {layers[:6]}")
                    probe_layer(f"{root}/{layers[0][0]}", lat, lon)
                else:
                    probe_layer(f"{root}/0", lat, lon)


def main():
    bloomington()
    for label, queries, lat, lon, hint in ARCGIS:
        arcgis_city(label, queries, lat, lon, hint)
    print("\nProbe complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
