"""Data spine (F0) logic on synthetic fixtures: schema validation and reconciliation."""

import math

import pandas as pd
import pytest

from equal_path.spine import (
    OBS_COLUMNS,
    ReconcileSpec,
    make_observations,
    parse_fi_number,
    reconcile_one,
    validate_observations,
)

UNITS = [f"{i:02d}" for i in range(1, 22)] + ["90"]
CATALOG = {
    "new_cases": {"unit": "count", "stage": "context", "source_ids": ("S_TEST",)},
    "screening_participation_breast": {"unit": "share", "stage": "detection", "source_ids": ("S_TEST",)},
    "survival": {"unit": "ratio", "stage": "treatment", "source_ids": ("S_TEST",)},
}
SOURCES_EXTRA = {"S_OTHER"}
SOURCES = {"S_TEST"}


def _rows(**overrides):
    base = {
        "geo_level": "unit",
        "county_id": "08",
        "indicator_id": "screening_participation_breast",
        "period": "2024",
        "subgroup": "all",
        "value": 0.8,
        "numerator": 800.0,
        "denominator": 1000.0,
        "quality_flag": "",
        "source_id": "S_TEST",
        "locator": "table 1",
        "ci_low": None,
        "ci_high": None,
    }
    return {**base, **overrides}


def _frame(*rows):
    return make_observations([_rows(**r) for r in rows])


def _problems(frame):
    return validate_observations(frame, catalog=CATALOG, unit_codes=UNITS, source_ids=SOURCES)


def test_columns_contract():
    assert tuple(_frame({}).columns) == OBS_COLUMNS
    assert OBS_COLUMNS[:2] == ("geo_level", "county_id")


def test_valid_frame_has_no_problems():
    assert _problems(_frame({}, {"county_id": "90", "value": 0.6, "numerator": 600.0})) == []


@pytest.mark.parametrize(
    "override,fragment",
    [
        ({"source_id": "S_NOPE"}, "source_id"),
        ({"indicator_id": "mystery"}, "indicator"),
        ({"county_id": "91"}, "unit code"),
        ({"geo_level": "planet"}, "geo_level"),
        ({"period": ""}, "period"),
        ({"numerator": 1200.0}, "numerator"),
        ({"denominator": 0.0}, "denominator"),
        ({"value": 80.0, "numerator": None, "denominator": None}, "0-1"),
        ({"value": 0.5}, "numerator/denominator"),
        ({"quality_flag": "imputed"}, "quality_flag"),
        ({"value": None, "quality_flag": ""}, "missing value"),
        ({"ci_low": 0.85, "ci_high": 0.9}, "confidence interval"),
        ({"ci_low": 0.7, "ci_high": None}, "confidence interval"),
        ({"indicator_id": "survival", "value": 92.1, "ci_low": 90.8, "ci_high": 93.3, "numerator": None, "denominator": None}, "ratio"),
        ({"indicator_id": "new_cases", "value": -3.0, "numerator": None, "denominator": None}, "negative"),
        ({"indicator_id": "new_cases", "value": float("inf"), "numerator": None, "denominator": None}, "finite"),
        ({"period": "None"}, "period"),
        ({"period": "24"}, "period"),
        ({"value": 0.8, "quality_flag": "suppressed"}, "flagged"),
        ({"subgroup": "???"}, "subgroup"),
        ({"subgroup": ""}, "subgroup"),
        ({"locator": ""}, "locator"),
        ({"denominator": None}, "both"),
    ],
)
def test_each_violation_is_reported(override, fragment):
    problems = _problems(_frame(override))
    assert any(fragment in p for p in problems), problems


def test_duplicate_key_is_reported():
    problems = _problems(_frame({}, {}))
    assert any("duplicate" in p for p in problems)


def test_same_unit_different_subgroup_is_not_duplicate():
    assert _problems(_frame({}, {"subgroup": "lang:other"})) == []


def test_missing_value_allowed_only_when_flagged():
    assert _problems(_frame({"value": None, "numerator": None, "denominator": None, "quality_flag": "suppressed"})) == []


