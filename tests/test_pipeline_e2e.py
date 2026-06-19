"""End-to-end: one mall, one mocked Socrata source, through the full pipeline."""

from datetime import datetime, timezone

import responses

from blotter import pipeline
from blotter.config import Registry, Settings, SourceEntry
from blotter.http import HttpClient
from blotter.properties import Property

NOW = datetime(2026, 6, 19, tzinfo=timezone.utc)


def _registry():
    return Registry([
        SourceEntry(
            property_id="BEVCENTER",
            type="socrata",
            name="LAPD",
            base_url="https://data.lacity.org",
            dataset_id="2nrs-mtv8",
            point_field="lat",
            point_field_lon="lon",
            date_field="date_occ",
            crime_type_field="crm_cd_desc",
            address_field="location",
            incident_id_field="dr_no",
        ),
        # A second mall with no source -> should surface as a coverage gap.
    ])


@responses.activate
def test_pipeline_end_to_end(fixtures_dir):
    body = (fixtures_dir / "socrata_la_response.json").read_text()
    responses.add(
        responses.GET,
        "https://data.lacity.org/resource/2nrs-mtv8.json",
        body=body,
        content_type="application/json",
    )
    props = {
        "BEVCENTER": Property("BEVCENTER", "Beverly Center", "", "", 34.07533, -118.37738),
    }
    settings = Settings(
        recency_window_days=30,
        radius_m=1000,
        crime_categories={"VIOLENT": ["robbery"], "PROPERTY": ["burglary"]},
    )
    result = pipeline.run(props, _registry(), settings, HttpClient(), now=NOW)

    # The far-away vandalism row is dropped by radius; 2 remain.
    assert len(result.incidents) == 2
    cats = {i.crime_type: i.crime_category for i in result.incidents}
    assert cats["ROBBERY"] == "VIOLENT"
    assert cats["BURGLARY FROM VEHICLE"] == "PROPERTY"
    # All distances within radius.
    assert all(i.distance_m is not None and i.distance_m <= 1000 for i in result.incidents)
    # Source recorded OK.
    assert result.run_report.sources[0].status == "OK"


@responses.activate
def test_pipeline_isolates_source_failure():
    responses.add(
        responses.GET,
        "https://data.lacity.org/resource/2nrs-mtv8.json",
        status=500,
    )
    props = {"BEVCENTER": Property("BEVCENTER", "Beverly Center", "", "", 34.07533, -118.37738)}
    result = pipeline.run(props, _registry(), Settings(), HttpClient(), now=NOW)
    assert result.incidents == []
    assert result.run_report.sources[0].status == "FAILED"
    assert result.run_report.all_failed is True
