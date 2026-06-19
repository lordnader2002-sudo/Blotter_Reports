"""The normalized incident schema shared across all sources and the report layer.

Every source adapter maps its raw, portal-specific rows into ``NormalizedIncident``
so the rest of the pipeline (filters, rollups, report) never has to know which
portal a record came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# Crime category buckets. ``crime_type`` keeps the raw portal vocabulary; the
# pipeline maps it into one of these buckets via the mapping in settings.yaml.
VIOLENT = "VIOLENT"
PROPERTY = "PROPERTY"
QUALITY_OF_LIFE = "QUALITY_OF_LIFE"
OTHER = "OTHER"
CATEGORIES = (VIOLENT, PROPERTY, QUALITY_OF_LIFE, OTHER)


@dataclass
class NormalizedIncident:
    """A single crime incident, normalized into a portal-agnostic shape."""

    property_id: str
    source_id: str
    incident_id: str | None
    occurred_at: datetime | None  # tz-aware UTC when known
    crime_type: str | None  # raw category string from the portal
    crime_category: str  # mapped bucket (one of CATEGORIES)
    description: str | None
    address: str | None
    lat: float | None
    lon: float | None
    distance_m: float | None = None  # haversine from the mall, annotated downstream
    raw: dict = field(default_factory=dict, repr=False)  # original row, for audit


# Columns surfaced in reports / dataframes, in display order. ``raw`` is dropped.
COLUMNS = [
    "property_id",
    "property_name",
    "source_id",
    "incident_id",
    "occurred_at",
    "crime_type",
    "crime_category",
    "description",
    "address",
    "lat",
    "lon",
    "distance_m",
]