def test_area_rows_use_area_codes():
    assert _problems(_frame({"geo_level": "cooperation_area", "county_id": "YTA3"})) == []
    assert _problems(_frame({"geo_level": "cooperation_area", "county_id": "08"}))


def test_reconciliation_only_rows_allowed():
    frame = _frame(
        {"geo_level": "excluded_unit", "county_id": "91"},
        {"geo_level": "unknown_residence", "county_id": "UNK"},
        {"geo_level": "national", "county_id": "FI"},
    )
    assert _problems(frame) == []


# ---------------------------------------------------------------- reconciliation


def _counts(values, extra=()):
    rows = [
        {"county_id": code, "indicator_id": "new_cases", "value": float(v), "numerator": None, "denominator": None}
        for code, v in zip(UNITS, values)
    ]
    rows += list(extra)
    return _frame(*rows)


def test_sum_includes_aland_and_unknown_and_passes_within_tolerance():
    frame = _counts(
        [100] * 22,
        extra=[
            {"geo_level": "excluded_unit", "county_id": "91", "indicator_id": "new_cases", "value": 10.0, "numerator": None, "denominator": None},
            {"geo_level": "unknown_residence", "county_id": "UNK", "indicator_id": "new_cases", "value": 5.0, "numerator": None, "denominator": None},
        ],
    )
    spec = ReconcileSpec(indicator_id="new_cases", period="2024", method="sum")
    result = reconcile_one(frame, spec, published=2215.0, counts_rel_tol=0.01, pct_abs_tol_pp=0.5)
    assert result.computed == 2215.0 and result.status == "pass"


def test_sum_outside_tolerance_fails_and_is_never_forced():
    frame = _counts([100] * 22)
    spec = ReconcileSpec(indicator_id="new_cases", period="2024", method="sum")
    result = reconcile_one(frame, spec, published=2300.0, counts_rel_tol=0.01, pct_abs_tol_pp=0.5)
    assert result.status == "fail" and math.isclose(result.diff, -100.0)


def test_weighted_share_uses_denominators_not_mean_of_shares():
    rows = [{"county_id": "01", "value": 0.9, "numerator": 900.0, "denominator": 1000.0}]
    rows += [{"county_id": code, "value": 0.5, "numerator": 50.0, "denominator": 100.0} for code in UNITS[1:]]
    frame = _frame(*rows)
    spec = ReconcileSpec(indicator_id="screening_participation_breast", period="2024", method="weighted_share", unit="share")
    weighted = 1950 / 3100  # 0.629; the mean of shares would be 0.518
    result = reconcile_one(frame, spec, published=weighted, counts_rel_tol=0.01, pct_abs_tol_pp=0.5)
    assert result.status == "pass" and math.isclose(result.computed, weighted)
    mean_of_shares = (0.9 + 21 * 0.5) / 22
    assert reconcile_one(frame, spec, published=mean_of_shares, counts_rel_tol=0.01, pct_abs_tol_pp=0.5).status == "fail"


def test_weighted_share_without_denominators_is_not_reconcilable():
    frame = _frame({"county_id": "01", "value": 0.9, "numerator": None, "denominator": None})
    spec = ReconcileSpec(indicator_id="screening_participation_breast", period="2024", method="weighted_share", unit="share")
    result = reconcile_one(frame, spec, published=0.9, counts_rel_tol=0.01, pct_abs_tol_pp=0.5)
    assert result.status == "not_reconcilable"


def test_direct_national_row():
    frame = _frame({"geo_level": "national", "county_id": "FI", "value": 0.423, "numerator": None, "denominator": None})
    spec = ReconcileSpec(indicator_id="screening_participation_breast", period="2024", method="direct", unit="share")
    assert reconcile_one(frame, spec, published=0.42, counts_rel_tol=0.01, pct_abs_tol_pp=0.5).status == "pass"
    assert reconcile_one(frame, spec, published=0.40, counts_rel_tol=0.01, pct_abs_tol_pp=0.5).status == "fail"


