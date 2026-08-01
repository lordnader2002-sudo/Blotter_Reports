import responses

from blotter.config import SourceEntry
from blotter.http import HttpClient
from blotter.sources.base import FetchQuery
from blotter.sources.csvfile import CsvAdapter

SD = SourceEntry(
    property_id="FASHIONVAL",
    type="csv",
    name="SDPD CFS",
    base_url="https://seshat.example.org/pd_calls_{year}.csv",
    date_field="DATE_TIME",
    crime_type_field="CALL_TYPE",
    address_field="ADDRESS_NUMBER_PRIMARY,ADDRESS_DIR_PRIMARY,ADDRESS_ROAD_PRIMARY,ADDRESS_SFX_PRIMARY",
    incident_id_field="INCIDENT_NUM",
    geocode_hint="San Diego, CA",
    geocode_priority_streets=["FRIARS"],
)

CSV_BODY = (
    '"INCIDENT_NUM","DATE_TIME","ADDRESS_NUMBER_PRIMARY","ADDRESS_DIR_PRIMARY",'
    '"ADDRESS_ROAD_PRIMARY","ADDRESS_SFX_PRIMARY","CALL_TYPE"\n'
    '"E1","2026-07-20 10:00:00.000","100","","OLD","ST","T"\n'
    '"E2","2026-07-28 11:30:00.000","7000","","FRIARS","RD","459A"\n'
    '"E3","2026-07-29 12:00:00.000","400","S","OTHER","AVE","415"\n'
)


@responses.activate
def test_csv_streams_filters_and_normalizes():
    responses.add(responses.GET, "https://seshat.example.org/pd_calls_2026.csv",
                  body=CSV_BODY, content_type="text/csv")
    adapter = CsvAdapter(SD, HttpClient())
    result = adapter.fetch(FetchQuery(32.767, -117.166, 1600, "2026-07-25T00:00:00"))

    assert result.fetched_count == 2  # E1 predates the window
    incidents = adapter.to_normalized(result)
    assert incidents[0].incident_id == "E2"
    assert incidents[0].address == "7000 FRIARS RD"
    assert incidents[0].occurred_at.day == 28
    assert incidents[0].lat is None  # geocoding happens downstream


def test_priority_streets_gate_geocoding(tmp_path):
    import responses as rsp

    from blotter.geocode import CENSUS_URL, Geocoder, fill_coordinates
    from blotter.schema import OTHER, NormalizedIncident

    incs = [
        NormalizedIncident("FASHIONVAL", "s", "E2", None, "459A", OTHER, None,
                           "7000 FRIARS RD", None, None),
        NormalizedIncident("FASHIONVAL", "s", "E3", None, "415", OTHER, None,
                           "400 S OTHER AVE", None, None),
    ]
    with rsp.RequestsMock() as mock:
        mock.add(rsp.GET, CENSUS_URL,
                 json={"result": {"addressMatches": [{"coordinates": {"x": -117.16, "y": 32.77}}]}})
        g = Geocoder(tmp_path / "c.json")
        assert fill_coordinates(incs, SD, g) == 1
    assert incs[0].lat == 32.77       # FRIARS matched -> geocoded
    assert incs[1].lat is None        # off-list street -> skipped entirely
