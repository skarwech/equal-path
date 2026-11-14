"""Indicator counts per unit come from the observations store, never from hard-coded text."""

from equal_path.observations import indicator_counts
from equal_path.spine import make_observations


def _row(**kw):
    base = dict(geo_level="unit", county_id="08", indicator_id="a", period="2024", subgroup="all", value=0.5,
                numerator=None, denominator=None, quality_flag="", source_id="S", locator="")
    return {**base, **kw}


def test_no_store_means_no_indicators(tmp_path):
    assert indicator_counts(tmp_path / "absent.parquet") == {}


def test_counts_distinct_unit_indicators_with_values(tmp_path):
    store = tmp_path / "obs.parquet"
    make_observations([
        _row(indicator_id="a", period="2023"), _row(indicator_id="a", period="2024"), _row(indicator_id="b"),
        _row(county_id="90", indicator_id="b"),
        _row(county_id="90", indicator_id="c", value=None, quality_flag="suppressed"),  # no value: not loaded
        _row(geo_level="cooperation_area", county_id="YTA3", indicator_id="d"),  # area rows never count for a unit
    ]).to_parquet(store)
    assert indicator_counts(store) == {"08": 2, "90": 1}


def test_status_problems_flags_partial_unit_coverage():
    from types import SimpleNamespace

    from equal_path.observations import status_problems

    rows = [_row(county_id=code, indicator_id="a") for code in [f"{i:02d}" for i in range(1, 21)]]  # 20 units only
    frame = make_observations(rows)
    catalog = [SimpleNamespace(id="a", status="available"), SimpleNamespace(id="b", status="not_public")]
    problems = status_problems(frame, catalog)
    assert any("a" in p and "20 of 22" in p for p in problems)


def test_status_problems_flags_values_for_not_public():
    from types import SimpleNamespace

    from equal_path.observations import status_problems

    frame = make_observations([_row(geo_level="national", county_id="FI", indicator_id="b")])
    problems = status_problems(frame, [SimpleNamespace(id="b", status="not_public")])
    assert any("not_public" in p for p in problems)
