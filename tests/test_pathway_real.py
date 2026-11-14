"""F1 + F2 on the REAL store: hand-calculated counties (literals), dark timing, bug detectors."""

import pytest

from equal_path.pathway import run_pathway

DET = 6 / 7          # detection: 7 catalogued, 'breast cancers below screening age' not public
REF = 1.0            # referral: primary-care waits
TRT = 2 / 4          # treatment: curative share + survival observable; first-line mix + RT distance not
SCORE = 25 * (DET + REF + 0.0 + TRT)


@pytest.fixture(scope="module")
def result():
    return run_pathway()


@pytest.mark.parametrize(
    "code,diagnosis,score",
    [
        ("90", 0.0, SCORE),                       # Helsinki
        ("20", 0.0, SCORE),                       # Kainuu
        ("08", 1 / 3, SCORE + 25 * (1 / 3)),      # Pirkanmaa: stage coverage published (71.9 %)
    ],
)
def test_hand_calculated_visibility(result, code, diagnosis, score):
    row = result.visibility.loc[code]
    assert row.detection == pytest.approx(DET, abs=1e-6)
    assert row.referral == pytest.approx(REF, abs=1e-6)
    assert row.diagnosis == pytest.approx(diagnosis, abs=1e-6)
    assert row.treatment == pytest.approx(TRT, abs=1e-6)
    assert row.timing == 0.0
    assert row.score == pytest.approx(score, abs=1e-6)


def test_injected_timing_values_leave_the_stage_dark():
    from equal_path.observations import load_observations
    from equal_path.spine import make_observations
    import pandas as pd

    store = load_observations()
    fake = make_observations([
        dict(geo_level="unit", county_id=code, indicator_id="access_referral_to_first_treatment", period="2025",
             subgroup="all", value=5.0, numerator=None, denominator=None, quality_flag="",
             source_id="S_THL_OHJAUS_21_2016", locator="synthetic", ci_low=None, ci_high=None)
        for code in store[store.geo_level == "unit"].county_id.unique()
    ])
    injected = run_pathway(store=pd.concat([store, fake], ignore_index=True))
    assert (injected.visibility.timing == 0).all()
    assert (injected.stages.timing == "unknown").all()


def test_only_pirkanmaa_reaches_the_stage_coverage_target(result):
    tiers = result.coverage_tiers
    assert tiers["08"] == "target"
    assert {tier for code, tier in tiers.items() if code != "08"} == {"not published"}


def test_every_unit_has_all_stage_states(result):
    assert len(result.stages) == 22
    assert set(result.stages.columns) == {"detection", "referral", "diagnosis", "treatment", "timing"}
    assert (result.stages.timing == "unknown").all()
    assert set(result.stages.diagnosis) <= {"unknown", "watch"}  # visibility < 0.5 everywhere: never Leak


def test_helsinki_detection_is_behind_national(result):
    """Spec bug detector: the registry singles out Helsinki as clearly behind on participation."""
    rows = result.assessments
    helsinki = rows[(rows.code == "90") & (rows.indicator_id == "screening_participation_breast")].iloc[0]
    assert helsinki.gap_national > 0.03
    assert result.stages.loc["90", "detection"] in ("leak", "watch")


@pytest.mark.parametrize("code", ["16", "12", "20"])  # Etelä-Pohjanmaa, Etelä-Savo, Kainuu
def test_top_participation_counties_have_no_breast_participation_leak(result, code):
    rows = result.assessments
    row = rows[(rows.code == code) & (rows.indicator_id == "screening_participation_breast")].iloc[0]
    assert row.state != "leak"


def test_lung_curative_share_varies_between_counties(result):
    rows = result.assessments[result.assessments.indicator_id == "lung_curative_route_share"]
    assert rows.value.nunique() > 10 and rows.value.min() < 0.22 and rows.value.max() > 0.33


def test_survival_produces_almost_no_leaks(result):
    """The registry reports no significant county differences; many leaks would mean a bug."""
    rows = result.assessments[result.assessments.indicator_id == "survival_5y_relative"]
    assert (rows.state == "leak").sum() <= 2


def test_hpv_and_primary_care_can_only_watch(result):
    rows = result.assessments[result.assessments.indicator_id.isin(["hpv_vaccination_coverage", "primary_care_access"])]
    assert "leak" not in set(rows.state)


def test_primary_leak_names_a_leaking_stage_or_says_why_not(result):
    for code, text in result.primary_leak.items():
        stage = text.split(":")[0]
        if stage in ("detection", "referral", "diagnosis", "treatment"):
            assert result.stages.loc[code, stage] == "leak"
        else:
            assert text in ("no verified leak", "cannot localise; the data gap is the finding")


def test_twin_sets_cover_all_units_and_exclude_self(result):
    assert len(result.twins) == 22
    for code, twins in result.twins.items():
        assert code not in twins.twins and len(twins.twins) == 3


