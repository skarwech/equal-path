"""F0 gate on the REAL store: schema, provenance, coverage honesty and reconciliation."""

import pytest

from equal_path.config import load_anchors, load_indicator_catalog, load_thresholds
from equal_path.geography import UNIT_CODES
from equal_path.observations import load_observations, reconcile_anchors
from equal_path.sources import source_ids
from equal_path.spine import validate_observations


@pytest.fixture(scope="module")
def store():
    return load_observations()


@pytest.fixture(scope="module")
def catalog():
    return {i.id: i for i in load_indicator_catalog()}


def test_store_exists_and_is_valid(store, catalog):
    assert not store.empty
    problems = validate_observations(
        store, catalog={k: v.model_dump() for k, v in catalog.items()}, unit_codes=UNIT_CODES, source_ids=source_ids()
    )
    assert problems == []


def test_catalog_status_matches_store(store, catalog):
    """available = all 22 units have a value; partial = values only above unit level; else none."""
    from equal_path.observations import status_problems

    assert status_problems(store, catalog.values()) == []


def test_unit_rows_cover_exactly_the_22_units(store):
    units = store[store.geo_level == "unit"]
    assert set(units.county_id) == set(UNIT_CODES)


def test_at_least_one_goal3_linked_indicator_has_unit_values(store, catalog):
    goal3 = {i.id for i in catalog.values() if i.goal3_link}
    units = store[(store.geo_level == "unit") & store.value.notna()]
    assert goal3 & set(units.indicator_id)


EXPECTED_STATUS = {
    "new_cancers_2024": "pass", "cancer_deaths_2024": "pass", "stage_coverage_national": "pass",
    "screening_cancers_found_2024": "pass", "screening_precursors_found_2024": "pass", "lung_curative_route_share": "pass",
    "stage_coverage_pirkanmaa": "pass", "stage_coverage_sisa_suomi": "pass",
    "stage_coverage_other_areas": "not_checked", "screening_participation_lowest": "pass",
    "lung_stage_missing_share": "not_checked",
}


def test_every_anchor_has_its_expected_status(store):
    results = reconcile_anchors(store, load_anchors(), load_thresholds())
    assert {r.anchor_id: r.status for r in results} == EXPECTED_STATUS


def test_every_raw_file_has_a_manifest_entry():
    import json

    from equal_path.paths import DATA_DIR

    for manifest in (DATA_DIR / "raw").glob("*/manifest.json"):
        entries = {e["file"] for e in json.loads(manifest.read_text(encoding="utf-8"))}
        files = {p.name for p in manifest.parent.iterdir() if p.name != "manifest.json"}
        assert files == entries, manifest.parent.name
