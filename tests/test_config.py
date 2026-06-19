import textwrap

from blotter.config import load_registry, load_settings


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(textwrap.dedent(content))
    return p


def test_load_registry_valid_and_invalid(tmp_path):
    reg = _write(
        tmp_path,
        "registry.yaml",
        """
        defaults:
          radius_m: 1000
        sources:
          - property_id: BEVCENTER
            type: socrata
            base_url: https://data.lacity.org
            dataset_id: 2nrs-mtv8
            date_field: date_occ
            crime_type_field: crm_cd_desc
          - property_id: BROKEN
            type: socrata
            base_url: https://x
            # missing required date_field/crime_type_field -> skipped
        """,
    )
    registry = load_registry(reg, valid_property_ids={"BEVCENTER", "BROKEN"})
    assert len(registry.entries) == 1
    assert registry.entries[0].property_id == "BEVCENTER"
    assert registry.entries[0].radius_m == 1000


def test_registry_skips_unknown_property(tmp_path):
    reg = _write(
        tmp_path,
        "registry.yaml",
        """
        sources:
          - property_id: NOTREAL
            type: socrata
            base_url: https://x
            dataset_id: abcd-1234
            date_field: d
            crime_type_field: c
        """,
    )
    registry = load_registry(reg, valid_property_ids={"BEVCENTER"})
    assert registry.entries == []


def test_coverage_gaps(tmp_path):
    reg = _write(
        tmp_path,
        "registry.yaml",
        """
        sources:
          - property_id: BEVCENTER
            type: socrata
            base_url: https://x
            dataset_id: abcd-1234
            date_field: d
            crime_type_field: c
        """,
    )
    registry = load_registry(reg, valid_property_ids={"BEVCENTER"})
    gaps = registry.malls_without_sources({"BEVCENTER", "LENOX"})
    assert gaps == {"LENOX"}


def test_load_settings_defaults(tmp_path):
    s = _write(tmp_path, "settings.yaml", "recency_window_days: 14\n")
    settings = load_settings(s)
    assert settings.recency_window_days == 14
    assert settings.radius_m == 1000  # default
