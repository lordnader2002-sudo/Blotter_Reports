#!/usr/bin/env python3
"""Probe open-data portals from CI to discover/validate registry endpoints.

Round 3 targets the remaining unknowns: LA's replacement NIBRS dataset columns,
an Austin dataset that still has geo columns, Denver's actual layer id, and
Atlanta's full DCAT distribution URLs. Results are read from the workflow logs.
"""

from __future__ import annotations

import json
import sys

import requests

S = requests.Session()
S.headers["User-Agent"] = "blotter-reports-probe/0.3"


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
        print(f"  !! non-JSON (HTTP {r.status_code}): {' '.join(r.text[:200].split())}")
        return None


def socrata_columns(domain, dataset, label=""):
    data = jsafe(get(f"https://{domain}/api/views/{dataset}/columns.json"))
    if data:
        cols = [(c.get("fieldName"), c.get("dataTypeName")) for c in data]
        print(f"  [{label or dataset}] columns: {cols}")
        return dict(cols)
    return {}


def socrata_test(domain, dataset, where, label):
    r = get(f"https://{domain}/resource/{dataset}.json", {"$where": where, "$limit": 2})
    if r is None:
        return
    print(f"  [{label}] {where!r}: HTTP {r.status_code}")
    if r.status_code != 200:
        print(f"    error: {' '.join(r.text[:300].split())}")
    else:
        rows = jsafe(r)
        print(f"    -> {len(rows or [])} row(s)")
        if rows:
            print(f"    sample: {json.dumps(rows[0], default=str)[:400]}")


def probe_layer(url, lat=None, lon=None):
    meta = jsafe(get(url, {"f": "json"}))
    if not meta:
        return
    if "error" in meta:
        print(f"  !! layer error at {url}: {meta['error']}")
        return
    fields = [(f["name"], f["type"].replace("esriFieldType", "")) for f in meta.get("fields", [])]
    print(f"  layer: {meta.get('name')}  maxRecordCount={meta.get('maxRecordCount')}")
    print(f"  fields: {fields}")
    if lat is None:
        return
    q = {
        "f": "json", "where": "1=1",
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects", "distance": 1500, "units": "esriSRUnit_Meter",
        "outFields": "*", "returnGeometry": "false", "resultRecordCount": 2,
    }
    data = jsafe(get(url.rstrip("/") + "/query", q))
    if not data:
        return
    if "error" in data:
        print(f"  !! query error: {data['error']}")
        return
    feats = data.get("features", [])
    print(f"  radius query OK — {len(feats)} sample feature(s)")
    if feats:
        print(f"  sample attrs: {json.dumps(feats[0].get('attributes', {}), default=str)[:450]}")


def main():
    since = "2026-06-29T00:00:00"

    section("LA replacement: LAPD NIBRS Offenses 2026-present (k7nn-b2ep)")
    cols = socrata_columns("data.lacity.org", "k7nn-b2ep", "LA-NIBRS-2026")
    # Also check the 2024-2025 NIBRS dataset in case 2026 lacks geo columns.
    socrata_columns("data.lacity.org", "y8y3-fqfu", "LA-NIBRS-2024-25")
    # If geo columns are evident, run a live bbox test near Beverly Center.
    latf = next((c for c in cols if c and "lat" in c.lower()), None)
    lonf = next((c for c in cols if c and "lon" in c.lower()), None)
    datef = next((c for c in cols if c and ("date_occ" in c.lower() or "occ" in c.lower())), None)
    print(f"  guessed fields: lat={latf} lon={lonf} date={datef}")
    if latf and lonf and datef:
        socrata_test("data.lacity.org", "k7nn-b2ep",
                     f"{latf} between 34.066 and 34.084 AND {lonf} between -118.389 and -118.366 "
                     f"AND {datef} > '{since}'", "LA-NIBRS-test")

    section("Austin: find a crime dataset WITH geo columns")
    data = jsafe(get("https://api.us.socrata.com/api/catalog/v1",
                     {"domains": "data.austintexas.gov", "q": "crime", "only": "datasets",
                      "limit": 10}))
    ids = []
    for it in (data or {}).get("results", []):
        res = it.get("resource", {})
        print(f"  - {res.get('name')!r} id={res.get('id')} updated={res.get('updatedAt')}")
        ids.append((res.get("id"), res.get("name")))
    for ds_id, name in ids[:6]:
        cols = socrata_columns("data.austintexas.gov", ds_id, name)
        geo = [c for c in cols if c and any(k in c.lower() for k in ("lat", "lon", "point", "location"))]
        if geo:
            print(f"    ^^ HAS GEO: {geo}")

    section("Denver: list layers of ODC_CRIME_OFFENSES_P")
    meta = jsafe(get("https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/"
                     "ODC_CRIME_OFFENSES_P/FeatureServer", {"f": "json"}))
    if meta:
        layers = [(l.get("id"), l.get("name")) for l in (meta.get("layers") or [])]
        tables = [(t.get("id"), t.get("name")) for t in (meta.get("tables") or [])]
        print(f"  layers: {layers}  tables: {tables}")
        for lid, _ in (layers or tables)[:2]:
            probe_layer("https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/"
                        f"ODC_CRIME_OFFENSES_P/FeatureServer/{lid}", 39.7168661, -104.9527576)

    section("Atlanta: full DCAT distributions (all formats)")
    data = jsafe(get("https://atlanta-police-opendata-atlantapd.hub.arcgis.com/api/feed/dcat-us/1.1.json"))
    for ds in (data or {}).get("dataset", []):
        title = ds.get("title", "")
        if any(k in title.lower() for k in ("crime", "cobra", "incident", "offense", "download")):
            dists = [(d.get("format"), d.get("accessURL") or d.get("downloadURL"))
                     for d in ds.get("distribution", [])]
            print(f"  - {title!r}:")
            for fmt, u in dists:
                print(f"      [{fmt}] {u}")

    print("\nProbe complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
