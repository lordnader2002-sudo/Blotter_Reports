import json

import responses

from blotter.geocode import CENSUS_URL, Geocoder, fill_coordinates, normalize_address


def test_normalize_address():
    assert normalize_address("100 BLOCK OF GRANBY ST") == "100 GRANBY ST"
    assert normalize_address("500 BLOCK MAIN ST") == "500 MAIN ST"
    assert normalize_address("A ST / B ST") == "A ST"
    assert normalize_address("  8500   Beverly  Blvd ") == "8500 Beverly Blvd"


def _census_body(lat=36.88, lon=-76.20, match=True):
    matches = [{"coordinates": {"x": lon, "y": lat}}] if match else []
    return {"result": {"addressMatches": matches}}


@responses.activate
def test_geocode_hit_miss_and_cache(tmp_path):
    cache = tmp_path / "cache.json"
    responses.add(responses.GET, CENSUS_URL, json=_census_body(), status=200)
    responses.add(responses.GET, CENSUS_URL, json=_census_body(match=False), status=200)

    g = Geocoder(cache)
    assert g.geocode("100 BLOCK OF GRANBY ST", "Norfolk, VA") == (36.88, -76.2)
    assert g.geocode("999 NOWHERE LN", "Norfolk, VA") is None  # definitive miss
    g.save()

    # Second geocoder instance answers both from cache — no HTTP.
    g2 = Geocoder(cache)
    assert g2.geocode("100 BLOCK OF GRANBY ST", "Norfolk, VA") == (36.88, -76.2)
    assert g2.geocode("999 NOWHERE LN", "Norfolk, VA") is None
    assert len(responses.calls) == 2

    data = json.loads(cache.read_text())
    assert data["100 GRANBY ST, NORFOLK, VA"] == [36.88, -76.2]
    assert data["999 NOWHERE LN, NORFOLK, VA"] is None


@responses.activate
def test_transient_failure_not_cached(tmp_path):
    responses.add(responses.GET, CENSUS_URL, status=500)
    g = Geocoder(tmp_path / "c.json")
    assert g.geocode("100 MAIN ST", "Norfolk, VA") is None
    assert g.cache == {}  # retried next run


@responses.activate
def test_lookup_budget(tmp_path):
    responses.add(responses.GET, CENSUS_URL, json=_census_body(), status=200)
    g = Geocoder(tmp_path / "c.json", max_lookups_per_run=1)
    assert g.geocode("1 A ST", "X, YZ") is not None
    assert g.geocode("2 B ST", "X, YZ") is None  # budget spent, not cached as miss
    assert "2 B ST, X, YZ" not in g.cache


@responses.activate
def test_fill_coordinates_drop_semantics(tmp_path):
    from blotter.config import SourceEntry
    from blotter.schema import OTHER, NormalizedIncident

    responses.add(responses.GET, CENSUS_URL, json=_census_body(), status=200)
    responses.add(responses.GET, CENSUS_URL, json=_census_body(match=False), status=200)
    entry = SourceEntry(property_id="X", type="socrata", base_url="https://x",
                        dataset_id="a-b", date_field="d", crime_type_field="c",
                        geocode_hint="Norfolk, VA")
    incs = [
        NormalizedIncident("X", "s", "1", None, "T", OTHER, None, "100 BLOCK OF GRANBY ST",
                           None, None),
        NormalizedIncident("X", "s", "2", None, "T", OTHER, None, "999 NOWHERE LN",
                           None, None),
    ]
    g = Geocoder(tmp_path / "c.json")
    assert fill_coordinates(incs, entry, g) == 1
    assert incs[0].lat == 36.88 and incs[1].lat is None
