#!/usr/bin/env python3
"""Probe open-data portals from CI to discover/validate registry endpoints.

The dev sandbox cannot reach the portals (egress-blocked), so this runs in a GitHub
runner (see .github/workflows/probe-sources.yml) and prints everything needed to fix
config/registry.yaml: real ArcGIS FeatureServer URLs + field lists, and live Socrata
query validation with error bodies. Read the workflow logs for the results.
"""

from __future__ import annotations

import json
import sys

import requests

S = requests.Session()
S.headers["User-Agent"] = "blotter-reports-probe/0.1"
ARCGIS_SEARCH = "https://www.arcgis.com/sharing/rest/search"
ARCGIS_ITEM = "https://www.arcgis.com/sharing/rest/content/items/{id}"


def section(title):
    print(f"\n{'=' * 70}\n== {title}\n{'=' * 70}")


def get(url, params=None, timeout=30):
    try:
        r = S.get(url, params=params or {}, timeout=timeout)
        return r
    except requests.RequestException as ex:
        print(f"  !! request failed: {ex}")
        return None


def arcgis_search(query, num=8):
    r = get(ARCGIS_SEARCH, {"f": "json", "q": query, "num": num})
    if r is None:
        return []
    try:
        results = r.json().get("results", [])
    except ValueError:
        print(f"  !! non-JSON from search: {r.text[:200]}")
        return []
    for it in results:
        print(f"  - [{it.get('type')}] {it.get('title')!r} owner={it.get('owner')}")
        print(f"      id={it.get('id')}  url={it.get('url')}")
    return results


def probe_layer(url):
    """Print layer metadata + field names for a FeatureServer layer url."""
    if not url:
        return
    if not url.rstrip("/").split("/")[-1].isdigit():
        # Service root: list layers first, then probe layer 0.
        r = get(url, {"f": "json"})
        if r is not None:
            try:
                layers = r.json().get("layers", [])
                print(f"    layers: {[(l.get('id'), l.get('name')) for l in layers]}")
            except ValueError:
                print(f"    !! non-JSON service root: {r.text[:150]}")
        url = url.rstrip("/") + "/0"
    r = get(url, {"f": "json"})
    if r is None:
        return
    try:
        meta = r.json()
    except ValueError:
        print(f"    !! non-JSON layer meta: {r.text[:150]}")
        return
    if "error" in meta:
        print(f"    !! layer error: {meta['error']}")
        return
    fields = [(f["name"], f["type"].replace("esriFieldType", "")) for f in meta.get("fields", [])]
    print(f"    layer: {meta.get('name')}  maxRecordCount={meta.get('maxRecordCount')}")
    print(f"    fields: {fields}")


def probe_arcgis_query(layer_url, lat, lon, date_field=None):
    """Run a live radius query to prove the endpoint + geometry params work."""
    params = {
        "f": "json", "where": "1=1",
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects", "distance": 1500, "units": "esriSRUnit_Meter",
        "outFields": "*", "returnGeometry": "false", "resultRecordCount": 2,
    }
    r = get(layer_url.rstrip("/") + "/query", params)
    if r is None:
        return
    try:
        data = r.json()
    except ValueError:
        print(f"    !! non-JSON query response: {r.text[:150]}")
        return
    if "error" in data:
        print(f"    !! query error: {data['error']}")
        return
    feats = data.get("features", [])
    print(f"    query OK — {len(feats)} sample feature(s)")
    if feats:
        print(f"    sample attrs: {json.dumps(feats[0].get('attributes', {}), default=str)[:500]}")


