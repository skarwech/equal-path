"""Source registry, frozen scope, reconciliation anchors and indicative reference times."""

import pytest

from equal_path.config import load_anchors, load_reference_times, load_scope
from equal_path.sources import REQUIRED_COLUMNS, load_sources, source_ids


@pytest.fixture(scope="module")
def sources():
    return load_sources()


def test_registry_columns_and_unique_ids(sources):
    assert list(sources.columns) == list(REQUIRED_COLUMNS)
    assert sources["source_id"].is_unique


@pytest.mark.parametrize("column", REQUIRED_COLUMNS)
def test_required_fields_non_empty(sources, column):
    assert sources[column].str.strip().ne("").all(), column


def test_urls_are_https(sources):
    assert sources["url"].str.startswith("https://").all()


def test_status_vocabulary(sources):
    assert set(sources["status"]) <= {"verified", "to_verify", "retrieved", "superseded"}


def test_scope_anchor_and_pending_decision():
    scope = load_scope()
    assert scope.anchor_cancer == "lung"
    assert set(scope.secondary_cancer_candidates) == {"breast", "colorectal"}
    assert scope.secondary_cancer in (None, *scope.secondary_cancer_candidates)
    assert scope.unit_count == 22
    assert scope.pathway_stages == ("detection", "referral", "diagnosis", "treatment")


def test_scope_goal3_indicators_cite_sources():
    scope = load_scope()
    assert len(scope.goal3_indicators) >= 1
    cited = {i.source_id for i in (*scope.goal3_indicators, *scope.related_targets)}
    assert cited <= source_ids()


def test_anchors_cite_sources_and_reproduce_doc_values():
    anchors = {a.id: a for a in load_anchors()}
    assert anchors["new_cancers_2024"].value == 38853
    assert anchors["cancer_deaths_2024"].value == 13490
    assert anchors["stage_coverage_national"].value == pytest.approx(0.42)
    assert anchors["lung_curative_route_share"].value == pytest.approx(0.27)
    assert {a.source_id for a in anchors.values()} <= source_ids()


def test_reference_times_are_indicative_not_binding():
    times = load_reference_times()
    assert times.binding is False
    assert times.source_id in source_ids()
    referral = {i.id: i for i in times.intervals}["referral_to_first_treatment"]
    assert referral.limit_weeks == 6


# Registry pinned to Appendix A (+ the geography sources this pipeline fetched).
EXPECTED_SOURCES = {
    "S_STRATEGY": "verified",
    "S_ROADMAP": "verified",
    "S_LINKPACK": "verified",
    "S_THL_OHJAUS_21_2016": "verified",
    "S_SYOPA2024_PRESS": "verified",
    "S_SYOPA2024_VU": "verified",
    "S_SCREENING2024_PRESS": "verified",
    "S_LUNG_2019_2023_VU": "verified",
    "S_LUNG_2018_2022_VU": "superseded",
    "S_PRIMARYCARE_VU_2023": "verified",
    "S_HILMO_STUDY_2014": "verified",
    "S_CANCER_REGISTRY_STATS": "to_verify",
    "S_SOTKANET": "retrieved",
    "S_STATFIN": "retrieved",
    "S_NORDCAN": "to_verify",  # url https://nordcan.iarc.who.int/
    "S_OECD_CCP_2023": "to_verify",
    "S_STATFI_HVA_CLASS_2026": "retrieved",
    "S_STATFI_YTA_CORR_2026": "retrieved",
    "S_STATFI_HVA_BOUNDARIES_2026": "retrieved",
    "S_CR_SCREENING_STATS": "retrieved",
    "S_CIF2024_REPORT": "retrieved",
    "S_LUNG_REPORT_2019_2023": "retrieved",
    "S_CR_APP_2024": "retrieved",
    "S_WIKIDATA_UNIV_HOSPITALS": "retrieved",
    "S_STATFI_KUNTA_BOUNDARIES_2026": "retrieved",
}


def test_registry_ids_and_statuses_pinned(sources):
    assert dict(zip(sources["source_id"], sources["status"])) == EXPECTED_SOURCES


