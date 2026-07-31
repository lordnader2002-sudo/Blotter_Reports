"""Orchestration: fetch (per-source isolated) -> normalize -> filter -> dedupe."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from . import filters
from .errors import RunReport
from .schema import NormalizedIncident
from .sources.base import FetchQuery, SourceError
from .sources.factory import build_adapter

log = logging.getLogger("blotter.pipeline")


@dataclass
class RunResult:
    incidents: list[NormalizedIncident]
    run_report: RunReport
    generated_at: datetime
    window_days: int
    cutoff: datetime
    pilot_ids: list[str] = field(default_factory=list)
    # Every property with no enabled source, with the reason — so "no data" is
    # always explicit and never mistaken for "no crime".
    uncovered: list[dict] = field(default_factory=list)


def run(properties, registry, settings, http, now: datetime | None = None) -> RunResult:
    """Execute the full pipeline. One source failing never aborts the run."""
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=settings.recency_window_days)
    # Naive UTC ISO string: Socrata floating timestamps reject timezone offsets
    # (a '+00:00' suffix causes a 400); ArcGIS adapters re-attach UTC as needed.
    since_iso = cutoff.astimezone(UTC).replace(tzinfo=None, microsecond=0).isoformat()

    incidents: list[NormalizedIncident] = []
    report = RunReport()

    for entry in registry.enabled_sources():
        prop = properties.get(entry.property_id)
        if prop is None:
            log.warning("No property %s for source; skipping", entry.property_id)
            continue
        radius = entry.radius_m or settings.radius_m
        query = FetchQuery(prop.lat, prop.lon, radius, since_iso, settings.result_limit)
        try:
            adapter = build_adapter(entry, http)
            raw = adapter.fetch(query)
            normalized = adapter.to_normalized(raw)
            report.record_success(entry, raw)
            incidents.extend(normalized)
        except SourceError as ex:
            log.warning("Source failed for %s: %s", entry.property_id, ex)
            report.record_failure(entry, ex)
            continue

    incidents = filters.apply(incidents, cutoff, settings, properties)
    incidents = filters.dedupe(incidents)

    pilot_ids = set(registry.property_ids())
    report.note_coverage_gaps(registry.malls_without_sources(pilot_ids))

    covered = {e.property_id for e in registry.enabled_sources()}
    disabled_reason = {
        e.property_id: (e.name or "source disabled")
        for e in registry.entries
        if not e.enabled
    }
    uncovered = [
        {
            "property_id": pid,
            "name": prop.name,
            "address": prop.address,
            "reason": disabled_reason.get(pid, "no source configured yet"),
            "known_issue": pid in disabled_reason,
        }
        for pid, prop in sorted(properties.items())
        if pid not in covered
    ]

    return RunResult(
        incidents=incidents,
        run_report=report,
        generated_at=now,
        window_days=settings.recency_window_days,
        cutoff=cutoff,
        pilot_ids=sorted(pilot_ids),
        uncovered=uncovered,
    )
