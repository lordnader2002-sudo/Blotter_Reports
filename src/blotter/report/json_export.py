"""Export the rollup as ``dashboard_data.json`` for the web dashboard.

Mirrors how the Protest-Tracker pipeline feeds its single-file dashboard: the same
``Rollup`` that backs the Excel/Markdown reports is serialized to a compact JSON the
browser reads (from a Supabase private bucket when configured, else the public file).

An append-only trend ledger (``trend_log.jsonl``, one line per run) powers the Trends
chart, analogous to Protest-Tracker's ``runs_log.jsonl``.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from ..schema import CATEGORIES, OTHER, PROPERTY, QUALITY_OF_LIFE, VIOLENT


def _jsonable(value):
    """Convert pandas/NumPy/datetime values into JSON-serializable primitives."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    try:
        if pd.isna(value):  # NaT, NaN
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (datetime, date, pd.Timestamp)):
        ts = pd.Timestamp(value)
        return ts.isoformat()
    if hasattr(value, "item"):  # numpy scalar
        return value.item()
    return value


def _records(df: pd.DataFrame) -> list[dict]:
    return [{k: _jsonable(v) for k, v in row.items()} for row in df.to_dict("records")]


def _category_totals(summary: pd.DataFrame) -> dict[str, int]:
    return {cat: int(summary[cat].sum()) if cat in summary else 0 for cat in CATEGORIES}


def build_payload(rollup, trend: list[dict] | None = None) -> dict:
    """Assemble the dashboard JSON payload from a ``Rollup``."""
    md = rollup.metadata
    sources = [
        {
            "property_id": s.property_id,
            "name": s.name,
            "status": s.status,
            "fetched_count": s.fetched_count,
            "truncated": s.truncated,
            "error": s.error,
            "url": getattr(s, "url", None),
            "contact": getattr(s, "contact", None),
        }
        for s in md.get("sources", [])
    ]
    return {
        "generated": _jsonable(md.get("generated_at")),
        "window_days": md.get("window_days"),
        "cutoff": _jsonable(md.get("cutoff")),
        "radius_m": md.get("radius_m"),
        "totals": {
            "incidents": int(md.get("total_incidents", 0)),
            "violent": int(md.get("violent_incidents", 0)),
            "malls": len(rollup.summary),
            "coverage_gaps": len(md.get("coverage_gaps", [])),
            **_category_totals(rollup.summary),
        },
        "malls": _records(rollup.summary),
        "incidents": _records(rollup.incidents),
        "highlights": _records(rollup.highlights),
        "sources": sources,
        "coverage_gaps": list(md.get("coverage_gaps", [])),
        "uncovered": list(md.get("uncovered", [])),
        "trend": trend or [],
    }


def _update_trend_log(rollup, trend_log_path: str | Path) -> list[dict]:
    """Append this run's totals to the JSONL ledger and return the full history."""
    md = rollup.metadata
    summary = rollup.summary
    cats = _category_totals(summary)
    generated = _jsonable(md.get("generated_at")) or datetime.now(UTC).isoformat()
    label = pd.Timestamp(generated).strftime("%b %d") if generated else ""
    entry = {
        "ts": generated,
        "label": label,
        "total": int(md.get("total_incidents", 0)),
        "violent": cats.get(VIOLENT, 0),
        "property": cats.get(PROPERTY, 0),
        "qol": cats.get(QUALITY_OF_LIFE, 0),
        "other": cats.get(OTHER, 0),
        # Per-mall totals power the mall drill-in trend; accumulates run over run.
        "malls": {
            str(r["property_id"]): int(r["total"])
            for r in summary.to_dict("records")
        } if len(summary) else {},
    }

    path = Path(trend_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    history: list[dict] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                history.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    # Replace a same-timestamp entry (e.g. reproducible --now reruns) rather than duplicate.
    history = [h for h in history if h.get("ts") != entry["ts"]]
    history.append(entry)
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(json.dumps(h) + "\n" for h in history)
    return history


def write(rollup, path: str | Path, trend_log_path: str | Path | None = None) -> dict:
    """Write ``dashboard_data.json`` to ``path``; update the trend ledger if given."""
    trend = _update_trend_log(rollup, trend_log_path) if trend_log_path else []
    payload = build_payload(rollup, trend=trend)
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
