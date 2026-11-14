"""Appendix B threshold register: values are copied verbatim and frozen by hash."""

import pytest
from pydantic import ValidationError

from equal_path.config import load_thresholds, read_lock_digest, thresholds_digest
from equal_path.paths import THRESHOLDS_FILE

# Verbatim copy of Appendix B (Equal Path rev 2). Changing a value here or in
# config/thresholds.yaml without updating the lock is a deliberate test failure.
APPENDIX_B = {
    "stage_coverage_target": 0.70,
    "stage_coverage_partial_min": 0.50,
    "min_denominator": 30,
    "min_practical_gap_pp": 3.0,
    "min_stage_visibility": 0.5,
    "subgroup_gap_trigger_pp": 5.0,
    "twin_stability_jaccard": 0.6,
    "min_annual_points_glidepath": 4,
    "min_monthly_points_early_warning": 24,
    "early_warning_detection_months_at_1sd": 6,
    "early_warning_detection_rate_min": 0.90,
    "early_warning_false_alarm_rate_max_per_year": 0.05,
    "false_leak_rate_max": 0.05,
    "reconciliation_counts_rel_tol": 0.01,
    "reconciliation_pct_abs_tol_pp": 0.5,
    "simulator_backcast_tol": 0.15,
    "analyst_brief_max_words": 120,
    "validator_regeneration_attempts": 2,
}

# Section 8 / 7.4 method constants (stated in the spec, outside Appendix B).
SECTION_8 = {
    "wilson_z": 1.96,
    "twin_k": 3,
    "no_good_twin_percentile": 90,
    "twin_noise_fraction": 0.05,
    "monte_carlo_draws": 5000,
    "simulator_interval": 0.80,
    "glidepath_target_year": 2035,
}

# Team-set additions frozen before any county data (spec F1 and F4 call them team-set).
TEAM_SET = {
    "early_warning_baseline_months": 12,
}


@pytest.fixture(scope="module")
def thresholds():
    return load_thresholds()


@pytest.mark.parametrize("name,expected", sorted({**APPENDIX_B, **SECTION_8, **TEAM_SET}.items()))
def test_value_matches_appendix_b(thresholds, name, expected):
    assert getattr(thresholds, name) == pytest.approx(expected)


def test_status_is_frozen(thresholds):
    assert thresholds.status == "frozen"
    assert thresholds.frozen_at  # non-empty timestamp


def test_digest_matches_lock():
    """Any edit to thresholds.yaml after the freeze must be explicit (re-lock)."""
    assert thresholds_digest() == read_lock_digest()


def test_tier_ordering(thresholds):
    assert 0 < thresholds.stage_coverage_partial_min < thresholds.stage_coverage_target <= 1


def test_model_is_immutable(thresholds):
    with pytest.raises(ValidationError, match="frozen"):
        thresholds.min_denominator = 5


def test_unknown_key_rejected(tmp_path):
    """A complete, valid file plus one stray knob must still be refused."""
    bad = tmp_path / "t.yaml"
    bad.write_text(THRESHOLDS_FILE.read_text(encoding="utf-8") + "\nsurprise_knob: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="surprise_knob"):
        load_thresholds(bad)


def test_visibility_stage_weights_fixed_and_sum_to_one(thresholds):
    weights = thresholds.visibility_stage_weights
    assert weights.model_dump() == {"detection": 0.25, "referral": 0.25, "diagnosis": 0.25, "treatment": 0.25}


@pytest.mark.parametrize("treatment", ["0.35", "0.15", "0.26", "0.2500001"])
def test_stage_weights_must_sum_to_one(tmp_path, treatment):
    text = THRESHOLDS_FILE.read_text(encoding="utf-8").replace("treatment: 0.25", f"treatment: {treatment}")
    bad = tmp_path / "t.yaml"
    bad.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="sum to 1"):
        load_thresholds(bad)


def test_every_field_is_pinned(thresholds):
    pinned = {**APPENDIX_B, **SECTION_8, **TEAM_SET, "status": None, "frozen_at": None, "visibility_stage_weights": None}
    assert set(type(thresholds).model_fields) == set(pinned)


def test_provenance_labels_every_field():
    from equal_path.config import threshold_provenance

    provenance = threshold_provenance()
    assert {k for k, v in provenance.items() if v == "Appendix B"} == set(APPENDIX_B)
    assert {k for k, v in provenance.items() if v == "Section 8 method constant"} == set(SECTION_8)
    assert {k for k, v in provenance.items() if v == "Team-set (not in spec)"} == {*TEAM_SET, "visibility_stage_weights"}
