import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES


@pytest.fixture
def load_fixture():
    def _load(name):
        return json.loads((FIXTURES / name).read_text())

    return _load


@pytest.fixture
def properties():
    from blotter.properties import Property

    return {
        "BEVCENTER": Property("BEVCENTER", "Beverly Center", "8500 Beverly Blvd LA CA", "90048",
                              34.07533, -118.37738),
        "LENOX": Property("LENOX", "Lenox Square", "3393 Peachtree Rd Atlanta GA", "30326",
                          33.8467259, -84.3624199),
    }
