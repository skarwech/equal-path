"""F0 gate: 10 randomly drawn cells were checked against the publishers' live pages."""


import pandas as pd
import pytest

from equal_path.observations import load_observations
from equal_path.paths import EVIDENCE_DIR, ROOT

SAMPLE = EVIDENCE_DIR / "spotcheck_sample.csv"


@pytest.fixture(scope="module")
def sample():
    return pd.read_csv(SAMPLE, dtype={"county_id": str, "period": str, "subgroup": str})


def test_ten_cells_all_match_with_screenshots(sample):
    assert len(sample) == 10 and sample.seed.nunique() == 1
    assert (sample.result == "match").all()
    for shot in sample.screenshot:
        assert (ROOT / shot).is_file(), shot


def test_sample_still_matches_the_store(sample):
    """If the store changes, the spot-check is stale and must be redone."""
    store = load_observations().set_index(["geo_level", "county_id", "indicator_id", "period", "subgroup"])
    for row in sample.itertuples():
        current = store.loc[(row.geo_level, row.county_id, row.indicator_id, row.period, row.subgroup), "value"]
        assert current == pytest.approx(row.value), row.check_id


def test_sample_spans_five_publishers(sample):
    assert sample.source_id.nunique() == 5


def test_live_numbers_equal_store_values(sample):
    assert sample.live_value_num.notna().all()
    for row in sample.itertuples():
        assert row.live_value_num == pytest.approx(row.value), row.check_id


def test_screenshots_unchanged_since_check(sample):
    import hashlib

    for row in sample.itertuples():
        assert hashlib.sha256((ROOT / row.screenshot).read_bytes()).hexdigest() == row.screenshot_sha256, row.check_id
