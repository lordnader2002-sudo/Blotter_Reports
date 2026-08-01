#!/usr/bin/env python3
"""Probe open-data portals from CI to discover/validate registry endpoints.

Round 10 — Ann Arbor retry only: the round-9 Socrata discovery call for
data.a2gov.org timed out. Retry the catalog search with a longer timeout and,
as a fallback, hit the domain's own catalog endpoint directly.
"""

from __future__ import annotations

import sys

import requests

S = requests.Session()
S.headers["User-Agent"] = "blotter-reports-probe/0.10"
DOMAIN = "data.a2gov.org"


def get(url, params=None, timeout=60):
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


def columns(ds):
    cols = jsafe(get(f"https://{DOMAIN}/api/views/{ds}/columns.json")) or []
    pairs = [(c.get("fieldName"), c.get("dataTypeName")) for c in cols]
    geo = [n for n, _ in pairs if n and any(k in (n or "").lower()
                                           for k in ("lat", "lon", "point", "location", "geo"))]
    print(f"  [{ds}] geo={geo}")
    print(f"  [{ds}] cols: {pairs}")


def main():
    print(f"== ANN ARBOR retry ({DOMAIN}) ==")
    for terms in ("police", "crime", "incident"):
        data = jsafe(get("https://api.us.socrata.com/api/catalog/v1",
                         {"domains": DOMAIN, "q": terms, "only": "datasets", "limit": 6}))
        results = (data or {}).get("results", [])
        print(f"  q={terms!r}: {len(results)} result(s)")
        for it in results:
            res = it.get("resource", {})
            print(f"  - {res.get('name')!r} id={res.get('id')} updated={res.get('updatedAt')}")
        if results:
            for it in results[:2]:
                ds = it.get("resource", {}).get("id")
                if ds:
                    columns(ds)
            break
    print("\nProbe complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
