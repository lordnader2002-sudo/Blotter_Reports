"""CSV-download adapter: static per-year files (e.g. San Diego's seshat bucket).

The file is streamed and date-filtered during parse; when the recency window
straddles New Year, both year files are fetched. These feeds carry no
coordinates — pair with geocode_hint (+ geocode_priority_streets to keep the
geocoding budget on the mall's neighborhood instead of the whole city).
"""

from __future__ import annotations

import csv
from datetime import datetime

import requests

from ..normalize import parse_datetime
from ..schema import OTHER, NormalizedIncident
from .base import FetchQuery, RawFetchResult, SourceAdapter, SourceError

# Some file hosts (S3 fronts) reject non-browser user agents.
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


class CsvAdapter(SourceAdapter):
    type_name = "csv"

    def _urls(self, query: FetchQuery) -> list[str]:
        base = self.entry.base_url
        if "{year}" not in base:
            return [base]
        since_year = int(query.since_iso[:4])
        this_year = datetime.now().year  # noqa: DTZ005 - year granularity only
        years = sorted({since_year, this_year})
        return [base.format(year=y) for y in years]

    def fetch(self, query: FetchQuery) -> RawFetchResult:
        e = self.entry
        since_day = query.since_iso[:10]
        records: list[dict] = []
        truncated = False
        for url in self._urls(query):
            try:
                resp = self.http.session.get(
                    url, headers={"User-Agent": _UA}, stream=True, timeout=(10, 120))
                if resp.status_code >= 400:
                    raise SourceError(
                        f"CSV fetch failed for {url}: HTTP {resp.status_code}")
                # S3-style hosts often omit charset -> encoding is None and
                # iter_lines would yield BYTES, crashing csv. Force a default.
                resp.encoding = resp.encoding or "utf-8"
                reader = csv.reader(resp.iter_lines(decode_unicode=True))
                header = next(reader, None)
                if not header or e.date_field not in header:
                    raise SourceError(
                        f"CSV {url}: missing {e.date_field!r} in header {header!r:.120}")
                idx = {name: i for i, name in enumerate(header)}
                date_i = idx[e.date_field]
                # Priority streets prune citywide noise DURING the stream: only
                # rows near the mall survive, so the row cap never truncates on
                # far-away records and the geocoder sees only relevant addresses.
                streets = [s.upper() for s in
                           getattr(e, "geocode_priority_streets", [])]
                addr_is = [idx[f.strip()] for f in (e.address_field or "").split(",")
                           if f.strip() in idx]
                for row in reader:
                    if len(row) <= date_i:
                        continue
                    # "YYYY-MM-DD ..." string compare on the date part.
                    if row[date_i][:10] < since_day:
                        continue
                    if streets:
                        addr = " ".join(row[i] for i in addr_is if i < len(row)).upper()
                        if not any(s in addr for s in streets):
                            continue
                    records.append({name: row[i] if i < len(row) else ""
                                    for name, i in idx.items()})
                    if len(records) >= query.limit:
                        truncated = True
                        break
            except requests.RequestException as ex:
                raise SourceError(f"CSV fetch failed for {url}: {ex}") from ex
            except (csv.Error, UnicodeDecodeError) as ex:
                raise SourceError(f"CSV parse failed for {url}: {ex}") from ex
            if truncated:
                break
        return RawFetchResult(
            records=records,
            source_id=self.source_id,
            fetched_count=len(records),
            truncated=truncated,
        )

    def to_normalized(self, result: RawFetchResult) -> list[NormalizedIncident]:
        e = self.entry
        addr_fields = [f.strip() for f in (e.address_field or "").split(",") if f.strip()]

        def build_address(row: dict) -> str | None:
            parts = [str(row.get(f)).strip() for f in addr_fields
                     if row.get(f) not in (None, "")]
            return " ".join(parts) or None if parts else None

        out: list[NormalizedIncident] = []
        for row in result.records:
            out.append(
                NormalizedIncident(
                    property_id=e.property_id,
                    source_id=self.source_id,
                    incident_id=(
                        str(row.get(e.incident_id_field)) if e.incident_id_field else None
                    ),
                    occurred_at=parse_datetime(row.get(e.date_field)),
                    crime_type=row.get(e.crime_type_field),
                    crime_category=OTHER,
                    description=row.get(e.description_field) if e.description_field else None,
                    address=build_address(row),
                    lat=None,
                    lon=None,
                    raw=row,
                )
            )
        return out

    @property
    def source_id(self) -> str:
        return f"{self.entry.property_id}:{self.entry.name or 'csv'}"