def test_primary_finding_ranks_by_verified_gap():
    """Verified gap = the smaller of the gaps under the references used."""
    import pandas as pd

    from equal_path.pathway import _primary

    stages = pd.Series({"detection": "leak", "referral": "ok", "diagnosis": "unknown", "treatment": "leak", "timing": "unknown"})
    rows = pd.DataFrame([
        dict(code="X", stage="detection", indicator_id="a", subgroup="all", state="leak", gap_national=0.10, gap_twin=0.04),
        dict(code="X", stage="treatment", indicator_id="b", subgroup="all", state="leak", gap_national=0.06, gap_twin=0.06),
    ])
    assert _primary("X", stages, rows).startswith("treatment: b")


def test_primary_finding_only_from_stages_that_are_leak():
    import pandas as pd

    from equal_path.pathway import _primary

    stages = pd.Series({"detection": "leak", "referral": "ok", "diagnosis": "unknown", "treatment": "watch", "timing": "unknown"})
    rows = pd.DataFrame([
        dict(code="X", stage="detection", indicator_id="a", subgroup="all", state="leak", gap_national=0.04, gap_twin=0.04),
        dict(code="X", stage="treatment", indicator_id="b", subgroup="all", state="leak", gap_national=0.11, gap_twin=0.11),
    ])  # treatment was downgraded to Watch by the visibility gate: it must not be named
    assert _primary("X", stages, rows).startswith("detection: a")


def test_f2_only_assesses_units_f1_finds_observable():
    from equal_path.config import load_indicator_catalog
    from equal_path.observations import load_observations
    from equal_path.pathway import eligible_series
    from equal_path.visibility import stage_members
    import pandas as pd

    catalog = {i.id: i for i in load_indicator_catalog()}
    members = stage_members(catalog)
    codes = [f"{i:02d}" for i in range(1, 22)] + ["90"]
    dark = pd.DataFrame(False, index=codes, columns=[i for ids in members.values() for i in ids])
    assert all(not s.values for s in eligible_series(load_observations(), catalog, dark))


def test_stage_level_false_leak_rate_on_real_stage_mix_at_most_5_percent():
    """1000 pure-noise draws with real denominators, real published CI widths and real twins."""
    import numpy as np

    from equal_path.config import load_indicator_catalog, load_thresholds
    from equal_path.gaps import SeriesInput, assess_series, stage_state
    from equal_path.observations import load_observations
    from equal_path.pathway import eligible_series, stage_z

    t, store = load_thresholds(), load_observations()
    catalog = {i.id: i for i in load_indicator_catalog()}
    result = run_pathway()
    twins = {c: x.twins for c, x in result.twins.items()}
    good = {c: x.good for c, x in result.twins.items()}
    series = [s for s in eligible_series(store, catalog, result.observable) if s.denominators or s.ci]
    z_by_stage = stage_z(series, t.wilson_z)
    rng = np.random.default_rng(20261114)
    leaks = {}
    for _ in range(1000):
        states = {}
        for s in series:
            if s.denominators:
                p0 = sum(s.values[c] * s.denominators[c] for c in s.denominators) / sum(s.denominators.values())
                vals = {c: rng.binomial(int(s.denominators[c]), p0) / s.denominators[c] for c in s.values}
                noisy = SeriesInput(s.indicator_id, s.subgroup, s.stage, s.direction, vals, s.denominators, {}, None, s.period, s.unit)
            else:
                vals, ci = {}, {}
                for c, (lo, hi) in s.ci.items():
                    se = (hi - lo) / (2 * 1.96)
                    v = rng.normal(s.national, se)
                    vals[c], ci[c] = v, (v - 1.96 * se, v + 1.96 * se)
                noisy = SeriesInput(s.indicator_id, s.subgroup, s.stage, s.direction, vals, {}, ci, s.national, s.period, s.unit)
            for c, a in assess_series(noisy, twins, good, z_by_stage[s.stage], t.min_practical_gap_pp, t.min_denominator).items():
                states.setdefault((c, s.stage), []).append(a.state)
        for key, cell in states.items():
            leaks[key] = leaks.get(key, 0) + (stage_state(1.0, cell, 0.5) == "leak")
    assert max(leaks.values()) / 1000 <= 0.05


def test_run_pathway_passes_the_stage_adjusted_z(monkeypatch):
    import equal_path.pathway as pathway

    seen = {}
    real_assess = pathway.assess_series

    def spy(series, twins, good, z, min_gap_pp, min_den):
        seen.setdefault(series.stage, set()).add(round(z, 4))
        return real_assess(series, twins, good, z, min_gap_pp, min_den)

    monkeypatch.setattr(pathway, "assess_series", spy)
    pathway.run_pathway()
    assert seen["treatment"] == {2.5759} and seen["detection"] == {2.394}


