import json
from urllib.parse import parse_qs, urlparse

import responses

from blotter.config import SourceEntry
from blotter.http import HttpClient
from blotter.sources.base import FetchQuery
from blotter.sources.socrata import SocrataAdapter

LA_ENTRY = SourceEntry(
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
)

POINT_ENTRY = SourceEntry(
    property_id="X",
    type="socrata",
    name="point",
    base_url="https://data.example.org",
    dataset_id="aaaa-bbbb",
    point_field="location_1",
    date_field="date_occ",
    crime_type_field="crm_cd_desc",
)


@responses.activate
def test_socrata_fetch_builds_bounding_box_query(fixtures_dir):
    body = (fixtures_dir / "socrata_la_response.json").read_text()
    responses.add(
        responses.GET,
        "https://data.lacity.org/resource/2nrs-mtv8.json",
        body=body,
        content_type="application/json",
    )
    adapter = SocrataAdapter(LA_ENTRY, HttpClient())
    result = adapter.fetch(FetchQuery(34.07533, -118.37738, 1000, "2026-06-01T00:00:00", limit=5000))

    assert result.fetched_count == 3
    qs = parse_qs(urlparse(responses.calls[0].request.url).query)
    where = qs["$where"][0]
    assert "lat between" in where and "lon between" in where
    assert "date_occ > '2026-06-01T00:00:00'" in where
    assert qs["$order"][0].startswith("date_occ")


@responses.activate
def test_socrata_point_field_uses_within_circle():
    responses.add(
        responses.GET,
        "https://data.example.org/resource/aaaa-bbbb.json",
        body="[]",
        content_type="application/json",
    )
    adapter = SocrataAdapter(POINT_ENTRY, HttpClient())
    adapter.fetch(FetchQuery(34.0, -118.0, 500, "2026-06-01T00:00:00"))
    where = parse_qs(urlparse(responses.calls[0].request.url).query)["$where"][0]
    # within_circle uses (field, lat, lon, radius) ordering.
    assert "within_circle(location_1, 34.0, -118.0, 500)" in where


@responses.activate
def test_socrata_text_columns_get_number_cast():
    entry = LA_ENTRY.model_copy(update={"point_cast_number": True})
    responses.add(
        responses.GET,
        "https://data.lacity.org/resource/2nrs-mtv8.json",
        body="[]",
        content_type="application/json",
    )
    adapter = SocrataAdapter(entry, HttpClient())
    adapter.fetch(FetchQuery(47.7, -122.3, 500, "2026-06-01T00:00:00"))
    where = parse_qs(urlparse(responses.calls[0].request.url).query)["$where"][0]
    assert "lat::number between" in where
    assert "lon::number between" in where


@responses.activate
def test_socrata_to_normalized_maps_fields(fixtures_dir):
    body = (fixtures_dir / "socrata_la_response.json").read_text()
    responses.add(
        responses.GET,
        "https://data.lacity.org/resource/2nrs-mtv8.json",
        body=body,
        content_type="application/json",
    )
    adapter = SocrataAdapter(LA_ENTRY, HttpClient())
    result = adapter.fetch(FetchQuery(34.07533, -118.37738, 1000, "2026-06-01T00:00:00"))
    incidents = adapter.to_normalized(result)

    first = incidents[0]
    assert first.property_id == "BEVCENTER"
    assert first.incident_id == "240001"
    assert first.crime_type == "ROBBERY"
    assert first.lat == 34.0770 and first.lon == -118.3775
    assert first.occurred_at.year == 2026


@responses.activate
def test_socrata_truncation_flag():
    rows = json.dumps([{"dr_no": str(i), "date_occ": "2026-06-10T00:00:00.000",
                        "crm_cd_desc": "THEFT", "lat": "34.0", "lon": "-118.0"} for i in range(2)])
    responses.add(
        responses.GET,
        "https://data.lacity.org/resource/2nrs-mtv8.json",
        body=rows,
        content_type="application/json",
    )
    adapter = SocrataAdapter(LA_ENTRY, HttpClient())
    result = adapter.fetch(FetchQuery(34.0, -118.0, 1000, "2026-06-01T00:00:00", limit=2))
    assert result.truncated is True
