"""Compute the summary tables shared by the Excel and Markdown reports."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..schema import CATEGORIES, COLUMNS, VIOLENT

# Severity order for highlights: violent first, then property, etc.
_SEVERITY = {cat: i for i, cat in enumerate(CATEGORIES)}


@dataclass
class Rollup:
    incidents: pd.DataFrame  # all incidents (COLUMNS)
    summary: pd.DataFrame  # one row per pilot mall
    highlights: pd.DataFrame  # most notable incidents across all malls
    metadata: dict


def _incidents_frame(result, properties) -> pd.DataFrame:
    rows = []
    for inc in result.incidents:
        prop = properties.get(inc.property_id)
        rows.append(
            {
                "property_id": inc.property_id,
                "property_name": prop.name if prop else inc.property_id,
                "source_id": inc.source_id,
                "incident_id": inc.incident_id,
                "occurred_at": inc.occurred_at,
                "crime_type": inc.crime_type,
                "crime_category": inc.crime_category,
                "description": inc.description,
                "address": inc.address,
                "lat": inc.lat,
                "lon": inc.lon,
                "distance_m": round(inc.distance_m, 1) if inc.distance_m is not None else None,
            }
        )
    return pd.DataFrame(rows, columns=COLUMNS)


def _source_status_by_mall(result) -> dict[str, str]:
    """Best status per mall: OK if any source ok, else FAILED; gaps handled by caller."""
    status: dict[str, str] = {}
    for s in result.run_report.sources:
        if status.get(s.property_id) == "OK":
            continue
        status[s.property_id] = s.status
    for pid in result.run_report.coverage_gaps:
        status.setdefault(pid, "NO COVERAGE")
    return status


def build_rollup(result, properties) -> Rollup:
    df = _incidents_frame(result, properties)
    status_by_mall = _source_status_by_mall(result)
    truncated_malls = {s.property_id for s in result.run_report.sources if s.truncated}

    summary_rows = []
    for pid in result.pilot_ids:
        prop = properties.get(pid)
        sub = df[df["property_id"] == pid]
        cat_counts = {cat: int((sub["crime_category"] == cat).sum()) for cat in CATEGORIES}
        nearest = sub["distance_m"].min() if not sub.empty else None
        most_recent = sub["occurred_at"].max() if not sub.empty else None
        summary_rows.append(
            {
                "property_id": pid,
                "property_name": prop.name if prop else pid,
                "status": status_by_mall.get(pid, "OK"),
                "total": len(sub),
                **cat_counts,
                "nearest_m": round(nearest, 1) if nearest is not None and pd.notna(nearest) else None,
                "most_recent": most_recent,
                "truncated": pid in truncated_malls,
            }
        )
    summary = pd.DataFrame(summary_rows)

    # Highlights: violent first, then nearest, then most recent.
    highlights = df.copy()
    if not highlights.empty:
        highlights["_sev"] = highlights["crime_category"].map(_SEVERITY).fillna(len(CATEGORIES))
        highlights = highlights.sort_values(
            by=["_sev", "distance_m", "occurred_at"],
            ascending=[True, True, False],
        ).drop(columns="_sev").head(25)

    metadata = {
        "generated_at": result.generated_at,
        "window_days": result.window_days,
        "cutoff": result.cutoff,
        "total_incidents": len(df),
        "violent_incidents": int((df["crime_category"] == VIOLENT).sum()) if not df.empty else 0,
        "sources": result.run_report.sources,
        "coverage_gaps": result.run_report.coverage_gaps,
    }
    return Rollup(incidents=df, summary=summary, highlights=highlights, metadata=metadata)
