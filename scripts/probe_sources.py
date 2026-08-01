#!/usr/bin/env python3
"""Probe open-data portals from CI to discover/validate registry endpoints.

Round 9 — WAVE-3 discovery across the next tier of candidate jurisdictions:
county portals (Montgomery MD, Loudoun, Prince William, Anne Arundel, Gwinnett,
Orange FL, Sarasota, Escambia), multi-mall cities (Jacksonville), and
data-forward towns (Edina, Ann Arbor, Chandler, Round Rock, Lakewood CO,
Carlsbad, Palo Alto, Jersey City, Anchorage, N. Little Rock).
"""

from __future__ import annotations

import json
import sys

import requests

S = requests.Session()
S.headers["User-Agent"] = "blotter-reports-probe/0.9"

ARCGIS = [
    ("STJOHNS+AVENUES/Jacksonville", ['jacksonville sheriff crime type:"Feature Service"',
                                      'JSO calls for service type:"Feature Service"'],
     30.2568578, -81.5255258, "jax|jacksonville|coj|jso|duval"),
    ("MOFGEORGIA+SUGARLOAF/Gwinnett", ['gwinnett police crime type:"Feature Service"'],
     34.0662711, -83.9842746, "gwinnett"),
    ("LEESBURG/Loudoun", ['loudoun sheriff crime type:"Feature Service"'],
     39.1073788, -77.5382065, "loudoun"),
    ("POTOMACMILLS/Prince William", ['prince william police crime type:"Feature Service"'],
     38.6431929, -77.2965242, "pwc|princewilliam|prince william"),
    ("ARUNMILLS/Anne Arundel", ['anne arundel police crime type:"Feature Service"'],
     39.15722, -76.72491, "arundel|aaco"),
    ("FLORIDAMALL/Orange Co FL", ['orange county sheriff florida calls type:"Feature Service"',
                                  'ocso crime orlando type:"Feature Service"'],
     28.4467242, -81.3952717, "ocfl|orange|ocso"),
    ("UNIVERSITYTOWNCENTER/Sarasota", ['sarasota sheriff crime type:"Feature Service"'],
     27.3861364, -82.4519187, "sarasota"),
    ("CORDOVA/Pensacola-Escambia", ['escambia sheriff dispatch type:"Feature Service"',
                                    'pensacola police crime type:"Feature Service"'],
     30.4754844, -87.2080135, "escambia|pensacola|myescambia"),
    ("SOUTHDALE/Edina MN", ['edina police crime type:"Feature Service"'],
     44.8808535, -93.3253561, "edina"),
    ("BRIARWOOD/Ann Arbor", ['ann arbor police crime type:"Feature Service"'],
     42.2403, -83.74688, "a2gov|annarbor|ann arbor|washtenaw"),
    ("PHOENIXPO/Chandler AZ", ['chandler police crime type:"Feature Service"'],
     33.2869949, -111.9735812, "chandler"),
    ("ROUNDROCK/Round Rock TX", ['round rock police crime type:"Feature Service"'],
     30.5635656, -97.6902118, "roundrock|round rock"),
    ("COLORADO/Lakewood CO", ['lakewood colorado police crime type:"Feature Service"'],
     39.7317152, -105.1613776, "lakewood"),
    ("CARLSBAD/Carlsbad CA", ['carlsbad police crime type:"Feature Service"'],
     33.1229539, -117.3175914, "carlsbad"),
    ("STANFORDSC/Palo Alto", ['palo alto police crime type:"Feature Service"'],
     37.4434982, -122.1709939, "paloalto|palo alto"),
    ("ANC5Ave/Anchorage", ['anchorage police crime type:"Feature Service"'],
     61.21696, -149.88826, "anchorage|muni"),
    ("MCCAINMALL/N Little Rock", ['little rock police crime type:"Feature Service"'],
     34.7913644, -92.2282605, "littlerock|little rock|pulaski|nlr"),
]

SOCRATA = [
    ("CLARKSBURG/Montgomery Co MD", "data.montgomerycountymd.gov", "crime"),
    ("BRIARWOOD/Ann Arbor", "data.a2gov.org", "police"),
    ("NEWPORTCTR/Jersey City", "data.jerseycitynj.gov", "police"),
    ("STANFORDSC/Palo Alto", "data.cityofpaloalto.org", "police"),
]

GENERIC_OFFICIAL = ("city", "county", "gov", "gis", "police", "sheriff", "opendata", "pd")


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
        return
    fields = [(f["name"], f["type"].replace("esriFieldType", ""))
              for f in meta.get("fields", [])]
    print(f"    layer: {meta.get('name')} fields({len(fields)}): {fields[:cap]}")
    q = {"f": "json", "where": "1=1", "geometry": f"{lon},{lat}",
         "geometryType": "esriGeometryPoint", "inSR": 4326,
         "spatialRel": "esriSpatialRelIntersects", "distance": radius,
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
    hints = tuple(own_hint.split("|")) + GENERIC_OFFICIAL
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


def socrata_domain(label, domain, terms):
    section(f"SOCRATA: {label} ({domain})")
    data = jsafe(get("https://api.us.socrata.com/api/catalog/v1",
                     {"domains": domain, "q": terms, "only": "datasets", "limit": 5})) or {}
    results = data.get("results", [])
    for it in results:
        res = it.get("resource", {})
        print(f"  - {res.get('name')!r} id={res.get('id')} updated={res.get('updatedAt')}")
    for it in results[:2]:
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
    for label, queries, lat, lon, hint in ARCGIS:
        arcgis_city(label, queries, lat, lon, hint)
    for label, domain, terms in SOCRATA:
        socrata_domain(label, domain, terms)
    print("\nProbe complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
