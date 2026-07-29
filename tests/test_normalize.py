from datetime import UTC

from blotter.normalize import parse_datetime, socrata_point, to_float


def test_parse_socrata_floating_timestamp():
    dt = parse_datetime("2026-06-10T00:00:00.000")
    assert dt.year == 2026 and dt.month == 6 and dt.day == 10
    assert dt.tzinfo == UTC


def test_parse_epoch_ms():
    dt = parse_datetime(1749513600000)
    assert dt.tzinfo == UTC
    assert dt.year == 2025


def test_parse_z_suffix_and_empty():
    assert parse_datetime("2026-06-10T12:00:00Z").hour == 12
    assert parse_datetime("") is None
    assert parse_datetime(None) is None


def test_to_float():
    assert to_float("3.5") == 3.5
    assert to_float(None) is None
    assert to_float("x") is None


def test_socrata_point_separate_columns():
    lat, lon = socrata_point({"lat": "34.07", "lon": "-118.37"}, "lat", "lon")
    assert lat == 34.07 and lon == -118.37


def test_socrata_point_geojson_object():
    row = {"location_1": {"type": "Point", "coordinates": [-118.37, 34.07]}}
    lat, lon = socrata_point(row, "location_1", None)
    assert lat == 34.07 and lon == -118.37
