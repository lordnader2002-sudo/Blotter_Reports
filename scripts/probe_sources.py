#!/usr/bin/env python3
"""Probe open-data portals from CI to discover/validate registry endpoints.

Round 12 — Honolulu direct + San Diego file recon:
- Honolulu: skip the (repeatedly timing-out) discovery API and hit
  data.honolulu.gov itself — columns + sample for the known crime dataset and
  the domain's legacy search for alternates.
- San Diego: the portal is static (S3) — read its DCAT data.json catalog for
  police entries and sample the CSV headers via Range requests.
"""

from __future__ import annotations

import json
import sys

import requests

S = requests.Session()
S.headers["User-Agent"] = "blotter-reports-probe/0.12"


def section(title):
    print(f"\n{'=' * 70}\n== {title}\n{'=' * 70}")


def get(url, params=None, timeout=45, headers=None):
    try:
        return S.get(url, params=params or {}, timeout=timeout, headers=headers or {})
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


def honolulu():
    section("HONOLULU direct: vg88-5rn5 columns + sample")
    cols = jsafe(get("https://data.honolulu.gov/api/views/vg88-5rn5/columns.json")) or []
    pairs = [(c.get("fieldName"), c.get("dataTypeName")) for c in cols]
    print(f"  [vg88-5rn5] cols: {pairs}")
    r = get("https://data.honolulu.gov/resource/vg88-5rn5.json",
            {"$limit": 2, "$order": ":id DESC"})
    rows = jsafe(r) if r is not None and r.status_code == 200 else None
    if rows:
        for row in rows:
            print(f"  sample: {json.dumps(row, default=str)[:350]}")
    elif r is not None:
        print(f"  !! resource probe HTTP {r.status_code}: {' '.join(r.text[:200].split())}")

    section("HONOLULU legacy search: other crime datasets")
    data = jsafe(get("https://data.honolulu.gov/api/search/views.json",
                     {"q": "crime", "limit": 8}))
    for v in (data or {}).get("results", [])[:8]:
        view = v.get("view", {})
        print(f"  - {view.get('name')!r} id={view.get('id')} "
              f"updated={view.get('rowsUpdatedAt')}")


def san_diego():
    section("SAN DIEGO: DCAT catalog (data.json)")
    data = jsafe(get("https://data.sandiego.gov/data.json"))
    hits = []
    for ds in (data or {}).get("dataset", []):
        title = ds.get("title") or ""
        if any(k in title.lower() for k in ("police", "crime", "calls for service", "arjis")):
            print(f"  - {title!r}")
            for d in ds.get("distribution", [])[:6]:
                u = d.get("downloadURL") or d.get("accessURL")
                print(f"      [{d.get('format')}] {u}")
                if u and u.lower().endswith(".csv"):
                    hits.append(u)
    if not hits:
        hits = [f"https://seshat.datasd.org/pd/pd_calls_for_service_{y}_datasd.csv"
                for y in (2026, 2025)]
        print("  (no catalog hits; falling back to guessed seshat URLs)")

    section("SAN DIEGO: CSV header samples (Range requests)")
    for u in hits[:4]:
        r = get(u, headers={"Range": "bytes=0-3000"})
        code = getattr(r, "status_code", "n/a")
        print(f"  --- {u} -> HTTP {code}")
        if r is not None and code in (200, 206):
            for ln in r.text.splitlines()[:3]:
                print(f"      {ln[:300]}")


def main():
    honolulu()
    san_diego()
    print("\nProbe complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