def test_no_rows_means_no_data_not_pass():
    spec = ReconcileSpec(indicator_id="new_cases", period="2099", method="sum")
    assert reconcile_one(_counts([1] * 22), spec, published=22.0, counts_rel_tol=0.01, pct_abs_tol_pp=0.5).status == "no_data"


def test_sum_with_a_missing_unit_is_incomplete():
    frame = _counts([100] * 21)  # zip stops at 21 values: Helsinki missing
    spec = ReconcileSpec(indicator_id="new_cases", period="2024", method="sum")
    result = reconcile_one(frame, spec, published=2100.0, counts_rel_tol=0.01, pct_abs_tol_pp=0.5)
    assert result.status == "incomplete"


# ---------------------------------------------------------------- Finnish number parsing


@pytest.mark.parametrize(
    "text,expected",
    [("2 360", 2360.0), ("2 360", 2360.0), ("67,8", 67.8), ("67,8 %", 67.8), ("−1,5", -1.5), ("38853", 38853.0)],
)
def test_parse_fi_number(text, expected):
    assert parse_fi_number(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["", "..", "-", "x", "n/a", None])
def test_parse_fi_number_missing_markers(text):
    assert parse_fi_number(text) is None


@pytest.mark.parametrize("text,expected", [("2\u2009360", 2360.0), ("2\u202f360", 2360.0), ("71,9 %", 71.9)])
def test_parse_fi_number_thin_spaces(text, expected):
    assert parse_fi_number(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["<5", "ca. 20", "12e3", "nan", "inf", "1_000", "١٢"])
def test_parse_fi_number_rejects_unexpected_tokens(text):
    with pytest.raises(ValueError):
        parse_fi_number(text)


def test_direct_count_uses_relative_tolerance():
    frame = _frame({"geo_level": "national", "county_id": "FI", "indicator_id": "new_cases", "value": 38900.0, "numerator": None, "denominator": None})
    spec = ReconcileSpec(indicator_id="new_cases", period="2024", method="direct", unit="count")
    assert reconcile_one(frame, spec, published=38853.0, counts_rel_tol=0.01, pct_abs_tol_pp=0.5).status == "pass"
    assert reconcile_one(frame, spec, published=30000.0, counts_rel_tol=0.01, pct_abs_tol_pp=0.5).status == "fail"


def test_spec_rejects_unknown_method():
    with pytest.raises(ValueError):
        ReconcileSpec(indicator_id="x", period="2024", method="average", unit="share")


def test_ratio_may_exceed_one_with_ci():
    row = {"indicator_id": "survival", "value": 0.98, "ci_low": 0.92, "ci_high": 1.042, "numerator": None, "denominator": None}
    assert _problems(_frame(row)) == []


def test_sum_across_all_subgroups():
    rows = []
    for subgroup, value in (("prog:breast", 10.0), ("prog:colorectal", 3.0)):
        rows += [
            {"county_id": code, "indicator_id": "new_cases", "subgroup": subgroup, "value": value, "numerator": None, "denominator": None}
            for code in UNITS
        ]
    spec = ReconcileSpec(indicator_id="new_cases", period="2024", method="sum", subgroup="*",
                         expected_subgroups=("prog:breast", "prog:colorectal"))
    result = reconcile_one(_frame(*rows), spec, published=22 * 13.0, counts_rel_tol=0.01, pct_abs_tol_pp=0.5)
    assert result.status == "pass" and result.computed == 22 * 13.0


def test_sum_across_subgroups_requires_each_subgroup_complete():
    rows = [{"county_id": code, "indicator_id": "new_cases", "subgroup": "prog:breast", "value": 1.0, "numerator": None, "denominator": None} for code in UNITS]
    rows += [{"county_id": "01", "indicator_id": "new_cases", "subgroup": "prog:colorectal", "value": 1.0, "numerator": None, "denominator": None}]
    spec = ReconcileSpec(indicator_id="new_cases", period="2024", method="sum", subgroup="*",
                         expected_subgroups=("prog:breast", "prog:colorectal"))
    assert reconcile_one(_frame(*rows), spec, published=23.0, counts_rel_tol=0.01, pct_abs_tol_pp=0.5).status == "incomplete"


