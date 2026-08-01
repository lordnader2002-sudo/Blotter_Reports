"""CKAN adapter: datastore_search_sql range queries against CKAN portals.

Built for portals like Boston's, where the crime resource's columns are ALL
text — so lat/lon get `CAST(NULLIF(col,'') AS float8)` and the ISO-text date
column compares lexicographically (valid for ISO 8601 strings).

Registry mapping: base_url = portal root, dataset_id = datastore RESOURCE id,
point_field/point_field_lon = lat/lon columns, remaining fields as usual.
"""

from __future__ import annotations

import requests

from ..geo import bounding_box
from ..normalize import parse_datetime, to_float
from ..schema import OTHER, NormalizedIncident
from .base import FetchQuery, RawFetchResult, SourceAdapter, SourceError


class CkanAdapter(SourceAdapter):
    type_name = "ckan"

    def _sql(self, query: FetchQuery) -> str:
        # Boston's CKAN whitelists SQL functions (CAST/NULLIF are "not authorized"),
        # so filter with pure string comparisons: within a small box the integer
        # part of text lat/lon is constant, making lexicographic order match
        # numeric order (reversed for negatives -> sort the bounds). Empty and
        # zero placeholders fall outside the quoted interval. Exact radius is
        # re-checked numerically downstream.
        e = self.entry
        min_lat, min_lon, max_lat, max_lon = bounding_box(query.lat, query.lon, query.radius_m)
        lat_lo, lat_hi = sorted([str(min_lat), str(max_lat)])
        lon_lo, lon_hi = sorted([str(min_lon), str(max_lon)])
        return (
            f'SELECT * FROM "{e.dataset_id}" '
            f"WHERE \"{e.point_field}\" BETWEEN '{lat_lo}' AND '{lat_hi}' "
            f"AND \"{e.point_field_lon}\" BETWEEN '{lon_lo}' AND '{lon_hi}' "
            f"AND \"{e.date_field}\" >= '{query.since_iso}' "
            f"LIMIT {query.limit}"
        )

    def fetch(self, query: FetchQuery) -> RawFetchResult:
        e = self.entry
        if not (e.point_field and e.point_field_lon):
            raise SourceError(f"{e.name or e.dataset_id}: ckan requires point_field(+_lon)")
        url = f"{e.base_url.rstrip('/')}/api/3/action/datastore_search_sql"
        try:
            data = self.http.get_json(url, {"sql": self._sql(query)})
        except (requests.RequestException, ValueError) as ex:
            raise SourceError(f"CKAN fetch failed for {e.dataset_id}: {ex}") from ex
        if not isinstance(data, dict) or not data.get("success"):
            raise SourceError(f"CKAN error for {e.dataset_id}: "
                              f"{str(data.get('error') if isinstance(data, dict) else data)[:200]}")
        records = data.get("result", {}).get("records", [])
        return RawFetchResult(
            records=records,
            source_id=self.source_id,
            fetched_count=len(records),
            truncated=len(records) >= query.limit,
        )

    def to_normalized(self, result: RawFetchResult) -> list[NormalizedIncident]:
        e = self.entry
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
                    address=row.get(e.address_field) if e.address_field else None,
                    lat=to_float(row.get(e.point_field)),
                    lon=to_float(row.get(e.point_field_lon)),
                    raw={k: v for k, v in row.items() if k != "_full_text"},
                )
            )
        return out

    @property
    def source_id(self) -> str:
        return f"{self.entry.property_id}:{self.entry.dataset_id}"