def test_a_national_all_row_does_not_hide_the_survival_series():
    import pandas as pd

    from equal_path.observations import load_observations
    from equal_path.spine import make_observations

    store = load_observations()
    extra = make_observations([dict(geo_level="national", county_id="FI", indicator_id="survival_5y_relative",
                                    period="2020-2024", subgroup="all", value=0.70, numerator=None, denominator=None,
                                    quality_flag="", source_id="S_CIF2024_REPORT", locator="x", ci_low=None, ci_high=None)])
    result = run_pathway(store=pd.concat([store, extra], ignore_index=True))
    survival = result.assessments[result.assessments.indicator_id == "survival_5y_relative"]
    assert set(survival.subgroup) == {"site:breast|sex:female", "site:colorectal|sex:all", "site:lung|sex:female", "site:lung|sex:male"}


def test_every_f1_observable_pair_has_an_f2_row(result):
    from equal_path.config import load_indicator_catalog

    eligible = {i.id for i in load_indicator_catalog()
                if i.stage in ("detection", "referral", "diagnosis", "treatment") and i.direction != "context" and i.unit in ("share", "ratio")}
    pairs = {(code, ind) for ind in eligible for code in result.observable.index[result.observable[ind]]}
    assessed = set(zip(result.assessments.code, result.assessments.indicator_id))
    assert pairs <= assessed


def test_small_denominator_unit_shows_as_unknown_row_and_keeps_pooled_national():

    from equal_path.observations import load_observations

    store = load_observations().copy()
    mask = (store.indicator_id == "lung_curative_route_share") & (store.county_id == "18") & (store.geo_level == "unit")
    store.loc[mask, ["numerator", "denominator", "value"]] = [6.0, 25.0, 0.24]
    result = run_pathway(store=store)
    rows = result.assessments[result.assessments.indicator_id == "lung_curative_route_share"]
    row = rows[rows.code == "18"].iloc[0]
    assert row.state == "unknown" and "25 < 30" in row.reason
    assert len(rows) == 22
    assert rows.national.dropna().iloc[0] == pytest.approx(
        (store[(store.indicator_id == "lung_curative_route_share") & (store.geo_level == "unit")].numerator.sum())
        / store[(store.indicator_id == "lung_curative_route_share") & (store.geo_level == "unit")].denominator.sum(), abs=1e-3)


def test_twin_sets_do_not_depend_on_outcome_rows():
    """Spec F3: no outcome leakage. Removing every non-covariate row leaves the twin sets unchanged."""
    from equal_path.geography import UNIT_CODES
    from equal_path.observations import load_observations
    from equal_path.twins import COVARIATES, covariate_matrix, twin_sets

    store = load_observations()
    only_covariates = store[store.indicator_id.isin(COVARIATES)]
    a = twin_sets(covariate_matrix(store, UNIT_CODES), 3, 90)
    b = twin_sets(covariate_matrix(only_covariates, UNIT_CODES), 3, 90)
    assert {k: v.twins for k, v in a.items()} == {k: v.twins for k, v in b.items()}


def test_twin_distance_matrix_is_symmetric_with_zero_diagonal():
    import numpy as np

    from equal_path.geography import UNIT_CODES
    from equal_path.observations import load_observations
    from equal_path.twins import covariate_matrix, distance_matrix

    d = distance_matrix(covariate_matrix(load_observations(), UNIT_CODES))
    assert np.allclose(d.values, d.values.T) and np.allclose(np.diag(d.values), 0)


def test_assessments_name_better_twins_or_leader(result):
    assert "better_twins" in result.assessments.columns
    rows = result.assessments[result.assessments.state != "unknown"]
    assert rows.better_twins.map(lambda v: v is None or isinstance(v, tuple)).all()


def test_no_twin_data_is_not_reported_as_leadership(result):
    """Review TW-1, real case: no twin of unit 08 has stage recording coverage, so its row must say
    'no twin data' (None), not 'leader among peers' (empty tuple)."""
    rows = result.assessments[(result.assessments.code == "08")
                              & (result.assessments.indicator_id == "stage_recording_coverage")]
    assert len(rows) and rows.better_twins.map(lambda v: v is None).all()


def test_real_twin_stability_is_reported_for_every_county(result):
    """Spec F3 gate: mean Jaccard >= 0.6 under +/-5 % noise. Reported per county (10 of 22 fall below:
    a disclosed gate result, driven by income), never silently turned into 'no good twin'."""
    values = result.twin_stability
    assert set(values) == set(result.twins) and all(0.0 <= v <= 1.0 for v in values.values())
    assert min(values.values()) < 1.0  # noise was applied
    assert all(t.good for t in result.twins.values())  # instability does not remove twins
