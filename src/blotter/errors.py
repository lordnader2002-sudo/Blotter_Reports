"""Run-level bookkeeping: per-source status and coverage gaps.

Surfacing this in the report matters: a mall showing zero incidents because its
source failed or has no coverage must not look like "no crime happened."
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SourceStatus:
    property_id: str
    source_id: str
    name: str
    status: str  # "OK" | "FAILED"
    fetched_count: int = 0
    truncated: bool = False
    error: str | None = None


@dataclass
class RunReport:
    sources: list[SourceStatus] = field(default_factory=list)
    coverage_gaps: list[str] = field(default_factory=list)  # property_ids with no source

    def record_success(self, entry, result) -> None:
        self.sources.append(
            SourceStatus(
                property_id=entry.property_id,
                source_id=result.source_id,
                name=entry.name or entry.dataset_id or entry.type,
                status="OK",
                fetched_count=result.fetched_count,
                truncated=result.truncated,
            )
        )

    def record_failure(self, entry, error: Exception) -> None:
        self.sources.append(
            SourceStatus(
                property_id=entry.property_id,
                source_id=f"{entry.property_id}:{entry.dataset_id or entry.name or entry.type}",
                name=entry.name or entry.dataset_id or entry.type,
                status="FAILED",
                error=str(error),
            )
        )

    def note_coverage_gaps(self, gaps) -> None:
        self.coverage_gaps = sorted(gaps)

    @property
    def all_failed(self) -> bool:
        return bool(self.sources) and all(s.status == "FAILED" for s in self.sources)
