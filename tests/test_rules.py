"""Section 6 action library: completeness, sourcing, evidence grading and neutrality."""

import pytest

from equal_path.config import load_rules
from equal_path.lint import neutrality_violations
from equal_path.sources import source_ids

EXPECTED_IDS = {
    "R-DET-01", "R-DET-02", "R-DAT-01", "R-REF-01", "R-REF-02", "R-REF-03",
    "R-SYM-01", "R-TRT-01", "R-TRT-02", "R-GER-01", "R-DIG-01", "R-AUD-01",
}
TEXT_FIELDS = ("trigger", "action", "owner", "kpi", "cost_ref")


@pytest.fixture(scope="module")
def rules():
    return load_rules()


def test_rule_ids_complete_and_unique(rules):
    ids = [r.id for r in rules]
    assert len(ids) == len(set(ids))
    assert set(ids) == EXPECTED_IDS


@pytest.mark.parametrize("field", TEXT_FIELDS)
def test_text_fields_non_empty(rules, field):
    for rule in rules:
        assert getattr(rule, field).strip(), (rule.id, field)


def test_every_citation_resolves(rules):
    known = source_ids()
    for rule in rules:
        assert rule.sources, rule.id
        for citation in rule.sources:
            assert citation.id in known, (rule.id, citation.id)


def test_hypothesis_only_as_test(rules):
    for rule in rules:
        assert (rule.evidence_grade == "hypothesis") == (rule.mode == "test"), rule.id
    assert {r.id for r in rules if r.mode == "test"} == {"R-AUD-01"}


def test_national_lead_labelled(rules):
    by_id = {r.id: r for r in rules}
    assert by_id["R-REF-02"].owner_level == "national"


def test_data_capture_rules_flagged(rules):
    assert {r.id for r in rules if r.data_capture} == {"R-DAT-01", "R-DET-02"}


def test_neutrality_lint_clean(rules):
    for rule in rules:
        for field in TEXT_FIELDS:
            assert neutrality_violations(getattr(rule, field)) == [], (rule.id, field)


# Expected per-rule content (spec section 6 + F5). owner_level classifies the section-6
# Owner column: national = a ministry leads (R-REF-02, STM); joint = a national body
# (Cancer Registry, FICAN, Cancer Society) shares ownership with counties; county = the
# county acts alone or with local partners (NGOs, university hospital).
EXPECTED = {
    "R-DET-01": ("detection", "joint", "strategy-endorsed", {("S_ROADMAP", "1.3.1"), ("S_SCREENING2024_PRESS", "points to the annual screening reports (breakdown by mother tongue)")}),
    "R-DET-02": ("detection", "joint", "strategy-endorsed", {("S_ROADMAP", "2.4.5")}),
    "R-DAT-01": ("diagnosis", "joint", "strategy-endorsed", {("S_ROADMAP", "4.1.1"), ("S_STRATEGY", "3.2 and 4.1")}),
    "R-REF-01": ("referral", "joint", "strategy-endorsed", {("S_ROADMAP", "2.5.2"), ("S_ROADMAP", "3.1.1")}),
    "R-REF-02": ("referral", "national", "strategy-endorsed", {("S_ROADMAP", "2.5.1")}),
    "R-REF-03": ("referral", "joint", "strategy-endorsed", {("S_ROADMAP", "1.2.3")}),
    "R-SYM-01": ("diagnosis", "joint", "strategy-endorsed", {("S_ROADMAP", "1.3.2")}),
    "R-TRT-01": ("treatment", "county", "study-supported", {("S_ROADMAP", "regional-inequality section (Paakkola et al. 2024; Jääskeläinen et al. 2023)")}),
    "R-TRT-02": ("treatment", "joint", "strategy-endorsed", {("S_ROADMAP", "3.2.2 and 3.2.3"), ("S_LUNG_2019_2023_VU", "county comparison")}),
    "R-GER-01": ("referral", "county", "strategy-endorsed", {("S_ROADMAP", "3.4.1-3.4.3"), ("S_STRATEGY", "3.4")}),
    "R-DIG-01": ("referral", "joint", "strategy-endorsed", {("S_ROADMAP", "3.5.3")}),
    "R-AUD-01": ("timing", "county", "hypothesis", {("S_THL_OHJAUS_21_2016", "time-point definitions"), ("S_ROADMAP", "regional-inequality section")}),
}


def test_expected_table_covers_all_rules():
    assert set(EXPECTED) == EXPECTED_IDS


@pytest.mark.parametrize("rule_id", sorted(EXPECTED_IDS))
def test_rule_matches_expected(rules, rule_id):
    rule = {r.id: r for r in rules}[rule_id]
    stage, owner_level, grade, citations = EXPECTED[rule_id]
    assert (rule.stage, rule.owner_level, rule.evidence_grade) == (stage, owner_level, grade)
    assert {(c.id, c.locator) for c in rule.sources} == citations


def test_only_r_ref_02_is_national_lead(rules):
    assert {r.id for r in rules if r.owner_level == "national"} == {"R-REF-02"}


def test_non_data_capture_rules_guard_their_own_stage(rules):
    """F5: no rule fires on an Unknown stage, except the data-capture rules."""
    for rule in rules:
        if rule.data_capture:
            continue
        own_guard = f"visibility_{rule.stage} < min_stage_visibility"
        assert own_guard in rule.do_not_fire_if, (rule.id, rule.do_not_fire_if)


def test_r_ref_01_also_guards_diagnosis(rules):
    """Its trigger uses stage I-II share, a diagnosis-stage indicator."""
    rule = {r.id: r for r in rules}["R-REF-01"]
    assert "visibility_diagnosis < min_stage_visibility" in rule.do_not_fire_if


def test_geriatric_trigger_is_population_share(rules):
    rule = {r.id: r for r in rules}["R-GER-01"]
    assert "75+" in rule.trigger and "population" in rule.trigger


NATIONAL_BODIES = ("Cancer Registry", "FICAN", "Cancer Society")


@pytest.mark.parametrize("rule_id", sorted(EXPECTED_IDS))
def test_owner_level_follows_the_documented_rule(rules, rule_id):
    rule = {r.id: r for r in rules}[rule_id]
    if "STM" in rule.owner:
        expected = "national"
    elif any(body in rule.owner for body in NATIONAL_BODIES):
        expected = "joint"
    else:
        expected = "county"
    assert rule.owner_level == expected, (rule_id, rule.owner)


@pytest.mark.parametrize("bad_id", ["R-DET-1", "det01", "R-det-01"])
def test_rule_id_pattern_enforced(tmp_path, bad_id):
    import yaml

    from equal_path.paths import RULES_FILE

    rules = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    rules[0]["id"] = bad_id
    path = tmp_path / "r.yaml"
    path.write_text(yaml.safe_dump(rules, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError):
        load_rules(path)


def test_section6_qualifiers_kept(rules):
    by_id = {r.id: r for r in rules}
    assert "at least the five most common cancers" in by_id["R-REF-01"].action
    assert "precondition for any equity claim" in by_id["R-DAT-01"].note
