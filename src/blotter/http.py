"""Shared HTTP client: one Session with timeouts, retry/backoff, and token injection.

Socrata accepts an optional ``X-App-Token`` (higher rate limits); it is read from
the ``SOCRATA_APP_TOKEN`` environment variable so the code also runs unauthenticated.
"""

from __future__ import annotations

import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_TIMEOUT = (10, 60)  # (connect, read) seconds


class HttpClient:
    def __init__(self, socrata_app_token: str | None = None, timeout=DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.socrata_app_token = socrata_app_token or os.environ.get("SOCRATA_APP_TOKEN")
        self.session = requests.Session()
        retry = Retry(
            total=4,
            backoff_factor=1.0,  # 1s, 2s, 4s, 8s
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({"User-Agent": "blotter-reports/0.1 (+ops analytics)"})

    def get_json(self, url: str, params: dict, *, socrata: bool = False):
        """GET a URL and return parsed JSON, raising with a response snippet on failure.

        Portals put the actual diagnosis in the body (Socrata 400s explain the SoQL
        error; migrated portals return HTML) — surfacing it makes CI logs actionable.
        """
        headers = {}
        if socrata and self.socrata_app_token:
            headers["X-App-Token"] = self.socrata_app_token
        resp = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
        if resp.status_code >= 400:
            snippet = " ".join(resp.text[:300].split())
            raise requests.HTTPError(
                f"HTTP {resp.status_code} for {resp.url} :: {snippet}", response=resp
            )
        try:
            return resp.json()
        except ValueError as ex:
            snippet = " ".join(resp.text[:200].split())
            raise ValueError(f"Non-JSON response from {resp.url} :: {snippet}") from ex
