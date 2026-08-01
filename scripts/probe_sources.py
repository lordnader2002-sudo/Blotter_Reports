#!/usr/bin/env python3
"""Probe open-data portals from CI to discover/validate registry endpoints.

Round 11 — recon for the deferred-machinery builds:
- CKAN: Boston (Copley + Chestnut Hill) and San Diego (Fashion Valley) —
  package/resource discovery, datastore field lists, and whether
  datastore_search_sql is enabled (range queries need it).
- Socrata columns for Norfolk + Honolulu — exact address/date/type fields to
  drive the geocoding adapter.
- Atlanta: scrape the download pages for real COBRA file URLs (CSV adapter).
"""

from __future__ import annotations

import json
import re
import sys

import requests

S = requests.Session()
S.headers["User-Agent"] = "blotter-reports-probe/0.11"


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


def ckan_probe(domain, query):
    section(f"CKAN: {domain} (q={query!r})")
    data = jsafe(get(f"https://{domain}/api/3/action/package_search",
                     {"q": query, "rows": 5}))
    if not data or not data.get("success"):
        print("  !! package_search failed or not CKAN")
        return
    for pkg in data["result"]["results"]:
        print(f"  package: {pkg.get('name')!r} title={pkg.get('title')!r}")
        for res in pkg.get("resources", [])[:8]:
            print(f"    - res id={res.get('id')} fmt={res.get('format')} "
                  f"datastore={res.get('datastore_active')} name={res.get('name')!r}")
    # Probe the first datastore-active resource of the most relevant package.
    for pkg in data["result"]["results"]:
        if not any(k in (pkg.get("title") or "").lower() for k in ("crime", "incident", "police")):
            continue
        for res in pkg.get("resources", []):
            if not res.get("datastore_active"):
                continue
            rid = res["id"]
            ds = jsafe(get(f"https://{domain}/api/3/action/datastore_search",
                           {"resource_id": rid, "limit": 1}))
            if ds and ds.get("success"):
                fields = [(f.get("id"), f.get("type")) for f in ds["result"].get("fields", [])]
                print(f"  [{rid}] fields: {fields}")
                recs = ds["result"].get("records", [])
                if recs:
                    print(f"  [{rid}] sample: {json.dumps(recs[0], default=str)[:350]}")
            sql = jsafe(get(f"https://{domain}/api/3/action/datastore_search_sql",
                            {"sql": f'SELECT COUNT(*) FROM "{rid}"'}))
            ok = bool(sql and sql.get("success"))
            print(f"  [{rid}] datastore_search_sql enabled: {ok}"
                  + ("" if ok else f" ({json.dumps((sql or {}).get('error', {}), default=str)[:150]})"))
            return


def socrata_columns(label, domain, terms):
    section(f"SOCRATA columns: {label} ({domain})")
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
        print(f"    [{ds}] cols: {pairs}")
        r = get(f"https://{domain}/resource/{ds}.json", {"$limit": 1})
        rows = jsafe(r) if r is not None and r.status_code == 200 else None
        if rows:
            print(f"    [{ds}] sample: {json.dumps(rows[0], default=str)[:350]}")


def atlanta_links():
    section("ATLANTA: scrape download pages for COBRA file URLs")
    pages = [
        "https://opendata-1-atlantapd.hub.arcgis.com/pages/crime-data-download",
        "https://opendata.atlantapd.org/",
        "https://opendataportal.azurewebsites.us/Crimedata/Default.aspx",
    ]
    for page in pages:
        print(f"  --- {page}")
        r = get(page)
        if r is None or r.status_code != 200:
            print(f"    HTTP {getattr(r, 'status_code', 'n/a')}")
            continue
        links = re.findall(r'href=["\']([^"\']+\.(?:csv|zip|xlsx)[^"\']*)["\']',
                           r.text, flags=re.I)
        uniq = list(dict.fromkeys(links))[:20]
        if uniq:
            for u in uniq:
                print(f"    file: {u}")
        else:
            print(f"    no file links; page snippet: {' '.join(r.text[:250].split())}")


def main():
    ckan_probe("data.boston.gov", "crime incident reports")
    ckan_probe("data.sandiego.gov", "police calls for service")
    socrata_columns("NORFOLKPO/Norfolk", "data.norfolk.gov", "police incidents")
    socrata_columns("INTLMARKET/Honolulu", "data.honolulu.gov", "crime incidents")
    atlanta_links()
    print("\nProbe complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
