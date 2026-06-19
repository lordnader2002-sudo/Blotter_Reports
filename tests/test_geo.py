from blotter.geo import bounding_box, haversine_m


def test_haversine_known_distance():
    # ~1 degree of latitude is ~111 km.
    d = haversine_m(0.0, 0.0, 1.0, 0.0)
    assert 110_000 < d < 112_000


def test_haversine_zero():
    assert haversine_m(34.0, -118.0, 34.0, -118.0) == 0.0


def test_bounding_box_contains_center_and_is_ordered():
    min_lat, min_lon, max_lat, max_lon = bounding_box(34.0, -118.0, 1000)
    assert min_lat < 34.0 < max_lat
    assert min_lon < -118.0 < max_lon
    # A 1km box should be a fraction of a degree.
    assert (max_lat - min_lat) < 0.05