def probe_socrata(domain, dataset, where=None, label=""):
    base = f"https://{domain}/resource/{dataset}.json"
    r = get(base, {"$limit": 1})
    if r is None:
        return
    print(f"  [{label}] no-filter probe: HTTP {r.status_code}")
    if r.status_code != 200:
        print(f"    body: {' '.join(r.text[:250].split())}")
        return
    try:
        rows = r.json()
        if rows:
            print(f"    fields: {sorted(rows[0].keys())}")
    except ValueError:
        print(f"    !! non-JSON (portal migrated?): {' '.join(r.text[:200].split())}")
        return
    if where:
        r2 = get(base, {"$where": where, "$limit": 2})
        status = r2.status_code if r2 is not None else "n/a"
        print(f"    filtered probe [{where}]: HTTP {status}")
        if r2 is not None and r2.status_code != 200:
            print(f"    error body: {' '.join(r2.text[:300].split())}")
        elif r2 is not None:
            try:
                print(f"    -> {len(r2.json())} row(s)")
            except ValueError:
                print(f"    !! non-JSON: {r2.text[:150]}")


def main():
    since = "2026-06-29T00:00:00"  # naive UTC — the format the pipeline now emits

    section("SOCRATA: LA / Beverly Center (2nrs-mtv8)")
    probe_socrata("data.lacity.org", "2nrs-mtv8", label="LA",
                  where=f"lat between 34.066 and 34.084 AND lon between -118.389 and -118.366 "
                        f"AND date_occ > '{since}'")

    section("SOCRATA: Austin / The Domain (fdj4-gpfu)")
    probe_socrata("data.austintexas.gov", "fdj4-gpfu", label="Austin",
                  where=f"latitude between 30.392 and 30.411 AND longitude between -97.737 and -97.716 "
                        f"AND occ_date > '{since}'")

    section("SOCRATA: Seattle / Northgate (tazs-3rd5)")
    probe_socrata("data.seattle.gov", "tazs-3rd5", label="Seattle",
                  where=f"latitude between 47.699 and 47.717 AND longitude between -122.340 and -122.313 "
                        f"AND offense_start_datetime > '{since}'")

    section("SOCRATA (legacy check): Nashville 2u6v-ujjs — expected migrated to ArcGIS Hub")
    probe_socrata("data.nashville.gov", "2u6v-ujjs", label="Nashville-legacy")

    section("ARCGIS SEARCH: Nashville MNPD Incidents")
    results = arcgis_search('title:"Metro Nashville Police Department Incidents" type:"Feature Service"')
    for it in results[:2]:
        if it.get("url"):
            probe_layer(it["url"])
            probe_arcgis_query(it["url"].rstrip("/") + ("/0" if not it["url"].rstrip("/").endswith("/0") else ""),
                               36.2029647, -86.6922661)

    section("ARCGIS SEARCH: Denver crime (owner geospatialDenver)")
    results = arcgis_search('crime owner:geospatialDenver type:"Feature Service"')
    if not results:
        results = arcgis_search('title:Crime denver NIBRS type:"Feature Service"')
    for it in results[:3]:
        if it.get("url") and "crime" in (it.get("title") or "").lower():
            probe_layer(it["url"])
            probe_arcgis_query(it["url"].rstrip("/") + "/0", 39.7168661, -104.9527576)

    section("ARCGIS ITEM: Atlanta Crime Stats (2f68476999b74aa0b8dc9769822854d2)")
    r = get(ARCGIS_ITEM.format(id="2f68476999b74aa0b8dc9769822854d2"), {"f": "json"})
    if r is not None:
        try:
            item = r.json()
            print(f"  title={item.get('title')!r} type={item.get('type')} url={item.get('url')}")
            if item.get("url"):
                probe_layer(item["url"])
                probe_arcgis_query(item["url"].rstrip("/") + "/0", 33.8467259, -84.3624199)
        except ValueError:
            print(f"  !! non-JSON: {r.text[:200]}")

    section("ARCGIS SEARCH: Atlanta PD (owner:atlantapd)")
    results = arcgis_search('owner:atlantapd type:"Feature Service"')
    for it in results[:3]:
        if it.get("url"):
            probe_layer(it["url"])

    print("\nProbe complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
