from datetime import UTC, datetime

from blotter import filters
from blotter.config import Settings
from blotter.properties import Property
from blotter.schema import OTHER, PROPERTY, VIOLENT, NormalizedIncident

MAPPING = {
    "VIOLENT": ["robbery", "assault"],
    "PROPERTY": ["burglary", "theft"],
    "QUALITY_OF_LIFE": ["trespass"],
}


def _inc(**kw):
    base = {
        "property_id": "BEVCENTER",
        "source_id": "s1",
        "incident_id": None,
        "occurred_at": datetime(2026, 6, 10, tzinfo=UTC),
        "crime_type": "ROBBERY",
        "crime_category": OTHER,
        "description": None,
        "address": None,
        "lat": 34.0770,
        "lon": -118.3775,
    }
    base.update(kw)
    return NormalizedIncident(**base)


def test_map_category_precedence_and_unknown():
    assert filters.map_category("ARMED ROBBERY", MAPPING) == VIOLENT
    assert filters.map_category("BURGLARY FROM VEHICLE", MAPPING) == PROPERTY
    assert filters.map_category("JAYWALKING", MAPPING) == OTHER
    assert filters.map_category(None, MAPPING) == OTHER


def test_apply_recency_radius_and_category():
    props = {"BEVCENTER": Property("BEVCENTER", "Beverly Center", "", "", 34.07533, -118.37738)}
    settings = Settings(radius_m=1000, crime_categories=MAPPING)
    cutoff = datetime(2026, 6, 1, tzinfo=UTC)
    incidents = [
        _inc(crime_type="ROBBERY"),  # near + recent + violent -> kept
        _inc(crime_type="BURGLARY", occurred_at=datetime(2026, 5, 1, tzinfo=UTC)),  # old
        _inc(crime_type="THEFT", lat=34.1000, lon=-118.4000),  # far -> dropped
    ]
    out = filters.apply(incidents, cutoff, settings, props)
    assert len(out) == 1
    assert out[0].crime_category == VIOLENT
    assert out[0].distance_m is not None and out[0].distance_m < 1000


def test_apply_keep_list():
    props = {"BEVCENTER": Property("BEVCENTER", "Beverly Center", "", "", 34.07533, -118.37738)}
    settings = Settings(radius_m=1000, crime_categories=MAPPING, keep_categories=["VIOLENT"])
    cutoff = datetime(2026, 6, 1, tzinfo=UTC)
    out = filters.apply([_inc(crime_type="BURGLARY")], cutoff, settings, props)
    assert out == []


def test_dedupe_by_incident_id_and_tuple():
    a = _inc(incident_id="X1")
    b = _inc(incident_id="X1")  # duplicate id
    c = _inc(incident_id=None)
    d = _inc(incident_id=None)  # identical tuple
    out = filters.dedupe([a, b, c, d])
    assert len(out) == 2
