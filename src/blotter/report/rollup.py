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


# Candidate raw-field names per context detail, across the different portals.
# Feeds never publish officer narratives, so the synopsis is composed from every
# structured context field the PD does release.
_DETAIL_FIELDS = {
    "weapon": ("weapon_desc", "weapon_description", "weapon_primary"),
    "premises": ("premis_desc", "location_description", "location_type"),
    "status": ("status_desc", "incident_status_description", "clearance_status",
               "investigation_status"),
    "victims": ("totalvictimcount", "victim_count", "victim_number"),
    "case": ("caseno", "incident_number", "incident_id", "report_number", "case_number"),
    "neighborhood": ("area_name", "neighborhood", "neighborhood_id"),
}

_FLAG_FIELDS = {
    "domestic_violence_crime": "domestic violence",
    "domestic_related": "domestic related",
    "hate_crime": "hate crime",
    "gang_related_crime": "gang related",
    "victim_shot": "victim shot",
    "family_violence": "family violence",
}


def _raw_lookup(raw: dict, candidates) -> str | None:
    low = {str(k).lower(): v for k, v in (raw or {}).items()}
    for key in candidates:
        val = low.get(key)
        if val not in (None, "", "0", 0):
            return str(val)
    return None


def build_synopsis(inc, prop) -> str:
    """One readable sentence of everything the PD published about the incident."""
    raw = inc.raw or {}
    when = inc.occurred_at.strftime("%b %d, %Y") if inc.occurred_at else "unknown date"
    where = f"{round(inc.distance_m)} m from {prop.name}" if (
        inc.distance_m is not None and prop) else (prop.name if prop else "the property")
    head = f"{(inc.crime_type or 'Incident').strip().capitalize()} on {when}, {where}"
    if inc.address:
        head += f" ({inc.address})"
    parts = [head + "."]
    for label, keys in (("Weapon", _DETAIL_FIELDS["weapon"]),
                        ("Premises", _DETAIL_FIELDS["premises"]),
                        ("Status", _DETAIL_FIELDS["status"]),
                        ("Victims", _DETAIL_FIELDS["victims"])):
        val = _raw_lookup(raw, keys)
        if val and val.upper() not in ("NONE", "UNKNOWN", "N/A"):
            parts.append(f"{label}: {val}.")
    low = {str(k).lower(): str(v).upper() for k, v in raw.items() if v is not None}
    flags = [text for key, text in _FLAG_FIELDS.items()
             if low.get(key) in ("Y", "YES", "TRUE", "1")]
    if flags:
        parts.append(f"Flags: {', '.join(flags)}.")
    case = _raw_lookup(raw, _DETAIL_FIELDS["case"]) or inc.incident_id
    if case:
        parts.append(f"Case #{case} (use for a records request — full narratives "
                     f"are not published in open data).")
    return " ".join(parts)


def _details(inc) -> dict:
    """Every non-empty raw field the portal returned, stringified for display."""
    out = {}
    for k, v in (inc.raw or {}).items():
        if v in (None, "") or isinstance(v, (dict, list)):
            continue
        out[str(k)] = str(v)
    return out


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
                "synopsis": build_synopsis(inc, prop),
                "details": _details(inc),
            }
        )
    return pd.DataFrame(rows, columns=[*COLUMNS, "synopsis", "details"])


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