def test_retrieved_sources_are_backed_by_manifests(sources):
    """Every 'retrieved' source has saved raw files; every saved file cites a registered source."""
    import json

    from equal_path.paths import DATA_DIR

    entries = [e for m in (DATA_DIR / "raw").glob("*/manifest.json") for e in json.loads(m.read_text(encoding="utf-8"))]
    cited = {e["source_id"] for e in entries}
    retrieved = set(sources.loc[sources["status"] == "retrieved", "source_id"])
    assert retrieved == cited
    assert all(e["url"].startswith("https://") for e in entries)


def test_goal3_and_related_targets_pinned():
    scope = load_scope()
    assert [g.id for g in scope.goal3_indicators] == [
        "treatment_within_target_times",
        "five_year_survival_nordic_level",
        "cancer_mortality_minus_10",
    ]
    assert [g.id for g in scope.related_targets] == [
        "screening_participation",
        "stage_one_two_share",
        "hpv_vaccination_coverage",
        "screening_parity_mother_tongue",
    ]


def test_excluded_units_match_geography():
    from equal_path.geography import EXCLUDED_CODES

    assert set(load_scope().excluded_units) == set(EXCLUDED_CODES)


EXPECTED_ANCHORS = {
    # id: (value, low, high, level, source_id)
    "new_cancers_2024": (38853, None, None, "national", "S_SYOPA2024_PRESS"),
    "cancer_deaths_2024": (13490, None, None, "national", "S_SYOPA2024_PRESS"),
    "stage_coverage_national": (0.42, None, None, "national", "S_SYOPA2024_VU"),
    "stage_coverage_pirkanmaa": (0.72, None, None, "unit", "S_SYOPA2024_VU"),
    "stage_coverage_sisa_suomi": (0.60, None, None, "cooperation_area", "S_SYOPA2024_VU"),
    "stage_coverage_other_areas": (None, 0.33, 0.42, "cooperation_area", "S_SYOPA2024_VU"),
    "screening_cancers_found_2024": (2360, None, None, "national", "S_SCREENING2024_PRESS"),
    "screening_precursors_found_2024": (5272, None, None, "national", "S_SCREENING2024_PRESS"),
    "screening_participation_lowest": (None, None, 0.68, "unit", "S_SCREENING2024_PRESS"),
    "lung_curative_route_share": (0.27, None, None, "national", "S_LUNG_2019_2023_VU"),
    "lung_stage_missing_share": (None, None, 0.50, "national", "S_LUNG_2019_2023_VU"),
}


def test_anchors_pinned():
    anchors = {a.id: (a.value, a.low, a.high, a.level, a.source_id) for a in load_anchors()}
    assert anchors == EXPECTED_ANCHORS


def test_anchor_needs_value_or_bound(tmp_path):
    from equal_path.config import load_anchors as load

    bad = tmp_path / "a.yaml"
    bad.write_text(
        "- {id: x, label: x, unit: share, period: '2024', level: national, source_id: S_STRATEGY}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="value or a bound"):
        load(bad)


EXPECTED_INTERVALS = {
    "referral_to_first_treatment": 6,
    "very_urgent_diagnosis_to_treatment": 3,
    "imaging_report": 1,
    "tissue_sample": 1,
    "pathology_report": 1,
    "adjuvant_after_surgery": 4,
}


def test_reference_intervals_pinned():
    assert {i.id: i.limit_weeks for i in load_reference_times().intervals} == EXPECTED_INTERVALS


def test_anchor_low_above_high_rejected(tmp_path):
    bad = tmp_path / "a.yaml"
    bad.write_text(
        "- {id: x, label: x, low: 0.5, high: 0.3, unit: share, period: '2024', level: national, source_id: S_STRATEGY}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="low > high"):
        load_anchors(bad)


def test_unretrieved_sources_say_so(sources):
    to_verify = sources[sources["status"] == "to_verify"]
    assert (to_verify["retrieved_on"] == "not retrieved").all()


def test_nordcan_uses_current_domain(sources):
    assert sources.set_index("source_id").loc["S_NORDCAN", "url"] == "https://nordcan.iarc.who.int/"
