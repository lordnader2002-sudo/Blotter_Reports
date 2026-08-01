#!/usr/bin/env python3
"""Probe open-data portals from CI to discover/validate registry endpoints.

Round 6 — WAVE-2 discovery:
- Houston: enumerate ALL layers of the recent-NIBRS service (offenses split
  across person/property/society sibling layers) and radius-test each.
- Re-search wave-1 misses with better query variants (Miami-Dade, Orlando,
  Indy, Tulsa, OKC, Fort Worth, El Paso, St. Pete, Knoxville, Springfield MO,
  Tacoma) and fresh candidates (Greenville SC, Sioux Falls, Reno, Boca Raton,
  Coral Springs, Sunrise FL).
- Socrata re-checks: Memphis, SLC (via opendata.utah.gov), Arlington VA.
Output is deliberately compact; a parser distills it into registry entries.
"""

from __future__ import annotations

import json
import sys

import requests

S = requests.Session()
S.headers["User-Agent"] = "blotter-reports-probe/0.6"

ARCGIS = [
    ("DADELAND/Miami-Dade", ['owner:MDPD type:"Feature Service"',
                             'miami dade police incident type:"Feature Service"'],
     25.6905361, -80.312504, "miami|dade|mdpd"),
    ("MALLATMILLENIA/Orlando", ['orlando police crimes type:"Feature Service"',
                                'OPD crimes orlando type:"Feature Service"'],
     28.4858595, -81.4320188, "orlando"),
    ("CASTLETON/Indianapolis", ['indianapolis UCR crime type:"Feature Service"',
                                'IMPD incidents type:"Feature Service"'],
     39.9092273, -86.065379, "indy|indianapolis|marion"),
    ("WOODLANDHILLS/Tulsa", ['tulsa police incidents type:"Feature Service"',
                             'tulsa crime type:"Feature Service"'],
     36.0637737, -95.8818853, "tulsa"),
    ("PENNSQUARE/OKC", ['oklahoma city police incidents type:"Feature Service"',
                        'OKC crime type:"Feature Service"'],
     35.5248002, -97.5444491, "okc|oklahoma"),
    ("CLEARFORK/Fort Worth", ['fort worth police crime type:"Feature Service"'],
     32.7101703, -97.4005879, "fortworth|fort worth|fwpd"),
    ("CIELOVISTA/El Paso", ['el paso police crime type:"Feature Service"'],
     31.7737267, -106.38104, "elpaso|el paso"),
    ("TYRONE/St. Petersburg", ['st petersburg police crime type:"Feature Service"'],
     27.7937118, -82.7331687, "stpete|petersburg"),
    ("WESTTOWN/Knoxville", ['knoxville police crime type:"Feature Service"'],
     35.9244853, -84.0383972, "knox"),
    ("BATTLEFIELD/Springfield MO", ['springfield missouri crime type:"Feature Service"',
                                    'greene county missouri crime type:"Feature Service"'],
     37.16282, -93.26571, "springfield|greene|sgf"),
    ("TACOMAMALL/Tacoma", ['tacoma crime incidents type:"Feature Service"'],
     47.2161436, -122.4682104, "tacoma"),
    ("HAYWOOD/Greenville SC", ['greenville police crime type:"Feature Service"'],
     34.8490186, -82.3340927, "greenville"),
    ("EMPIRE/Sioux Falls", ['sioux falls police type:"Feature Service"'],
     43.5103141, -96.7757826, "sioux"),
    ("MEADOWOOD/Reno", ['reno police crime type:"Feature Service"'],
     39.4715327, -119.7830083, "reno|washoe"),
    ("TOWNBOCARATON/Boca Raton", ['boca raton police type:"Feature Service"'],
     26.364967, -80.1325963, "boca"),
    ("CORALSQR/Coral Springs", ['coral springs police type:"Feature Service"'],
     26.2410392, -80.2492081, "coral"),
    ("SAWGRASS/Sunrise FL", ['sunrise florida police type:"Feature Service"'],
     26.1518472, -80.3218487, "sunrise"),
]

