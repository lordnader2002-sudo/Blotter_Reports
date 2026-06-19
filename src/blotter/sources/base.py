"""The source-adapter abstraction.

An adapter's job is narrow: take a geographic + date query intent and return raw
records, then map those raw records into ``NormalizedIncident`` objects using the
field names declared in its registry entry. Adapters do NOT filter beyond what the
portal does natively -- recency/radius/category filtering is centralized in the
pipeline so it stays testable without HTTP.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..schema import NormalizedIncident


@dataclass(frozen=True)
class FetchQuery:
    """A request for incidents near a point within a recency window."""

    lat: float
    lon: float
    radius_m: int
    since_iso: str  # ISO datetime cutoff (inclusive lower bound)
    limit: int = 5000


@dataclass
class RawFetchResult:
    """Raw rows returned by a portal, plus provenance/quality flags."""

    records: list[dict]
    source_id: str
    fetched_count: int
    truncated: bool = False  # hit the limit -> counts are a floor, not exact
    notes: list[str] = field(default_factory=list)


class SourceError(Exception):
    """Non-recoverable fetch failure for a single source (isolated by the pipeline)."""


class SourceAdapter(ABC):
    type_name: str

    def __init__(self, entry, http):
        self.entry = entry
        self.http = http

    @abstractmethod
    def fetch(self, query: FetchQuery) -> RawFetchResult:
        """Issue the geo + date query. Raise SourceError on failure."""

    @abstractmethod
    def to_normalized(self, result: RawFetchResult) -> list[NormalizedIncident]:
        """Map raw rows -> NormalizedIncident using the entry's field map."""
