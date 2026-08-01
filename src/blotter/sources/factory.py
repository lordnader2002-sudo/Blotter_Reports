"""Map a registry entry's ``type`` to its adapter class."""

from __future__ import annotations

from .arcgis import ArcGISAdapter
from .base import SourceAdapter, SourceError
from .ckan import CkanAdapter
from .csvfile import CsvAdapter
from .socrata import SocrataAdapter

_REGISTRY = {
    SocrataAdapter.type_name: SocrataAdapter,
    ArcGISAdapter.type_name: ArcGISAdapter,
    CkanAdapter.type_name: CkanAdapter,
    CsvAdapter.type_name: CsvAdapter,
}


def build_adapter(entry, http) -> SourceAdapter:
    cls = _REGISTRY.get(entry.type)
    if cls is None:
        # OpenPoliceData is optional and lives behind an extra; load lazily.
        if entry.type == "opendata":
            try:
                from .opendata import OpenPoliceDataAdapter
            except ImportError as ex:  # pragma: no cover - optional dependency
                raise SourceError(
                    f"openpolicedata not installed; cannot use source for {entry.property_id}"
                ) from ex
            return OpenPoliceDataAdapter(entry, http)
        raise SourceError(f"Unknown source type {entry.type!r} for {entry.property_id}")
    return cls(entry, http)