def test_source_must_be_listed_for_the_indicator():
    problems = validate_observations(_frame({"source_id": "S_OTHER"}), catalog=CATALOG, unit_codes=UNITS, source_ids=SOURCES | SOURCES_EXTRA)
    assert any("not a listed source" in p for p in problems)


def test_star_requires_expected_subgroups():
    with pytest.raises(ValueError):
        ReconcileSpec(indicator_id="new_cases", period="2024", method="sum", subgroup="*")


def test_sum_of_shares_is_rejected():
    with pytest.raises(ValueError):
        ReconcileSpec(indicator_id="x", period="2024", method="sum", unit="share")


def _programmes(*subgroups):
    rows = []
    for subgroup in subgroups:
        rows += [{"county_id": code, "indicator_id": "new_cases", "subgroup": subgroup, "value": 5.0, "numerator": None, "denominator": None} for code in UNITS]
    return _frame(*rows)


def test_missing_whole_subgroup_is_incomplete_not_pass():
    spec = ReconcileSpec(indicator_id="new_cases", period="2024", method="sum", subgroup="*",
                         expected_subgroups=("prog:a", "prog:b", "prog:c"))
    frame = _programmes("prog:a", "prog:b")  # prog:c entirely absent, sum still within 1 %? make it so:
    result = reconcile_one(frame, spec, published=220.0, counts_rel_tol=0.6, pct_abs_tol_pp=0.5)
    assert result.status == "incomplete" and "prog:c" in result.detail


def test_unexpected_subgroup_is_incomplete():
    spec = ReconcileSpec(indicator_id="new_cases", period="2024", method="sum", subgroup="*", expected_subgroups=("prog:a",))
    result = reconcile_one(_programmes("prog:a", "prog:z"), spec, published=110.0, counts_rel_tol=0.01, pct_abs_tol_pp=0.5)
    assert result.status == "incomplete"


def test_duplicated_rows_are_incomplete_not_double_counted():
    frame = _counts([100] * 22)
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    spec = ReconcileSpec(indicator_id="new_cases", period="2024", method="sum")
    assert reconcile_one(frame, spec, published=2200.0, counts_rel_tol=0.01, pct_abs_tol_pp=0.5).status == "incomplete"


def test_direct_requires_exactly_one_national_row():
    row = {"geo_level": "national", "county_id": "FI", "value": 0.42, "numerator": None, "denominator": None}
    frame = _frame(row, {**row, "subgroup": "lang:other"})
    frame.loc[1, "subgroup"] = "all"  # force a duplicate national row
    spec = ReconcileSpec(indicator_id="screening_participation_breast", period="2024", method="direct", unit="share")
    assert reconcile_one(frame, spec, published=0.42, counts_rel_tol=0.01, pct_abs_tol_pp=0.5).status == "incomplete"


def test_sum_reports_source_national_residual():
    frame = _counts([100] * 22, extra=[{"geo_level": "national", "county_id": "FI", "indicator_id": "new_cases", "value": 2210.0, "numerator": None, "denominator": None}])
    spec = ReconcileSpec(indicator_id="new_cases", period="2024", method="sum")
    result = reconcile_one(frame, spec, published=2210.0, counts_rel_tol=0.01, pct_abs_tol_pp=0.5)
    assert result.status == "pass" and "residual 10" in result.detail


def test_sum_fails_when_source_national_row_disagrees_with_anchor():
    frame = _counts([100] * 22, extra=[{"geo_level": "national", "county_id": "FI", "indicator_id": "new_cases", "value": 2205.0, "numerator": None, "denominator": None}])
    spec = ReconcileSpec(indicator_id="new_cases", period="2024", method="sum")
    result = reconcile_one(frame, spec, published=2210.0, counts_rel_tol=0.01, pct_abs_tol_pp=0.5)
    assert result.status == "fail" and "national" in result.detail
