from urllib.parse import parse_qs, urlparse

import responses

from blotter.config import SourceEntry
from blotter.http import HttpClient
from blotter.sources.base import FetchQuery
from blotter.sources.ckan import CkanAdapter

BOSTON = SourceEntry(
    property_id="COPLEY",
    type="ckan",
    name="BPD",
    base_url="https://data.boston.gov",
    dataset_id="b973d8cb-eeb2-4e7e-99da-c92938efc9c0",
    point_field="Lat",
    point_field_lon="Long",
    date_field="OCCURRED_ON_DATE",
    crime_type_field="OFFENSE_DESCRIPTION",
    address_field="STREET",
    incident_id_field="INCIDENT_NUMBER",
)

SQL_URL = "https://data.boston.gov/api/3/action/datastore_search_sql"

BODY = {
    "success": True,
    "result": {"records": [{
        "_id": 1, "INCIDENT_NUMBER": "I252059", "OFFENSE_DESCRIPTION": "LARCENY SHOPLIFTING",
        "OCCURRED_ON_DATE": "2026-07-28 14:30:00+00", "STREET": "BOYLSTON ST",
        "Lat": "42.3476", "Long": "-71.0776", "_full_text": "tsvector-noise",
    }]},
}


@responses.activate
def test_ckan_sql_casts_and_normalizes():
    responses.add(responses.GET, SQL_URL, json=BODY)
    adapter = CkanAdapter(BOSTON, HttpClient())
    result = adapter.fetch(FetchQuery(42.3476, -71.0776, 1600, "2026-07-25T00:00:00"))

    sql = parse_qs(urlparse(responses.calls[0].request.url).query)["sql"][0]
    assert 'CAST(NULLIF("Lat", \'\') AS float8) BETWEEN' in sql
    assert 'CAST(NULLIF("Long", \'\') AS float8) BETWEEN' in sql
    assert '"OCCURRED_ON_DATE" >= \'2026-07-25T00:00:00\'' in sql
    assert f'FROM "{BOSTON.dataset_id}"' in sql

    incidents = adapter.to_normalized(result)
    inc = incidents[0]
    assert inc.incident_id == "I252059"
    assert inc.lat == 42.3476 and inc.lon == -71.0776
    assert inc.occurred_at.year == 2026 and inc.occurred_at.day == 28
    assert "_full_text" not in inc.raw


@responses.activate
def test_ckan_error_payload_raises():
    from blotter.sources.base import SourceError

    responses.add(responses.GET, SQL_URL, json={"success": False, "error": {"info": "bad sql"}})
    adapter = CkanAdapter(BOSTON, HttpClient())
    try:
        adapter.fetch(FetchQuery(42.3, -71.0, 1600, "2026-07-25T00:00:00"))
        raise AssertionError("expected SourceError")
    except SourceError:
        pass
