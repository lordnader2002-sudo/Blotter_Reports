"""ArcGIS adapter: FeatureServer /query with point geometry + distance + date where."""

from __future__ import annotations

from datetime import UTC

import requests

from ..normalize import parse_datetime, to_float
from ..schema import OTHER, NormalizedIncident
from .base import FetchQuery, RawFetchResult, SourceAdapter, SourceError

_PAGE_SAFETY_CAP = 20  # max pages to walk, guards against runaway pagination


class ArcGISAdapter(SourceAdapter):
    type_name = "arcgis"

    def _query_url(self) -> str:
        base = (self.entry.layer or self.entry.base_url).rstrip("/")
        return f"{base}/query"

    def _date_clause(self, query: FetchQuery) -> str:
        e = self.entry
        if e.date_query_style == "epoch_ms":
            from datetime import datetime

            dt = datetime.fromisoformat(query.since_iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return f"{e.date_field} > {int(dt.timestamp() * 1000)}"
        # date_literal: ArcGIS understands DATE 'YYYY-MM-DD'
        return f"{e.date_field} > DATE '{query.since_iso[:10]}'"

    def _base_params(self, query: FetchQuery) -> dict:
        return {
            "f": "json",
            "where": self._date_clause(query),
            "geometry": f"{query.lon},{query.lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "distance": query.radius_m,
            "units": "esriSRUnit_Meter",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": 4326,
        }

    def fetch(self, query: FetchQuery) -> RawFetchResult:
        params = self._base_params(query)
        features: list[dict] = []
        truncated = False
        offset = 0
        for _ in range(_PAGE_SAFETY_CAP):
            params = {**params, "resultOffset": offset, "resultRecordCount": query.limit}
            try:
                data = self.http.get_json(self._query_url(), params)
            except (requests.RequestException, ValueError) as ex:
                raise SourceError(f"ArcGIS fetch failed for {self.entry.name}: {ex}") from ex
            if isinstance(data, dict) and "error" in data:
                raise SourceError(f"ArcGIS error for {self.entry.name}: {data['error']}")
            page = (data or {}).get("features", []) or []
            features.extend(page)
            if not data.get("exceededTransferLimit") or not page:
                break
            offset += len(page)
        else:
            truncated = True
        return RawFetchResult(
            records=features,
            source_id=self.source_id,
            fetched_count=len(features),
            truncated=truncated,
        )

    def to_normalized(self, result: RawFetchResult) -> list[NormalizedIncident]:
        e = self.entry
        # Some portals (e.g. Houston) split the address across several fields;
        # a comma-separated address_field joins the non-empty parts with spaces.
        addr_fields = [f.strip() for f in (e.address_field or "").split(",") if f.strip()]

        def build_address(attrs: dict) -> str | None:
            parts = [str(attrs.get(f)).strip() for f in addr_fields
                     if attrs.get(f) not in (None, "")]
            return " ".join(parts) or None if parts else None

        out: list[NormalizedIncident] = []
        for feat in result.records:
            attrs = feat.get("attributes", {}) or {}
            geom = feat.get("geometry", {}) or {}
            out.append(
                NormalizedIncident(
                    property_id=e.property_id,
                    source_id=self.source_id,
                    incident_id=(
                        str(attrs.get(e.incident_id_field)) if e.incident_id_field else None
                    ),
                    occurred_at=parse_datetime(attrs.get(e.date_field)),
                    crime_type=attrs.get(e.crime_type_field),
                    crime_category=OTHER,
                    description=attrs.get(e.description_field) if e.description_field else None,
                    address=build_address(attrs),
                    # Some layers return empty geometry but carry coordinate
                    # attributes — registry point_field(_lon) names them.
                    lat=to_float(geom.get("y")) if geom.get("y") is not None
                    else (to_float(attrs.get(e.point_field)) if e.point_field else None),
                    lon=to_float(geom.get("x")) if geom.get("x") is not None
                    else (to_float(attrs.get(e.point_field_lon)) if e.point_field_lon else None),
                    raw=attrs,
                )
            )
        return out

    @property
    def source_id(self) -> str:
        return f"{self.entry.property_id}:{self.entry.name or 'arcgis'}"
