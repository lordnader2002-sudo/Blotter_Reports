"""Load and validate the registry + settings, and join the registry to properties.

The registry is the most error-prone surface (a mistyped field name silently breaks
a source), so it is validated up front with pydantic. A single bad entry is disabled
with a warning rather than aborting the whole run.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

log = logging.getLogger("blotter.config")


class SourceEntry(BaseModel):
    """One mall -> dataset binding. Field names vary per portal, hence all the knobs."""

    property_id: str
    type: str  # "socrata" | "arcgis" | "opendata"
    name: str | None = None
    base_url: str
    dataset_id: str | None = None  # Socrata 4x4 id
    layer: str | None = None  # ArcGIS FeatureServer layer path (if not in base_url)
    point_field: str | None = None  # Socrata point column, or lat column if paired below
    point_field_lon: str | None = None  # set when the dataset has separate lat/lon columns
    point_is_text: bool = False  # lat/lon stored as text -> compare as strings (cast breaks on 'REDACTED' rows)
    date_field: str
    crime_type_field: str
    description_field: str | None = None
    address_field: str | None = None
    incident_id_field: str | None = None
    date_query_style: str = "date_literal"  # ArcGIS: "date_literal" | "epoch_ms"
    radius_m: int | None = None
    enabled: bool = True
    contact: dict | None = None  # e.g. {agency, agency_url} for the dashboard source card
    geocode_hint: str | None = None  # "City, ST" -> geocode address-only incidents
    geocode_priority_streets: list[str] = Field(default_factory=list)  # only geocode these streets


class Settings(BaseModel):
    recency_window_days: int = 30
    radius_m: int = 1000
    result_limit: int = 5000
    # bucket -> list of lowercase substrings; first matching bucket wins, else OTHER
    crime_categories: dict[str, list[str]] = Field(default_factory=dict)
    # optional allow/deny lists of buckets (empty allow = keep all)
    keep_categories: list[str] = Field(default_factory=list)
    drop_categories: list[str] = Field(default_factory=list)


class Registry:
    """Validated source entries plus coverage helpers against the properties set."""

    def __init__(self, entries: list[SourceEntry]):
        self.entries = entries

    def enabled_sources(self) -> list[SourceEntry]:
        return [e for e in self.entries if e.enabled]

    def property_ids(self) -> set[str]:
        return {e.property_id for e in self.entries}

    def malls_without_sources(self, pilot_ids: set[str]) -> set[str]:
        """Pilot malls that have no enabled source -> reported as coverage gaps."""
        covered = {e.property_id for e in self.enabled_sources()}
        return pilot_ids - covered


def load_settings(path: str | Path) -> Settings:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return Settings(**data)


def load_registry(path: str | Path, valid_property_ids: set[str] | None = None) -> Registry:
    """Parse registry.yaml, validating each entry; invalid entries are skipped."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    defaults = data.get("defaults", {}) or {}
    entries: list[SourceEntry] = []
    for raw in data.get("sources", []) or []:
        merged = {**defaults, **raw}
        try:
            entry = SourceEntry(**merged)
        except ValidationError as ex:
            log.warning("Skipping invalid registry entry %r: %s", raw.get("property_id"), ex)
            continue
        if valid_property_ids is not None and entry.property_id not in valid_property_ids:
            log.warning(
                "Registry entry %r references a property_id not in the CSV; skipping",
                entry.property_id,
            )
            continue
        entries.append(entry)
    return Registry(entries)
