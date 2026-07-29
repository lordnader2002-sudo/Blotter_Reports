#!/usr/bin/env python3
"""Probe open-data portals from CI to discover/validate registry endpoints.

Round 2: authoritative Socrata column metadata, LA staleness + replacement search,
Denver's official FeatureServer, Atlanta via the Hub DCAT catalog. Results are read
from the workflow logs (see .github/workflows/probe-sources.yml).
"""

from __future__ import annotations

import json
import sys

import requests

S = requests.Session()
S.headers["User-Agent"] = "blotter-reports-probe/0.2"


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


def socrata_columns(domain, dataset):
    """Authoritative field names + types from the dataset metadata."""
    data = jsafe(get(f"https://{domain}/api/views/{dataset}/columns.json"))
    if data:
        cols = [(c.get("fieldName"), c.get("dataTypeName")) for c in data]
        print(f"  columns: {cols}")


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
        print(f"  !! layer error: {meta['error']}")
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
        "orderByFields": "1 DESC" if False else "",
    }
    q.pop("orderByFields")
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

    section("LA (2nrs-mtv8): staleness check + column metadata")
    r = get("https://data.lacity.org/resource/2nrs-mtv8.json",
            {"$select": "max(date_occ) as max_date, count(*) as n"})
    print(f"  max date probe: {jsafe(r)}")
    socrata_columns("data.lacity.org", "2nrs-mtv8")

    section("LA replacement search (Socrata discovery)")
    data = jsafe(get("https://api.us.socrata.com/api/catalog/v1",
                     {"domains": "data.lacity.org", "q": "crime", "only": "datasets", "limit": 8}))
    for it in (data or {}).get("results", []):
        res = it.get("resource", {})
        print(f"  - {res.get('name')!r} id={res.get('id')} updated={res.get('updatedAt')}")

    section("Austin (fdj4-gpfu): column metadata")
    socrata_columns("data.austintexas.gov", "fdj4-gpfu")

    section("Seattle (tazs-3rd5): column metadata + corrected test query")
    socrata_columns("data.seattle.gov", "tazs-3rd5")
    socrata_test("data.seattle.gov", "tazs-3rd5",
                 f"latitude between 47.699 and 47.717 AND longitude between -122.340 and -122.313 "
                 f"AND offense_date > '{since}'", "Seattle-fixed")

    section("Denver official: ODC_CRIME_OFFENSES_P")
    probe_layer("https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/"
                "ODC_CRIME_OFFENSES_P/FeatureServer/0", 39.7168661, -104.9527576)

    section("Nashville official (confirm layer 0 works)")
    probe_layer("https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/"
                "Metro_Nashville_Police_Department_Incidents_view/FeatureServer/0",
                36.2029647, -86.6922661)

    section("Atlanta: Hub DCAT catalog")
    for host in ("atlanta-police-opendata-atlantapd.hub.arcgis.com",
                 "opendata-1-atlantapd.hub.arcgis.com"):
        print(f"  --- {host}")
        data = jsafe(get(f"https://{host}/api/feed/dcat-us/1.1.json"))
        if not data:
            continue
        hits = []
        for ds in data.get("dataset", []):
            title = ds.get("title", "")
            if any(k in title.lower() for k in ("crime", "cobra", "incident", "offense")):
                urls = [d.get("accessURL") for d in ds.get("distribution", [])
                        if "rest/services" in (d.get("accessURL") or "")]
                print(f"  - {title!r}: {urls}")
                hits.extend(urls)
        if hits:
            layer = hits[0]
            if not layer.rstrip("/").split("/")[-1].isdigit():
                layer = layer.rstrip("/") + "/0"
            probe_layer(layer, 33.8467259, -84.3624199)
            break

    print("\nProbe complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
