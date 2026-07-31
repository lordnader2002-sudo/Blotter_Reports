#!/usr/bin/env python3
"""Probe open-data portals from CI to discover/validate registry endpoints.

Round 5 — targeted follow-ups from the wave-1 sweep:
- Tempe: the real "General Offenses" service (only hate-crimes was probed).
- Houston: the recent-crime-reports service (yearly archive is stale).
- Tampa: FULL field list of crimes_public_365days (round 4 capped at 30 fields
  and missed the date column).
- Wichita: direct layer-0 metadata on the ageweb MapServer.
"""

from __future__ import annotations

import json
import sys

import requests

S = requests.Session()
S.headers["User-Agent"] = "blotter-reports-probe/0.5"


def section(title):
    print(f"\n{'=' * 70}\n== {title}\n{'=' * 70}")


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
        print(f"  !! non-JSON (HTTP {r.status_code}): {' '.join(r.text[:150].split())}")
        return None


def probe_layer(url, lat, lon, order_field=None):
    meta = jsafe(get(url, {"f": "json"})) or {}
    if "error" in meta:
        print(f"  !! layer error: {meta['error']}")
        return
    fields = [(f["name"], f["type"].replace("esriFieldType", ""))
              for f in meta.get("fields", [])]
    print(f"  layer: {meta.get('name')}  maxRecordCount={meta.get('maxRecordCount')}")
    print(f"  fields (ALL {len(fields)}): {fields}")
    q = {"f": "json", "where": "1=1", "geometry": f"{lon},{lat}",
         "geometryType": "esriGeometryPoint", "inSR": 4326,
         "spatialRel": "esriSpatialRelIntersects", "distance": 1500,
         "units": "esriSRUnit_Meter", "outFields": "*", "returnGeometry": "false",
         "resultRecordCount": 2}
    if order_field:
        q["orderByFields"] = f"{order_field} DESC"
    data = jsafe(get(url.rstrip("/") + "/query", q)) or {}
    if "error" in data:
        print(f"  !! query error: {data['error']}")
        return
    feats = data.get("features", [])
    print(f"  radius query OK — {len(feats)} feature(s)")
    for f in feats[:2]:
        print(f"  sample: {json.dumps(f.get('attributes', {}), default=str)[:400]}")


def main():
    section("TEMPE: General Offenses (Open Data)")
    # Search result gave the item; resolve its service url first.
    data = jsafe(get("https://www.arcgis.com/sharing/rest/search",
                     {"f": "json", "q": 'General Offenses owner:tempeautomation type:"Feature Service"',
                      "num": 5})) or {}
    for it in data.get("results", []):
        print(f"  - {it.get('title')!r} owner={it.get('owner')} url={it.get('url')}")
        if it.get("url") and "offense" in (it.get("title") or "").lower():
            probe_layer(it["url"].rstrip("/") + "/0", 33.38327, -111.96453)
            break

    section("HOUSTON: NIBRS Recent Crime Reports (on-prem)")
    probe_layer("https://mycity2.houstontx.gov/pubgis02/rest/services/HPD/"
                "NIBRS_Recent_Crime_Reports/FeatureServer/0", 29.739343, -95.4641184)

    section("TAMPA: crimes_public_365days FULL fields")
    probe_layer("https://services1.arcgis.com/IbNXlmt2RVVRCZ6M/arcgis/rest/services/"
                "crimes_public_365days/FeatureServer/0", 27.9654551, -82.5204017)

    section("WICHITA: OpenData/Crime MapServer layer 0 direct")
    probe_layer("https://gismaps.wichita.gov/ageweb/rest/services/OpenData/Crime/"
                "MapServer/0", 37.6826997, -97.2474183)

    print("\nProbe complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
