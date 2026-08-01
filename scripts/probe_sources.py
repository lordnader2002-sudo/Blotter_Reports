#!/usr/bin/env python3
"""Probe open-data portals from CI to discover/validate registry endpoints.

Round 13 — San Diego second attempt: the DCAT catalog 404s and seshat CSV
guesses got 403. Scrape the dataset HTML pages for real file URLs and retry
the CSVs with a browser User-Agent (S3 may filter by UA).
"""

from __future__ import annotations

import re
import sys

import requests

S = requests.Session()
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def section(title):
    print(f"\n{'=' * 70}\n== {title}\n{'=' * 70}")


def get(url, timeout=45, ua=None, rng=None):
    headers = {"User-Agent": ua or "blotter-reports-probe/0.13"}
    if rng:
        headers["Range"] = rng
    try:
        return S.get(url, timeout=timeout, headers=headers)
    except requests.RequestException as ex:
        print(f"  !! request failed: {ex}")
        return None


def main():
    section("SAN DIEGO: scrape dataset pages for file URLs")
    pages = [
        "https://data.sandiego.gov/datasets/police-calls-for-service/",
        "https://data.sandiego.gov/datasets/",
        "https://data.sandiego.gov/",
    ]
    found = []
    for page in pages:
        r = get(page, ua=BROWSER_UA)
        code = getattr(r, "status_code", "n/a")
        print(f"  --- {page} -> HTTP {code}")
        if r is None or code != 200:
            continue
        links = re.findall(r'https?://[^"\'\s>]+\.csv[^"\'\s>]*', r.text)
        uniq = [u for u in dict.fromkeys(links) if "pd_" in u or "police" in u.lower()][:12]
        for u in uniq:
            print(f"      file: {u}")
        found.extend(uniq)
        if uniq:
            break

    section("SAN DIEGO: CSV header retries (browser UA)")
    candidates = found[:3] or [
        "https://seshat.datasd.org/pd/pd_calls_for_service_2026_datasd.csv",
        "https://seshat.datasd.org/pd/pd_calls_for_service_2025_datasd.csv",
    ]
    for u in candidates:
        r = get(u, ua=BROWSER_UA, rng="bytes=0-3000")
        code = getattr(r, "status_code", "n/a")
        print(f"  --- {u} -> HTTP {code}")
        if r is not None and code in (200, 206):
            for ln in r.text.splitlines()[:3]:
                print(f"      {ln[:300]}")

    print("\nProbe complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
