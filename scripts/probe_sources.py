#!/usr/bin/env python3
"""Probe open-data portals from CI to discover/validate registry endpoints.

Round 14 — WAVE-4: candidates reopened by the geocoding + CSV capabilities
(address-only feeds and file publishers now qualify):
- Socrata domains never probed: Bloomington IN, Nassau County NY, Westchester
  County NY, City of Las Vegas.
- LVMPD open-data pages scraped for downloadable incident files (5-property
  Vegas cluster rides on this).
- Atlanta: ArcGIS Online ITEM search for downloadable COBRA files (the Hub
  DCAT hid file distributions; items may still exist in the org).
"""

from __future__ import annotations

import json
import re
import sys

import requests

S = requests.Session()
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

SOCRATA = [
    ("COLLEGE/Bloomington IN", "data.bloomington.in.gov", "police"),
    ("ROOSEVELT/Nassau County NY", "data.nassaucountyny.gov", "crime police"),
    ("WESTCHESTER/Westchester Co NY", "data.westchestergov.com", "police incident"),
    ("VEGAS cluster/City of Las Vegas", "opendata.lasvegasnevada.gov", "crime police"),
]


def section(title):
    print(f"\n{'=' * 70}\n== {title}\n{'=' * 70}")


def get(url, params=None, timeout=45, ua=None, rng=None):
    headers = {"User-Agent": ua or "blotter-reports-probe/0.14"}
    if rng:
        headers["Range"] = rng
    try:
        return S.get(url, params=params or {}, timeout=timeout, headers=headers)
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


def socrata_domain(label, domain, terms):
    section(f"SOCRATA: {label} ({domain})")
    data = jsafe(get("https://api.us.socrata.com/api/catalog/v1",
                     {"domains": domain, "q": terms, "only": "datasets", "limit": 6}))
    results = (data or {}).get("results", [])
    if not results:
        # Discovery can be flaky/miss small domains — fall back to the domain itself.
        data = jsafe(get(f"https://{domain}/api/search/views.json",
                         {"q": terms.split()[0], "limit": 6}))
        for v in (data or {}).get("results", [])[:6]:
            view = v.get("view", {})
            print(f"  - (legacy) {view.get('name')!r} id={view.get('id')} "
                  f"updated={view.get('rowsUpdatedAt')}")
            results.append({"resource": {"id": view.get("id"), "name": view.get("name")}})
    else:
        for it in results:
            res = it.get("resource", {})
            print(f"  - {res.get('name')!r} id={res.get('id')} updated={res.get('updatedAt')}")
    for it in results[:3]:
        ds = it.get("resource", {}).get("id")
        name = (it.get("resource", {}).get("name") or "").lower()
        if not ds or not any(k in name for k in ("crime", "police", "incident", "offense", "call")):
            continue
        cols = jsafe(get(f"https://{domain}/api/views/{ds}/columns.json")) or []
        pairs = [(c.get("fieldName"), c.get("dataTypeName")) for c in cols]
        print(f"    [{ds}] cols: {pairs}")
        r = get(f"https://{domain}/resource/{ds}.json", {"$limit": 1, "$order": ":id DESC"})
        rows = jsafe(r) if r is not None and r.status_code == 200 else None
        if rows:
            print(f"    [{ds}] sample: {json.dumps(rows[0], default=str)[:320]}")


def lvmpd_files():
    section("LVMPD: scrape open-data pages for incident files")
    pages = [
        "https://www.lvmpd.com/en-us/Pages/OpenDataInitiative.aspx",
        "https://www.lvmpd.com/opendata",
        "https://www.lvmpd.com/en-us/Pages/InternetCrimeMapping.aspx",
    ]
    for page in pages:
        r = get(page, ua=BROWSER_UA)
        code = getattr(r, "status_code", "n/a")
        print(f"  --- {page} -> HTTP {code}")
        if r is None or code != 200:
            continue
        links = re.findall(r'href=["\']([^"\']+\.(?:csv|xlsx|zip|json)[^"\']*)["\']',
                           r.text, flags=re.I)
        for u in list(dict.fromkeys(links))[:15]:
            print(f"      file: {u}")


def atlanta_items():
    section("ATLANTA: ArcGIS Online item search for COBRA files")
    for q in ('cobra atlanta', 'atlanta police crime type:CSV',
              'title:cobra type:CSV'):
        data = jsafe(get("https://www.arcgis.com/sharing/rest/search",
                         {"f": "json", "q": q, "num": 8}))
        print(f"  q={q!r}:")
        for it in (data or {}).get("results", []):
            print(f"  - [{it.get('type')}] {it.get('title')!r} owner={it.get('owner')} "
                  f"id={it.get('id')} modified={it.get('modified')}")
        # Probe the first CSV-typed item's data endpoint.
        for it in (data or {}).get("results", []):
            if it.get("type") == "CSV":
                u = f"https://www.arcgis.com/sharing/rest/content/items/{it['id']}/data"
                r = get(u, rng="bytes=0-2000")
                code = getattr(r, "status_code", "n/a")
                print(f"    data probe {u} -> HTTP {code}")
                if r is not None and code in (200, 206):
                    for ln in r.text.splitlines()[:2]:
                        print(f"      {ln[:300]}")
                break


def main():
    for label, domain, terms in SOCRATA:
        socrata_domain(label, domain, terms)
    lvmpd_files()
    atlanta_items()
    print("\nProbe complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
