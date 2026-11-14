"""Coverage matrix: indicator x unit, with honest empty cells."""

from equal_path.coverage import AREA_ONLY, NONE, SUPPRESSED, VALUE, coverage_matrix
from equal_path.spine import make_observations

UNITS = {"08": "Pirkanmaa", "90": "Helsinki", "20": "Kainuu"}
CATALOG = ["a", "b", "c", "d"]


def _row(**kw):
    base = dict(geo_level="unit", county_id="08", indicator_id="a", period="2024", subgroup="all", value=0.5,
                numerator=None, denominator=None, quality_flag="", source_id="S", locator="")
    return {**base, **kw}


def test_cells_distinguish_value_area_suppressed_and_none():
    store = make_observations([
        _row(),  # a: Pirkanmaa has a value
        _row(county_id="90", value=None, quality_flag="suppressed"),  # a: Helsinki suppressed
        _row(indicator_id="b", geo_level="cooperation_area", county_id="YTA3"),  # b: area level only
        _row(indicator_id="c", subgroup="lang:other", county_id="20"),  # c: subgroup-only still counts as a value
    ])
    matrix = coverage_matrix(store, CATALOG, UNITS)
    assert list(matrix.columns) == ["Pirkanmaa", "Helsinki", "Kainuu"]
    assert matrix.loc["a"].tolist() == [VALUE, SUPPRESSED, NONE]
    assert matrix.loc["b"].tolist() == [AREA_ONLY] * 3
    assert matrix.loc["c"].tolist() == [NONE, NONE, VALUE]
    assert matrix.loc["d"].tolist() == [NONE] * 3  # catalogued but no data: a visible gap


def test_value_wins_over_suppressed_across_periods():
    store = make_observations([
        _row(period="2023", value=None, quality_flag="suppressed"),
        _row(period="2024"),
    ])
    assert coverage_matrix(store, ["a"], UNITS).loc["a", "Pirkanmaa"] == VALUE


def test_empty_store_is_all_gaps():
    matrix = coverage_matrix(make_observations([]), CATALOG, UNITS)
    assert (matrix == NONE).all().all() and matrix.shape == (4, 3)
