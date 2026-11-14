"""Twin core (F3 dependency of F2): structural covariates only, deterministic, symmetric."""

import numpy as np
import pandas as pd
import pytest

from equal_path.twins import (
    COVARIATES, LOG1P_COVARIATES, LOG_COVARIATES, better_twins, distance_matrix, prepare, stability, twin_sets,
)

CODES = [f"{i:02d}" for i in range(1, 9)]


def _matrix(seed=0):
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(rng.normal(size=(len(CODES), len(COVARIATES))), index=CODES, columns=list(COVARIATES))
    return frame.assign(cov_population_density=10 ** frame.cov_population_density,  # positive
                        cov_distance_university_hospital_km=10 ** (1 + frame.cov_distance_university_hospital_km))


def test_covariates_are_the_spec_structural_set():
    assert set(COVARIATES) == {"cov_share_aged_75_plus", "cov_education", "cov_income", "cov_population_density",
                               "cov_foreign_language_share", "cov_distance_university_hospital_km"}


def test_distance_symmetric_with_zero_diagonal():
    d = distance_matrix(_matrix())
    assert np.allclose(d.values, d.values.T) and np.allclose(np.diag(d.values), 0)


def test_k_nearest_excluding_self_with_code_tie_break():
    m = pd.DataFrame({c: [0.0] * 4 for c in COVARIATES}, index=["01", "02", "03", "04"]).assign(cov_population_density=1.0)
    m.loc["01", "cov_income"] = 1.0  # 02, 03, 04 are identical: ties broken by code
    sets = twin_sets(m, k=2, no_good_percentile=90)
    assert sets["02"].twins == ("03", "04")
    assert "02" not in sets["02"].twins


def test_far_county_has_no_good_twin():
    codes = [f"{i:02d}" for i in range(1, 22)] + ["90"]  # the real unit count matters for the percentile
    rng = np.random.default_rng(1)
    m = pd.DataFrame(rng.normal(size=(22, len(COVARIATES))), index=codes, columns=list(COVARIATES))
    m = m.assign(cov_population_density=10 ** m.cov_population_density,
                 cov_distance_university_hospital_km=m.cov_distance_university_hospital_km.abs())
    m.loc["90"] = 50.0  # far from everyone
    m.loc["90", "cov_population_density"] = 1e40
    sets = twin_sets(m, k=3, no_good_percentile=90)
    assert not sets["90"].good
    assert sum(t.good for t in sets.values()) >= 18


def test_order_invariance():
    m = _matrix(2)
    shuffled = m.sample(frac=1, random_state=3)
    a, b = twin_sets(m, 3, 90), twin_sets(shuffled, 3, 90)
    assert {k: v.twins for k, v in a.items()} == {k: v.twins for k, v in b.items()}


def test_outcome_columns_are_rejected():
    m = _matrix().assign(screening_participation_breast=0.8)
    with pytest.raises(ValueError, match="covariate"):
        twin_sets(m, 3, 90)


def test_twins_are_scale_invariant():
    """z-scoring: measuring income in cents instead of euros must not change any twin set."""
    m = _matrix(4)
    scaled = m.assign(cov_income=m.cov_income * 100 + 30_000)
    a, b = twin_sets(m, 3, 90), twin_sets(scaled, 3, 90)
    assert {k: v.twins for k, v in a.items()} == {k: v.twins for k, v in b.items()}


def test_density_is_log_transformed_before_z_scoring():
    assert LOG_COVARIATES == ("cov_population_density",)
    m = pd.DataFrame({c: [1.0, 2.0, 3.0, 4.0] for c in COVARIATES}, index=["01", "02", "03", "04"])
    m["cov_population_density"] = [2.0, 20.0, 200.0, 3000.0]
    prepared = prepare(m)
    assert prepared.cov_population_density.tolist() == pytest.approx(np.log10([2.0, 20.0, 200.0, 3000.0]).tolist())


def test_near_ties_are_broken_by_code():
    m = pd.DataFrame({c: [0.0, 0.0, 0.0] for c in COVARIATES}, index=["01", "02", "03"]).assign(cov_population_density=1.0)
    m.loc["01", "cov_income"] = 1.0
    m.loc["03", "cov_income"] = 1.0 + 1e-13  # float noise must not beat the code tie-break
    for income in (2.0, 1.5):  # wherever the float noise falls, the tie goes to the lower code
        m.loc["02", "cov_income"] = income
        assert twin_sets(m, k=1, no_good_percentile=100)["02"].twins == ("01",)


def test_distance_uses_log1p_so_zero_km_is_allowed():
    assert LOG1P_COVARIATES == ("cov_distance_university_hospital_km",)
    m = pd.DataFrame({c: [1.0, 2.0, 3.0] for c in COVARIATES}, index=["01", "02", "03"])
    m["cov_distance_university_hospital_km"] = [0.0, 9.0, 99.0]
    assert prepare(m).cov_distance_university_hospital_km.tolist() == pytest.approx([0.0, 1.0, 2.0])


def test_stability_is_one_without_noise_and_reported_per_county():
    m = _matrix(5)
    scores = stability(m, k=3, noise_fraction=0.0, draws=5, seed=1)
    assert set(scores) == set(CODES) and all(v == 1.0 for v in scores.values())


def test_stability_is_deterministic_for_a_seed():
    m = _matrix(6)
    assert stability(m, 3, 0.05, 50, seed=7) == stability(m, 3, 0.05, 50, seed=7)


@pytest.mark.parametrize(
    "direction,values,expected",
    [
        ("higher_better", {"02": 0.80, "03": 0.70, "04": 0.90}, ("04", "02")),   # better = higher, best first
        ("lower_better", {"02": 0.80, "03": 0.70, "04": 0.90}, ("03",)),         # better = lower
        ("higher_better", {"02": 0.60, "03": 0.65, "04": 0.70}, ()),             # leader among peers
    ],
)
def test_better_twins(direction, values, expected):
    assert better_twins(0.75, ("02", "03", "04"), values, direction) == expected


def test_noise_lowers_stability():
    m = _matrix(8)
    noisy = stability(m, k=3, noise_fraction=0.5, draws=50, seed=3)
    assert min(noisy.values()) < 1.0


def test_better_twins_is_none_when_no_twin_has_data():
    """Review TW-1: 'no twin has a value' must not read as 'leader among peers' (empty tuple)."""
    assert better_twins(0.75, ("02", "03"), {"04": 0.90, "02": float("nan"), "03": None}, "higher_better") is None
    assert better_twins(0.75, ("02", "03"), {"02": 0.70}, "higher_better") == ()


@pytest.mark.parametrize("column,raw", [
    ("cov_population_density", [1.0, 30.0, 100.0, 100_000.0]),       # log10: 0, 1.48, 2, 5
    ("cov_distance_university_hospital_km", [0.0, 30.0, 100.0, 5_000.0]),  # log10(1+x): 0, 1.49, 2.00, 3.70
])
def test_log_transforms_decide_the_twin_set(column, raw):
    """Review T-3: the transform must reach the distance, not just prepare(). With every other
    covariate equal, county 02 (30) is nearer 01 on the raw scale (29 vs 70) but nearer 03 on the
    log scale (0.52 vs 1.48), so twin_sets must pick 03."""
    m = pd.DataFrame({c: [1.0] * 4 for c in COVARIATES}, index=["01", "02", "03", "04"])
    m[column] = raw
    assert twin_sets(m, k=1, no_good_percentile=100)["02"].twins == ("03",)
    d = distance_matrix(m)
    assert d.loc["02", "03"] < d.loc["02", "01"]
