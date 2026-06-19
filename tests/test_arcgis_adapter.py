from urllib.parse import parse_qs, urlparse

import responses

from blotter.config import SourceEntry
from blotter.http import HttpClient
from blotter.sources.arcgis import ArcGISAdapter
from blotter.sources.base import FetchQuery

ATL_ENTRY = SourceEntry(
    property_id="LENOX",
    type="arcgis",
    name="Atlanta PD Crime",
    base_url="https://services3.arcgis.com/x/arcgis/rest/services/Crime/FeatureServer/0",
    date_query_style="epoch_ms",
    date_field="occur_date",
    crime_type_field="UC2_Literal",
    address_field="location",
    incident_id_field="offense_id",
)

QUERY_URL = (
    "https://services3.arcgis.com/x/arcgis/rest/services/Crime/FeatureServer/0/query"
)


@responses.activate
def test_arcgis_fetch_builds_geometry_and_epoch_where(fixtures_dir):
    body = (fixtures_dir / "arcgis_atlanta_response.json").read_text()
    responses.add(responses.GET, QUERY_URL, body=body, content_type="application/json")
    adapter = ArcGISAdapter(ATL_ENTRY, HttpClient())
    result = adapter.fetch(FetchQuery(33.8467, -84.3624, 1000, "2026-06-01T00:00:00"))

    assert result.fetched_count == 2
    qs = parse_qs(urlparse(responses.calls[0].request.url).query)
    assert qs["geometryType"][0] == "esriGeometryPoint"
    assert qs["geometry"][0] == "-84.3624,33.8467"
    assert qs["distance"][0] == "1000"
    assert qs["units"][0] == "esriSRUnit_Meter"
    # epoch_ms style -> numeric millisecond comparison, no DATE literal.
    assert qs["where"][0].startswith("occur_date > ")
    assert "DATE" not in qs["where"][0]


@responses.activate
def test_arcgis_date_literal_style():
    entry = ATL_ENTRY.model_copy(update={"date_query_style": "date_literal"})
    responses.add(responses.GET, QUERY_URL, json={"features": []}, content_type="application/json")
    adapter = ArcGISAdapter(entry, HttpClient())
    adapter.fetch(FetchQuery(33.8, -84.3, 1000, "2026-06-01T00:00:00"))
    where = parse_qs(urlparse(responses.calls[0].request.url).query)["where"][0]
    assert where == "occur_date > DATE '2026-06-01'"


@responses.activate
def test_arcgis_to_normalized_uses_geometry(fixtures_dir):
    body = (fixtures_dir / "arcgis_atlanta_response.json").read_text()
    responses.add(responses.GET, QUERY_URL, body=body, content_type="application/json")
    adapter = ArcGISAdapter(ATL_ENTRY, HttpClient())
    result = adapter.fetch(FetchQuery(33.8467, -84.3624, 1000, "2026-06-01T00:00:00"))
    incidents = adapter.to_normalized(result)

    assert incidents[0].incident_id == "A1"
    assert incidents[0].crime_type == "LARCENY-FROM VEHICLE"
    assert incidents[0].lat == 33.84680 and incidents[0].lon == -84.36242
    assert incidents[0].occurred_at is not None


@responses.activate
def test_arcgis_error_response_raises():
    from blotter.sources.base import SourceError

    responses.add(responses.GET, QUERY_URL, json={"error": {"code": 400, "message": "bad"}})
    adapter = ArcGISAdapter(ATL_ENTRY, HttpClient())
    try:
        adapter.fetch(FetchQuery(33.8, -84.3, 1000, "2026-06-01T00:00:00"))
        raise AssertionError("expected SourceError")
    except SourceError:
        pass
