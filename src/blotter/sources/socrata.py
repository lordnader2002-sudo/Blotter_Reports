"""Socrata adapter: SoQL geo + date queries against open-data crime datasets."""

from __future__ import annotations

import requests

from ..normalize import parse_datetime, socrata_point
from ..schema import OTHER, NormalizedIncident
from .base import FetchQuery, RawFetchResult, SourceAdapter, SourceError


class SocrataAdapter(SourceAdapter):
    type_name = "socrata"

    def _resource_url(self) -> str:
        return f"{self.entry.base_url.rstrip('/')}/resource/{self.entry.dataset_id}.json"

    def _build_where(self, query: FetchQuery) -> str:
        e = self.entry
        date_clause = f"{e.date_field} > '{query.since_iso}'"
        if e.point_field and not e.point_field_lon:
            # True point column: within_circle uses (field, lat, lon, radius_m).
            geo = f"within_circle({e.point_field}, {query.lat}, {query.lon}, {query.radius_m})"
        elif e.point_field and e.point_field_lon:
            # Separate lat/lon columns: bounding box (pipeline re-filters exactly).
            from ..geo import bounding_box

            min_lat, min_lon, max_lat, max_lon = bounding_box(
                query.lat, query.lon, query.radius_m
            )
            # Some datasets (e.g. Seattle) store lat/lon as text -> cast for BETWEEN.
            cast = "::number" if e.point_cast_number else ""
            geo = (
                f"{e.point_field}{cast} between {min_lat} and {max_lat} "
                f"AND {e.point_field_lon}{cast} between {min_lon} and {max_lon}"
            )
        else:
            raise SourceError(f"{e.name or e.dataset_id}: no point_field configured")
        return f"{geo} AND {date_clause}"

    def fetch(self, query: FetchQuery) -> RawFetchResult:
        params = {
            "$where": self._build_where(query),
            "$limit": query.limit,
            "$order": f"{self.entry.date_field} DESC",
        }
        try:
            records = self.http.get_json(self._resource_url(), params, socrata=True)
        except (requests.RequestException, ValueError) as ex:
            raise SourceError(f"Socrata fetch failed for {self.entry.dataset_id}: {ex}") from ex
        if not isinstance(records, list):
            raise SourceError(f"Unexpected Socrata response for {self.entry.dataset_id}")
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
            lat, lon = socrata_point(row, e.point_field, e.point_field_lon)
            out.append(
                NormalizedIncident(
                    property_id=e.property_id,
                    source_id=self.source_id,
                    incident_id=str(row.get(e.incident_id_field)) if e.incident_id_field else None,
                    occurred_at=parse_datetime(row.get(e.date_field)),
                    crime_type=row.get(e.crime_type_field),
                    crime_category=OTHER,  # mapped later by filters
                    description=row.get(e.description_field) if e.description_field else None,
                    address=row.get(e.address_field) if e.address_field else None,
                    lat=lat,
                    lon=lon,
                    raw=row,
                )
            )
        return out

    @property
    def source_id(self) -> str:
        return f"{self.entry.property_id}:{self.entry.dataset_id}"
