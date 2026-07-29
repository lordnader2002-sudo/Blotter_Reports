"""Optional OpenPoliceData adapter (behind the `opd` extra).

OpenPoliceData mostly exposes traffic-stops / use-of-force / complaints rather than
general blotter incidents, so it is a best-effort SECONDARY source. It is only imported
when a registry entry uses ``type: opendata`` and the library is installed.

Registry fields reused here:
  base_url        -> OPD source name (e.g. "Virginia")
  dataset_id      -> OPD table type (e.g. "STOPS")
  date_field      -> date column in the returned table
  crime_type_field, point_field (lat), point_field_lon (lon), address_field, incident_id_field
"""

from __future__ import annotations

from ..geo import bounding_box
from ..normalize import parse_datetime, to_float
from ..schema import OTHER, NormalizedIncident
from .base import FetchQuery, RawFetchResult, SourceAdapter, SourceError


class OpenPoliceDataAdapter(SourceAdapter):
    type_name = "opendata"

    def fetch(self, query: FetchQuery) -> RawFetchResult:
        try:
            import openpolicedata as opd
        except ImportError as ex:  # pragma: no cover - optional dependency
            raise SourceError("openpolicedata not installed (pip install '.[opd]')") from ex

        e = self.entry
        try:
            src = opd.Source(e.base_url)
            table = src.load_from_url(year="latest", table_type=e.dataset_id)
            df = table.table
        except Exception as ex:
            raise SourceError(f"OpenPoliceData load failed for {e.base_url}: {ex}") from ex

        # OPD has no geo query, so bound the box client-side then exact-filter downstream.
        records = df.to_dict("records") if df is not None else []
        if e.point_field and e.point_field_lon:
            min_lat, min_lon, max_lat, max_lon = bounding_box(
                query.lat, query.lon, query.radius_m
            )
            kept = []
            for row in records:
                lat, lon = to_float(row.get(e.point_field)), to_float(row.get(e.point_field_lon))
                if lat is None or lon is None:
                    continue
                if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                    kept.append(row)
            records = kept
        return RawFetchResult(records=records, source_id=self.source_id, fetched_count=len(records))

    def to_normalized(self, result: RawFetchResult) -> list[NormalizedIncident]:
        e = self.entry
        out: list[NormalizedIncident] = []
        for row in result.records:
            out.append(
                NormalizedIncident(
                    property_id=e.property_id,
                    source_id=self.source_id,
                    incident_id=str(row.get(e.incident_id_field)) if e.incident_id_field else None,
                    occurred_at=parse_datetime(row.get(e.date_field)),
                    crime_type=row.get(e.crime_type_field),
                    crime_category=OTHER,
                    description=row.get(e.description_field) if e.description_field else None,
                    address=row.get(e.address_field) if e.address_field else None,
                    lat=to_float(row.get(e.point_field)) if e.point_field else None,
                    lon=to_float(row.get(e.point_field_lon)) if e.point_field_lon else None,
                    raw=row,
                )
            )
        return out

    @property
    def source_id(self) -> str:
        return f"{self.entry.property_id}:{self.entry.base_url}:{self.entry.dataset_id}"
