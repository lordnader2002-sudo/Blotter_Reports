# Blotter_Reports

Pulls police-blotter / crime-incident data from **free open-data portals** near our
shopping-mall properties, filters and normalizes it, and produces a single combined
report for analysts — on a daily schedule.

There is no single national police-blotter feed, so the program queries each
jurisdiction's own crime dataset by the mall's coordinates:

- **Socrata** portals via SoQL (`within_circle(point, lat, lon, radius_m)`, or a
  bounding-box query for datasets exposing separate latitude/longitude columns).
- **ArcGIS** FeatureServer `/query` (point geometry + distance + date `where`).

## Pilot scope

Six US malls whose jurisdictions publish queryable crime data (see
`config/registry.yaml`): Beverly Center (Los Angeles), The Domain (Austin),
Opry Mills (Nashville), Northgate Station (Seattle), Cherry Creek (Denver),
and Lenox Square (Atlanta). OCONUS properties are out of scope for now.

## Quick start

```bash
pip install -e ".[dev]"     # install + dev tools
pytest                      # run the unit suite (hermetic, no network)
blotter run --out reports/  # pull data and build the report
```

Outputs land in `reports/<YYYY-MM-DD>/` (and a stable `reports/latest/`):

- `blotter_report.xlsx` — **primary** deliverable: a Summary sheet (per-mall counts by
  category, nearest/most-recent incident, source status, conditional formatting),
  a Highlights sheet (most notable incidents), a filterable All-Incidents sheet, and a
  Run-Metadata sheet.
- `report.md` — a Markdown summary that renders in the GitHub diff for quick review.

### Configuration

- `config/settings.yaml` — recency window, search radius, and the crime-type → category
  mapping (`VIOLENT` / `PROPERTY` / `QUALITY_OF_LIFE` / `OTHER`).
- `config/registry.yaml` — the mall → dataset bindings and per-portal field names.
- `data/properties.csv` — the mall list (`property_id,name,address,postal_code,lat,lon`).

### Socrata app token (optional)

Set `SOCRATA_APP_TOKEN` for higher rate limits. The program runs unauthenticated too.
In CI, store it as the `SOCRATA_APP_TOKEN` repository secret.

## Web dashboard

A single-file React dashboard (`dashboard.html`) — styled to match the Protest-Tracker
project (Inter + JetBrains Mono, midnight/daylight themes, lime accent, Leaflet map,
Chart.js) — visualizes the data. Each `blotter run` writes `dashboard_data.json` (alongside
the Excel/Markdown) and appends a per-run point to `reports/trend_log.jsonl` for the trend
chart. Views: **Summary** (KPIs + category/mall breakdown + highlights), **Incidents**
(sortable/filterable table), **By Mall**, **Map** (incidents colored by crime category),
**Trends**, and **Data Quality** (per-source status + coverage gaps).

### Local preview

```bash
python scripts/preview_data.py   # writes a populated SAMPLE dashboard_data.json
python -m http.server            # then open http://localhost:8000/dashboard.html
```

(The live portals need internet; the sample lets you preview the UI offline. A real
`blotter run` overwrites it with actual incidents.)

### Hosting & access

The daily Action publishes `dashboard.html` to **GitHub Pages** (the `gh-pages` branch —
enable it under *Settings → Pages → Deploy from a branch → `gh-pages`*). By default the data
is published publicly as `dashboard_data.json` and the page needs no login. To gate it behind
a shared-password login with the data in a **private Supabase bucket**, follow
[`docs/SUPABASE_SETUP.md`](docs/SUPABASE_SETUP.md) — fill the Supabase block in `dashboard.html`
and add the `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` repo secrets. The switch from public to
gated is automatic.

## Daily schedule

`.github/workflows/daily-report.yml` runs on a cron: it generates the report + dashboard JSON,
uploads an artifact, commits `reports/` back to the repo, (optionally) uploads data to Supabase,
and deploys the dashboard to GitHub Pages. Trigger it manually from the Actions tab
(`workflow_dispatch`) for a dry run before relying on the schedule.

## Resilience

Each `(mall, source)` fetch is isolated — one portal outage or a wrong field name is
recorded as **FAILED** (visible in the report) and never aborts the run. Malls with no
configured source show as **NO COVERAGE** so a zero is never mistaken for "no crime." If a
fetch hits the row limit the mall is flagged **truncated** (counts are a floor). The run
exits non-zero only if *every* source fails.

## Adding a mall

1. Confirm the mall exists in `data/properties.csv` (it needs lat/lon).
2. Find the jurisdiction's crime dataset (Socrata `/resource/<id>.json` or an ArcGIS
   FeatureServer layer) and its field names for date, crime type, location, and id.
3. Add a `sources:` entry in `config/registry.yaml`. **Validate the field names against the
   live schema** — a wrong name fails that source gracefully but yields no data.
4. Extend the `crime_categories` keyword lists in `settings.yaml` for any new vocabulary.
5. Optionally record a sample API response in `tests/fixtures/` and add an adapter test.

## Architecture

```
properties.csv ─┐
registry.yaml  ─┼─► pipeline ─► [SourceAdapter.fetch → to_normalized]  (per-source isolated)
settings.yaml  ─┘        │
                         ├─► filters (recency, exact radius, category map, dedupe)
                         └─► rollup ─► Excel + Markdown
```

Adapters (`src/blotter/sources/`) conform to one interface (`base.py`); add a new portal
family by writing an adapter and registering it in `factory.py`. The optional
`openpolicedata` source lives behind the `opd` extra (`pip install -e ".[opd]"`).
