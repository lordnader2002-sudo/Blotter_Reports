#!/usr/bin/env python3
"""Probe open-data portals from CI to discover/validate registry endpoints.

Round 7 — wave-2 stragglers, all with named official endpoints from round 6:
- Indianapolis: IMPD_NIBRS_Public/1 (gis.indy.gov)
- Fort Worth:   CIVIC/Crime_Data/MapServer/0 (mapit.fortworthtexas.gov)
- Sioux Falls:  Data/Safety/MapServer/16 direct-layer (gis.siouxfalls.gov)
- Orlando:      resolve + probe the geopolis OPD crime services
"""

from __future__ import annotations

import json
import sys

import requests

S = requests.Session()
S.headers["User-Agent"] = "blotter-reports-probe/0.7"


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
        print(f"  !! non-JSON (HTTP {r.status_code}): {' '.join(r.text[:120].split())}")
        return None


def probe_layer(url, lat, lon, radius=1600, cap=30):
    meta = jsafe(get(url, {"f": "json"})) or {}
    if "error" in meta:
        print(f"  !! layer error: {meta['error']}")
        return
    fields = [(f["name"], f["type"].replace("esriFieldType", ""))
              for f in meta.get("fields", [])]
    print(f"  layer: {meta.get('name')}  maxRecordCount={meta.get('maxRecordCount')}")
    print(f"  fields({len(fields)}): {fields[:cap]}")
    q = {"f": "json", "where": "1=1", "geometry": f"{lon},{lat}",
         "geometryType": "esriGeometryPoint", "inSR": 4326,
         "spatialRel": "esriSpatialRelIntersects", "distance": radius,
         "units": "esriSRUnit_Meter", "outFields": "*", "returnGeometry": "false",
         "resultRecordCount": 2}
    data = jsafe(get(url.rstrip("/") + "/query", q)) or {}
    if "error" in data:
        print(f"  !! query error: {data['error']}")
        return
    feats = data.get("features", [])
    print(f"  radius query OK — {len(feats)} feature(s)")
    for f in feats[:2]:
        print(f"  sample: {json.dumps(f.get('attributes', {}), default=str)[:350]}")


def main():
    section("INDIANAPOLIS: IMPD_NIBRS_Public layer 1 (+ service layer list)")
    root = "https://gis.indy.gov/server/rest/services/IMPD/IMPD_NIBRS_Public/FeatureServer"
    meta = jsafe(get(root, {"f": "json"})) or {}
    print(f"  layers: {[(la.get('id'), la.get('name')) for la in (meta.get('layers') or [])]}")
    probe_layer(f"{root}/1", 39.9092273, -86.065379)

    section("FORT WORTH: CIVIC/Crime_Data/MapServer/0")
    probe_layer("https://mapit.fortworthtexas.gov/ags/rest/services/CIVIC/Crime_Data/MapServer/0",
                32.7101703, -97.4005879)

    section("SIOUX FALLS: Data/Safety/MapServer/16 (Police Calls for Service)")
    probe_layer("https://gis.siouxfalls.gov/arcgis/rest/services/Data/Safety/MapServer/16",
                43.5103141, -96.7757826)

    section("ORLANDO: resolve geopolis OPD crime services")
    data = jsafe(get("https://www.arcgis.com/sharing/rest/search",
                     {"f": "json", "q": 'OPD crimes owner:geopolis type:"Feature Service"',
                      "num": 8})) or {}
    for it in data.get("results", []):
        print(f"  - {it.get('title')!r} url={it.get('url')}")
    for it in data.get("results", []):
        title = (it.get("title") or "").lower()
        if it.get("url") and ("join" in title or title.strip() == "opd crimes" or "crimes view" in title):
            probe_layer(it["url"].rstrip("/") + "/0", 28.4858595, -81.4320188)

    print("\nProbe complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
