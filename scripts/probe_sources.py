#!/usr/bin/env python3
"""Probe open-data portals from CI to discover/validate registry endpoints.

Round 4 — WAVE-1 EXPANSION discovery. For each candidate city, find its crime
dataset (Socrata discovery API or ArcGIS Online search), print authoritative
column lists, and where possible run a live radius test at the mall's
coordinates. Registry entries are authored from this output.
"""

from __future__ import annotations

import json
import sys

import requests

S = requests.Session()
S.headers["User-Agent"] = "blotter-reports-probe/0.4"

# (label, socrata domain, search terms, mall lat, mall lon)
SOCRATA_CANDIDATES = [
    ("WOLFCHASE/Memphis", "data.memphistn.gov", "police incidents", 35.200892, -89.7877063),
    ("NORFOLKPO/Norfolk", "data.norfolk.gov", "police incident", 36.8821267, -76.200199),
    ("INTLMARKET/Honolulu", "data.honolulu.gov", "crime incidents", 21.2779875, -157.826706),
    ("MALLATMILLENIA/Orlando", "data.cityoforlando.net", "OPD crimes", 28.4858595, -81.4320188),
    ("TACOMAMALL/Tacoma", "data.cityoftacoma.org", "crime", 47.2161436, -122.4682104),
    ("PENTAGONCITY/Arlington", "data.arlingtonva.us", "police incidents", 38.8631596, -77.0612117),
    ("CITYCREEK/SLC", "opendata.utah.gov", "salt lake city police cases", 40.768357, -111.8917453),
    ("CIELOVISTA/El Paso", "data.elpasotexas.gov", "crime", 31.7737267, -106.38104),
    ("CLEARFORK/Fort Worth", "data.fortworthtexas.gov", "crime", 32.7101703, -97.4005879),
]

# (label, arcgis.com search query, mall lat, mall lon)
ARCGIS_CANDIDATES = [
    ("SOUTHPARK/Charlotte CMPD", 'CMPD incidents type:"Feature Service"', 35.1518906, -80.8304507),
    ("DADELAND/Miami-Dade", 'miami dade police crime type:"Feature Service"', 25.6905361, -80.312504),
    ("CASTLETON/Indianapolis", 'indianapolis police incidents type:"Feature Service"', 39.9092273, -86.065379),
    ("WOODLANDHILLS/Tulsa", 'tulsa police incidents type:"Feature Service"', 36.0637737, -95.8818853),
    ("PENNSQUARE/OKC", 'oklahoma city crime incidents type:"Feature Service"', 35.5248002, -97.5444491),
    ("TOWNEEAST/Wichita", 'wichita crime incidents type:"Feature Service"', 37.6826997, -97.2474183),
    ("INTLPLAZA/Tampa", 'tampa police crime type:"Feature Service"', 27.9654551, -82.5204017),
    ("TYRONE/St. Petersburg", 'st petersburg police incidents type:"Feature Service"', 27.7937118, -82.7331687),
    ("ARZMILLS/Tempe", 'tempe crime type:"Feature Service"', 33.38327, -111.96453),
    ("ABQUP/Albuquerque", 'albuquerque police incidents type:"Feature Service"', 35.07893, -106.56826),
    ("HOUSTONGAL/Houston", 'houston police crime nibrs type:"Feature Service"', 29.739343, -95.4641184),
    ("WESTTOWN/Knoxville", 'knoxville police crime type:"Feature Service"', 35.9244853, -84.0383972),
    ("BATTLEFIELD/Springfield MO", 'springfield missouri police incidents type:"Feature Service"', 37.16282, -93.26571),
]

_OFFICIAL_HINTS = ("city", "county", "police", "gov", "gis", "cmpd", "miamidade", "tulsa",
                   "okc", "wichita", "tampa", "tempe", "cabq", "indy", "houston", "knox",
                   "springfield", "stpete")


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


def socrata_probe(label, domain, terms, lat, lon):
    section(f"SOCRATA: {label} ({domain})")
    data = jsafe(get("https://api.us.socrata.com/api/catalog/v1",
                     {"domains": domain, "q": terms, "only": "datasets", "limit": 6}))
    results = (data or {}).get("results", [])
    if not results:
        # Retry with a generic query before giving up on the domain.
        data = jsafe(get("https://api.us.socrata.com/api/catalog/v1",
                         {"domains": domain, "q": "crime", "only": "datasets", "limit": 6}))
        results = (data or {}).get("results", [])
    for it in results:
        res = it.get("resource", {})
        print(f"  - {res.get('name')!r} id={res.get('id')} updated={res.get('updatedAt')}")
    for it in results[:3]:
        ds = it.get("resource", {}).get("id")
        if not ds:
            continue
        cols = jsafe(get(f"https://{domain}/api/views/{ds}/columns.json")) or []
        pairs = [(c.get("fieldName"), c.get("dataTypeName")) for c in cols]
        geo = [n for n, _ in pairs if n and any(k in n.lower() for k in
                                               ("lat", "lon", "point", "location", "geo"))]
        datecols = [n for n, ty in pairs if ty == "calendar_date"]
        print(f"    [{ds}] geo={geo} dates={datecols}")
        print(f"    [{ds}] all: {pairs}")


def arcgis_probe(label, query, lat, lon):
    section(f"ARCGIS: {label}")
    data = jsafe(get("https://www.arcgis.com/sharing/rest/search",
                     {"f": "json", "q": query, "num": 8}))
    results = (data or {}).get("results", [])
    for it in results:
        print(f"  - {it.get('title')!r} owner={it.get('owner')} url={it.get('url')}")
    probed = 0
    for it in results:
        owner = (it.get("owner") or "").lower()
        url = it.get("url")
        if not url or probed >= 2:
            continue
        if not any(h in owner for h in _OFFICIAL_HINTS):
            continue
        probed += 1
        root = url.rstrip("/")
        meta = jsafe(get(root, {"f": "json"})) or {}
        layers = [(la.get("id"), la.get("name")) for la in (meta.get("layers") or [])]
        print(f"    service layers: {layers}")
        layer_id = layers[0][0] if layers else 0
        lmeta = jsafe(get(f"{root}/{layer_id}", {"f": "json"})) or {}
        if "error" in lmeta:
            print(f"    !! layer error: {lmeta['error']}")
            continue
        fields = [(f["name"], f["type"].replace("esriFieldType", ""))
                  for f in lmeta.get("fields", [])][:30]
        print(f"    layer {layer_id} fields: {fields}")
        q = {"f": "json", "where": "1=1", "geometry": f"{lon},{lat}",
             "geometryType": "esriGeometryPoint", "inSR": 4326,
             "spatialRel": "esriSpatialRelIntersects", "distance": 1500,
             "units": "esriSRUnit_Meter", "outFields": "*", "returnGeometry": "false",
             "resultRecordCount": 1}
        qd = jsafe(get(f"{root}/{layer_id}/query", q)) or {}
        if "error" in qd:
            print(f"    !! query error: {qd['error']}")
        else:
            feats = qd.get("features", [])
            print(f"    radius query OK — {len(feats)} feature(s) near mall")
            if feats:
                print(f"    sample: {json.dumps(feats[0].get('attributes', {}), default=str)[:300]}")


def main():
    for label, domain, terms, lat, lon in SOCRATA_CANDIDATES:
        socrata_probe(label, domain, terms, lat, lon)
    for label, query, lat, lon in ARCGIS_CANDIDATES:
        arcgis_probe(label, query, lat, lon)
    print("\nProbe complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
