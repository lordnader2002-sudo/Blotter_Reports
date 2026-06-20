"""Command-line entrypoint: `blotter run --out reports/`."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import pipeline
from .config import load_registry, load_settings
from .http import HttpClient
from .properties import load_properties
from .report import excel, json_export, markdown
from .report.rollup import build_rollup

log = logging.getLogger("blotter")

_DEFAULTS = {
    "properties": "data/properties.csv",
    "registry": "config/registry.yaml",
    "settings": "config/settings.yaml",
    "out": "reports",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="blotter", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Pull data and generate the combined report.")
    run.add_argument("--properties", default=_DEFAULTS["properties"])
    run.add_argument("--registry", default=_DEFAULTS["registry"])
    run.add_argument("--settings", default=_DEFAULTS["settings"])
    run.add_argument("--out", default=_DEFAULTS["out"], help="Output directory root.")
    run.add_argument("--now", default=None, help="Override 'now' (ISO) for reproducible runs.")
    return parser


def _run(args) -> int:
    properties = load_properties(args.properties)
    settings = load_settings(args.settings)
    registry = load_registry(args.registry, valid_property_ids=set(properties))
    http = HttpClient()

    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    result = pipeline.run(properties, registry, settings, http, now=now)
    rollup = build_rollup(result, properties)
    rollup.metadata["radius_m"] = settings.radius_m  # surfaced in the dashboard JSON

    date_dir = Path(args.out) / now.strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = date_dir / "blotter_report.xlsx"
    md_path = date_dir / "report.md"
    json_path = date_dir / "dashboard_data.json"
    excel.write(rollup, xlsx_path)
    markdown.write(rollup, md_path)
    # The trend ledger lives at the output root so it accumulates across daily runs.
    json_export.write(rollup, json_path, trend_log_path=Path(args.out) / "trend_log.jsonl")

    latest = Path(args.out) / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(xlsx_path, latest / "blotter_report.xlsx")
    shutil.copy2(md_path, latest / "report.md")
    shutil.copy2(json_path, latest / "dashboard_data.json")

    md = rollup.metadata
    log.info(
        "Wrote %s and %s (%d incidents, %d violent, gaps=%s)",
        xlsx_path,
        md_path,
        md["total_incidents"],
        md["violent_incidents"],
        md["coverage_gaps"] or "none",
    )

    # Exit non-zero only on total failure so the daily artifact still gets committed.
    if result.run_report.all_failed:
        log.error("All sources failed.")
        return 1
    return 0


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _build_parser().parse_args(argv)
    if args.command == "run":
        return _run(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
