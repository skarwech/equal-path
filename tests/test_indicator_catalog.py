"""Indicator catalog: every section-5 indicator is listed, including those with no public data."""

import pytest

from equal_path.config import load_indicator_catalog, load_scope
from equal_path.sources import source_ids

# Section 5 pathway-to-indicator map (+ section 7.4 timing intervals, F3 covariates, Goal 3 links).
SECTION5 = {
    # detection
    "screening_participation_breast", "screening_participation_cervical", "screening_participation_colorectal",
    "hpv_vaccination_coverage", "breast_cancer_below_screening_age",
    # referral
    "primary_care_access",
    # diagnosis
    "stage_recording_coverage", "stage_one_two_share", "lung_cell_type_completeness",
    # treatment
    "lung_curative_route_share", "lung_first_line_treatment_mix", "survival_5y_relative",
    "distance_to_radiotherapy_km",
    # timing (THL Ohjaus 21/2016)
    "access_referral_to_first_treatment", "access_referral_to_first_visit", "access_queue_to_first_treatment",
}
COVARIATES = {
    "cov_population", "cov_share_aged_75_plus", "cov_education", "cov_income",
    "cov_population_density", "cov_foreign_language_share", "cov_distance_university_hospital_km",
}
STAGES = {"detection", "referral", "diagnosis", "treatment", "timing", "covariate", "context"}
STATUSES = {"available", "partial", "not_public", "to_verify"}


@pytest.fixture(scope="module")
def catalog():
    return {i.id: i for i in load_indicator_catalog()}


def test_catalog_lists_every_section5_indicator_and_covariate(catalog):
    assert SECTION5 | COVARIATES <= set(catalog)


def test_vocabularies(catalog):
    for indicator in catalog.values():
        assert indicator.stage in STAGES, indicator.id
        assert indicator.status in STATUSES, indicator.id


def test_covariates_never_double_as_outcomes(catalog):
    for indicator_id in COVARIATES:
        assert catalog[indicator_id].stage == "covariate"
        assert catalog[indicator_id].direction == "context"


def test_sources_resolve(catalog):
    known = source_ids()
    for indicator in catalog.values():
        assert indicator.source_ids and set(indicator.source_ids) <= known, indicator.id


def test_goal3_links_resolve(catalog):
    scope = load_scope()
    targets = {g.id for g in (*scope.goal3_indicators, *scope.related_targets)}
    for indicator in catalog.values():
        assert indicator.goal3_link is None or indicator.goal3_link in targets, indicator.id


def test_timing_intervals_are_not_claimed_available_without_thl_series(catalog):
    for indicator_id in ("access_referral_to_first_treatment", "access_referral_to_first_visit", "access_queue_to_first_treatment"):
        assert catalog[indicator_id].stage == "timing"
        assert catalog[indicator_id].unit == "weeks"


def test_ids_unique():
    ids = [i.id for i in load_indicator_catalog()]
    assert len(ids) == len(set(ids))
