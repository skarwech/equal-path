"""F1 visibility score on synthetic fixtures: weights, range, monotonicity, observability rules."""

import itertools

import pandas as pd
import pytest

from equal_path.spine import make_observations
from equal_path.visibility import observable_matrix, stage_members, visibility_scores, within_stage_weights

UNITS = ("01", "02", "03")
CATALOG = {
    "det_a": {"stage": "detection", "status": "available", "source_ids": ("S",)},
    "det_b": {"stage": "detection", "status": "available", "source_ids": ("S",)},
    "ref_a": {"stage": "referral", "status": "available", "source_ids": ("S",)},
    "dia_a": {"stage": "diagnosis", "status": "partial", "source_ids": ("S",)},
    "trt_a": {"stage": "treatment", "status": "available", "source_ids": ("S",)},
    "trt_b": {"stage": "treatment", "status": "not_public", "source_ids": ("S",)},
    "tim_a": {"stage": "timing", "status": "not_public", "source_ids": ("S",)},
    "cov_a": {"stage": "covariate", "status": "available", "source_ids": ("S",)},
}
REGISTRY = {"S": "retrieved", "S_FAKE": "to_verify"}
WEIGHTS = {"detection": 0.25, "referral": 0.25, "diagnosis": 0.25, "treatment": 0.25}


def _row(code, indicator, value=0.5, period="2024", subgroup="all", den=None, num=None, source="S", flag="", geo="unit"):
    return dict(geo_level=geo, county_id=code, indicator_id=indicator, period=period, subgroup=subgroup, value=value,
                numerator=num, denominator=den, quality_flag=flag, source_id=source, locator="x", ci_low=None, ci_high=None)


def _store(rows):
    return make_observations(rows)


def _full_rows():
    rows = []
    for code in UNITS:
        rows += [_row(code, "det_a"), _row(code, "det_b"), _row(code, "ref_a"), _row(code, "trt_a"), _row(code, "cov_a")]
    return rows


def test_members_come_from_catalog_stage_and_exclude_covariates():
    members = stage_members(CATALOG)
    assert members == {"detection": ("det_a", "det_b"), "referral": ("ref_a",), "diagnosis": ("dia_a",),
                       "treatment": ("trt_a", "trt_b"), "timing": ("tim_a",)}


def test_within_stage_weights_sum_to_one():
    for stage, weights in within_stage_weights(stage_members(CATALOG)).items():
        assert sum(weights.values()) == pytest.approx(1.0), stage


def test_hand_calculated_scores():
    obs = observable_matrix(_store(_full_rows()), CATALOG, UNITS, min_denominator=30, registry=REGISTRY)
    scores = visibility_scores(obs, stage_members(CATALOG), WEIGHTS)
    row = scores.loc["01"]
    # detection 2/2, referral 1/1, diagnosis 0/1, treatment 1/2 -> 25*(1+1+0+0.5) = 62.5
    assert (row.detection, row.referral, row.diagnosis, row.treatment, row.timing) == (1.0, 1.0, 0.0, 0.5, 0.0)
    assert row.score == pytest.approx(62.5, abs=1e-9)


def test_scores_stay_in_range_for_every_observability_pattern():
    members = stage_members(CATALOG)
    indicators = [i for stage in members.values() for i in stage]
    for pattern in itertools.product([False, True], repeat=len(indicators)):
        obs = pd.DataFrame([dict(zip(indicators, pattern))], index=["01"])
        score = visibility_scores(obs, members, WEIGHTS).loc["01", "score"]
        assert 0.0 <= score <= 100.0


def test_monotonic_adding_an_observable_indicator_never_lowers_score():
    members = stage_members(CATALOG)
    indicators = [i for stage in members.values() for i in stage]
    for pattern in itertools.product([False, True], repeat=len(indicators)):
        base = pd.DataFrame([dict(zip(indicators, pattern))], index=["01"])
        before = visibility_scores(base, members, WEIGHTS).loc["01", "score"]
        for indicator in indicators:
            more = base.copy()
            more[indicator] = True
            assert visibility_scores(more, members, WEIGHTS).loc["01", "score"] >= before - 1e-12


def test_small_denominator_and_suppressed_cells_are_not_observable():
    rows = _full_rows()
    rows = [r for r in rows if not (r["county_id"] == "02" and r["indicator_id"] in ("det_a", "det_b"))]
    rows += [_row("02", "det_a", den=12, num=6), _row("02", "det_b", value=None, flag="suppressed")]
    obs = observable_matrix(_store(rows), CATALOG, UNITS, min_denominator=30, registry=REGISTRY)
    assert not obs.loc["02", "det_a"] and not obs.loc["02", "det_b"]
    assert obs.loc["01", "det_a"] and obs.loc["01", "det_b"]


def test_only_latest_period_and_headline_subgroup_count():
    rows = [r for r in _full_rows() if not (r["county_id"] == "03" and r["indicator_id"] == "det_a")]
    rows += [_row("03", "det_a", period="2020"), _row("03", "det_a", subgroup="lang:other")]
    obs = observable_matrix(_store(rows), CATALOG, UNITS, min_denominator=30, registry=REGISTRY)
    assert not obs.loc["03", "det_a"]  # 2024 headline value missing: older year / subgroup do not count


def test_area_rows_never_make_a_unit_observable():
    rows = _full_rows() + [_row("YTA1", "dia_a", geo="cooperation_area")]
    obs = observable_matrix(_store(rows), CATALOG, UNITS, min_denominator=30, registry=REGISTRY)
    assert not obs["dia_a"].any()


def test_injected_rows_for_not_public_or_unlisted_sources_stay_dark():
    rows = _full_rows()
    rows += [_row(code, "tim_a") for code in UNITS]                    # catalog says not_public
    rows += [_row(code, "dia_a", source="S_FAKE") for code in UNITS]   # source not listed / not retrieved
    obs = observable_matrix(_store(rows), CATALOG, UNITS, min_denominator=30, registry=REGISTRY)
    assert not obs["tim_a"].any() and not obs["dia_a"].any()
    scores = visibility_scores(obs, stage_members(CATALOG), WEIGHTS)
    assert (scores.timing == 0).all() and (scores.diagnosis == 0).all()


def test_all_missing_newer_period_does_not_blank_the_latest_real_one():
    rows = _full_rows() + [_row(code, "det_a", period="2025", value=None, flag="suppressed") for code in UNITS]
    obs = observable_matrix(_store(rows), CATALOG, UNITS, min_denominator=30, registry=REGISTRY)
    assert obs["det_a"].all()  # 2024 still counts: 2025 has no values at all
