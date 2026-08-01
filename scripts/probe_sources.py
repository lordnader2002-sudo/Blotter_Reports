#!/usr/bin/env python3
"""Probe open-data portals from CI to discover/validate registry endpoints.

Round 8 — single leftover: Indianapolis IMPD_NIBRS_Public layer 1.
Round 7 confirmed the layer is spatially queryable but the field list was
truncated (30 of 44) and samples were oldest-first — this round prints the
FULL field list and date-sorted samples near Castleton Square to settle the
address/geometry question and freshness.
"""

from __future__ import annotations

import json
import sys

import requests

S = requests.Session()
S.headers["User-Agent"] = "blotter-reports-probe/0.8"

URL = "https://gis.indy.gov/server/rest/services/IMPD/IMPD_NIBRS_Public/FeatureServer/1"
LAT, LON = 39.9092273, -86.065379  # Castleton Square


def get(url, params=None, timeout=40):
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
        print(f"  !! non-JSON (HTTP {r.status_code}): {' '.join(r.text[:120].split())}")
        return None


def main():
    print("== INDIANAPOLIS: IMPD_NIBRS_Public/1 — full fields + date-sorted samples ==")
    meta = jsafe(get(URL, {"f": "json"})) or {}
    fields = [(f["name"], f["type"].replace("esriFieldType", ""))
              for f in meta.get("fields", [])]
    print(f"fields (ALL {len(fields)}): {fields}")

    q = {"f": "json", "where": "1=1", "geometry": f"{LON},{LAT}",
         "geometryType": "esriGeometryPoint", "inSR": 4326,
         "spatialRel": "esriSpatialRelIntersects", "distance": 1600,
         "units": "esriSRUnit_Meter", "outFields": "*", "returnGeometry": "true",
         "outSR": 4326, "resultRecordCount": 3, "orderByFields": "OccurredFrom DESC"}
    data = jsafe(get(URL + "/query", q)) or {}
    if "error" in data:
        print(f"!! query error: {data['error']}")
        # Retry without orderBy in case sorting is unsupported.
        q.pop("orderByFields")
        data = jsafe(get(URL + "/query", q)) or {}
    feats = data.get("features", [])
    print(f"radius query — {len(feats)} feature(s) near Castleton")
    for f in feats[:3]:
        print(f"  geometry: {f.get('geometry')}")
        print(f"  attrs: {json.dumps(f.get('attributes', {}), default=str)[:450]}")
    print("\nProbe complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
