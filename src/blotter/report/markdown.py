"""Render the rollup as a Markdown report (diff-visible in the GitHub UI)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..schema import CATEGORIES


def _fmt_dt(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)) or pd.isna(value):
        return "-"
    try:
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return str(value)


def render(rollup) -> str:
    md = rollup.metadata
    lines: list[str] = []
    lines.append("# Mall Blotter Report")
    lines.append("")
    lines.append(
        f"Generated **{_fmt_dt(md['generated_at'])}** · "
        f"window **{md['window_days']} days** (since {_fmt_dt(md['cutoff'])}) · "
        f"**{md['total_incidents']}** incidents "
        f"(**{md['violent_incidents']}** violent) across {len(rollup.summary)} malls."
    )
    lines.append("")

    # Per-mall summary.
    lines.append("## Summary by mall")
    lines.append("")
    header = ["Mall", "Status", "Total", *CATEGORIES, "Nearest (m)", "Most recent"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for _, r in rollup.summary.iterrows():
        flag = " ⚠️" if r["status"] != "OK" else ""
        trunc = " ✂️" if r.get("truncated") else ""
        nearest = "-" if pd.isna(r["nearest_m"]) else f"{r['nearest_m']:.0f}"
        lines.append(
            "| "
            + " | ".join(
                [
                    f"{r['property_name']}{trunc}",
                    f"{r['status']}{flag}",
                    str(r["total"]),
                    *[str(r[c]) for c in CATEGORIES],
                    nearest,
                    _fmt_dt(r["most_recent"]),
                ]
            )
            + " |"
        )
    lines.append("")

    # Coverage gaps & failures.
    failures = [s for s in md["sources"] if s.status == "FAILED"]
    uncovered = md.get("uncovered", [])
    if md["coverage_gaps"] or failures or uncovered:
        lines.append("## Data quality")
        lines.append("")
        if md["coverage_gaps"]:
            lines.append(f"- **No coverage:** {', '.join(md['coverage_gaps'])}")
        for s in failures:
            lines.append(f"- **Source failed** ({s.property_id} / {s.name}): {s.error}")
        if uncovered:
            known = sum(1 for u in uncovered if u.get("known_issue"))
            lines.append(
                f"- **Properties without data:** {len(uncovered)} "
                f"({known} known upstream issues, {len(uncovered) - known} not yet configured) "
                f"— full list on the dashboard's Data Quality tab"
            )
        lines.append("")

    # Highlights.
    if not rollup.highlights.empty:
        lines.append("## Highlights (most notable)")
        lines.append("")
        cols = ["property_name", "occurred_at", "crime_category", "crime_type", "distance_m"]
        lines.append("| Mall | Date | Category | Type | Distance (m) |")
        lines.append("|---|---|---|---|---|")
        for _, r in rollup.highlights[cols].iterrows():
            dist = "-" if pd.isna(r["distance_m"]) else f"{r['distance_m']:.0f}"
            lines.append(
                f"| {r['property_name']} | {_fmt_dt(r['occurred_at'])} | "
                f"{r['crime_category']} | {r['crime_type']} | {dist} |"
            )
        lines.append("")

    return "\n".join(lines)


def write(rollup, path: str | Path) -> None:
    Path(path).write_text(render(rollup), encoding="utf-8")