SOCRATA = [
    ("WOLFCHASE/Memphis", "data.memphistn.gov", "police incidents", 35.200892, -89.7877063),
    ("CITYCREEK/SLC", "opendata.utah.gov", "salt lake police case", 40.768357, -111.8917453),
    ("PENTAGONCITY/Arlington VA", "data.arlingtonva.us", "police incident", 38.8631596, -77.0612117),
]

GENERIC_OFFICIAL = ("city", "county", "gov", "gis", "police", "pd_", "opendata")


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


def probe_layer(url, lat, lon, radius=1600, cap=25):
    meta = jsafe(get(url, {"f": "json"})) or {}
    if "error" in meta:
        print(f"    !! layer error: {meta['error']}")
        return False
    fields = [(f["name"], f["type"].replace("esriFieldType", ""))
              for f in meta.get("fields", [])]
    print(f"    layer: {meta.get('name')} fields({len(fields)}): {fields[:cap]}")
    q = {"f": "json", "where": "1=1", "geometry": f"{lon},{lat}",
         "geometryType": "esriGeometryPoint", "inSR": 4326,
         "spatialRel": "esriSpatialRelIntersects", "distance": radius,
         "units": "esriSRUnit_Meter", "outFields": "*", "returnGeometry": "false",
         "resultRecordCount": 1}
    data = jsafe(get(url.rstrip("/") + "/query", q)) or {}
    if "error" in data:
        print(f"    !! query error: {data['error']}")
        return False
    feats = data.get("features", [])
    print(f"    radius query OK — {len(feats)} feature(s)")
    if feats:
        print(f"    sample: {json.dumps(feats[0].get('attributes', {}), default=str)[:280]}")
    return True


def arcgis_city(label, queries, lat, lon, own_hint):
    section(f"ARCGIS: {label}")
    seen = set()
    hints = tuple(own_hint.split("|")) + GENERIC_OFFICIAL
    probed = 0
    for q in queries:
        data = jsafe(get("https://www.arcgis.com/sharing/rest/search",
                         {"f": "json", "q": q, "num": 6})) or {}
        for it in data.get("results", []):
            url = it.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            owner = (it.get("owner") or "").lower()
            title = (it.get("title") or "")
            print(f"  - {title!r} owner={it.get('owner')} url={url}")
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


def socrata_city(label, domain, terms, lat, lon):
    section(f"SOCRATA: {label} ({domain})")
    data = jsafe(get("https://api.us.socrata.com/api/catalog/v1",
                     {"domains": domain, "q": terms, "only": "datasets", "limit": 5})) or {}
    for it in data.get("results", []):
        res = it.get("resource", {})
        print(f"  - {res.get('name')!r} id={res.get('id')} updated={res.get('updatedAt')}")
    for it in data.get("results", [])[:2]:
        ds = it.get("resource", {}).get("id")
        if not ds:
            continue
        cols = jsafe(get(f"https://{domain}/api/views/{ds}/columns.json")) or []
        pairs = [(c.get("fieldName"), c.get("dataTypeName")) for c in cols]
        geo = [n for n, _ in pairs if n and any(k in (n or "").lower()
                                               for k in ("lat", "lon", "point", "location", "geo"))]
        print(f"    [{ds}] geo={geo}")
        print(f"    [{ds}] cols: {pairs}")


def main():
    section("HOUSTON: enumerate NIBRS_Recent_Crime_Reports layers")
    root = ("https://mycity2.houstontx.gov/pubgis02/rest/services/HPD/"
            "NIBRS_Recent_Crime_Reports/FeatureServer")
    meta = jsafe(get(root, {"f": "json"})) or {}
    layers = [(la.get("id"), la.get("name")) for la in (meta.get("layers") or [])]
    print(f"  layers: {layers}")
    for lid, lname in layers[:6]:
        print(f"  -- layer {lid}: {lname}")
        probe_layer(f"{root}/{lid}", 29.739343, -95.4641184, radius=2500, cap=18)

    for label, queries, lat, lon, hint in ARCGIS:
        arcgis_city(label, queries, lat, lon, hint)

    for label, domain, terms, lat, lon in SOCRATA:
        socrata_city(label, domain, terms, lat, lon)

    print("\nProbe complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
