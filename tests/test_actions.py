"""F5 action engine: truth tables per rule, guards, Unknown stages, ranking, owners, neutrality, determinism."""

import pytest

from equal_path.actions import (
    DATA_CAPTURE_FIRST, FACT_NAMES, NO_VERIFIED_GAP, county_plan, evaluate_condition, evaluate_rule,
)
from equal_path.config import load_rules, load_thresholds

RULES = {r.id: r for r in load_rules()}
T = load_thresholds()

QUIET = {  # every fact known and nothing wrong: no gap rule should fire
    **{f"stage_{s}": "ok" for s in ("detection", "referral", "diagnosis", "treatment", "timing")},
    **{f"visibility_{s}": 1.0 for s in ("detection", "referral", "diagnosis", "treatment", "timing")},
    **{f"gap_{s}": 0.0 for s in ("detection", "referral", "diagnosis", "treatment", "timing")},
    "stage_coverage": 0.90, "screening_stats_annual": 0, "leaking_participation_below_target": 0,
    "max_subgroup_gap_pp": 0.0, "primary_care_trend_worse": 0, "coordinator_in_use": 1, "stage12_below_twin": 0,
    "slow_symptom_route": 0, "late_stage_pattern": 0, "low_symptom_awareness": 0, "distance_above_median": 0,
    "lung_curative_leak": 0, "treatment_mix_deviates": 0, "share_75_above_national": 0,
    "primary_care_worse_than_national": 0, "digital_pathway_in_use": 1, "public_private_delay_suspected": 0,
}

# Oracle written from spec section 6, independently of the conditions in config/rules.yaml:
# rule -> (facts that satisfy its trigger, single changes that must each stop it from firing)
TRUTH = {
    "R-DET-01": ({"stage_detection": "leak", "leaking_participation_below_target": 1, "max_subgroup_gap_pp": 6.0},
                 [{"stage_detection": "watch"}, {"leaking_participation_below_target": 0}, {"max_subgroup_gap_pp": 4.9}]),
    "R-DET-02": ({"screening_stats_annual": 1}, [{"screening_stats_annual": 0}]),
    "R-DAT-01": ({"stage_coverage": 0.419}, [{"stage_coverage": 0.70}, {"stage_coverage": 0.72}]),
    "R-REF-01": ({"stage_referral": "leak", "stage12_below_twin": 1},
                 [{"stage_referral": "ok"}, {"stage12_below_twin": 0}]),
    "R-REF-02": ({"stage_referral": "leak", "primary_care_trend_worse": 1},
                 [{"stage_referral": "watch"}, {"primary_care_trend_worse": 0}]),
    "R-REF-03": ({"stage_referral": "leak", "coordinator_in_use": 0},
                 [{"stage_referral": "ok"}, {"coordinator_in_use": 1}]),
    "R-SYM-01": ({"stage_diagnosis": "leak", "late_stage_pattern": 1, "low_symptom_awareness": 1},
                 [{"stage_diagnosis": "ok"}, {"late_stage_pattern": 0}, {"low_symptom_awareness": 0}]),
    "R-TRT-01": ({"stage_treatment": "leak", "distance_above_median": 1, "lung_curative_leak": 1},
                 [{"stage_treatment": "ok"}, {"distance_above_median": 0}, {"lung_curative_leak": 0}]),
    "R-TRT-02": ({"stage_treatment": "leak", "lung_curative_leak": 1},
                 [{"stage_treatment": "watch"}, {"lung_curative_leak": 0}]),
    "R-GER-01": ({"stage_referral": "leak", "share_75_above_national": 1},
                 [{"stage_referral": "ok"}, {"share_75_above_national": 0}]),
    "R-DIG-01": ({"stage_referral": "leak", "primary_care_worse_than_national": 1, "digital_pathway_in_use": 0},
                 [{"stage_referral": "ok"}, {"primary_care_worse_than_national": 0}, {"digital_pathway_in_use": 1}]),
    "R-AUD-01": ({"stage_timing": "leak", "public_private_delay_suspected": 1},
                 [{"stage_timing": "ok"}, {"public_private_delay_suspected": 0}]),
}


def test_truth_table_covers_every_rule():
    assert set(TRUTH) == set(RULES)


@pytest.mark.parametrize("rule_id", sorted(TRUTH))
def test_truth_table_fires_when_satisfied(rule_id):
    satisfy, _ = TRUTH[rule_id]
    assert evaluate_rule(RULES[rule_id], {**QUIET, **satisfy}, T).status == "fires"


@pytest.mark.parametrize("rule_id,change", [(r, c) for r, (_, changes) in sorted(TRUTH.items()) for c in changes])
def test_truth_table_does_not_fire_when_violated(rule_id, change):
    satisfy, _ = TRUTH[rule_id]
    assert evaluate_rule(RULES[rule_id], {**QUIET, **satisfy, **change}, T).status == "not triggered"


@pytest.mark.parametrize("rule_id", sorted(TRUTH))
def test_quiet_county_fires_nothing(rule_id):
    assert evaluate_rule(RULES[rule_id], QUIET, T).status == "not triggered"


@pytest.mark.parametrize("rule_id", sorted(r for r in TRUTH if not RULES[r].data_capture))
def test_no_gap_rule_fires_on_an_unknown_stage(rule_id):
    """F5: no rule fires on a stage that is Unknown, except the data-capture rules."""
    satisfy, _ = TRUTH[rule_id]
    stage = RULES[rule_id].stage
    assert evaluate_rule(RULES[rule_id], {**QUIET, **satisfy, f"stage_{stage}": "unknown"}, T).status != "fires"


@pytest.mark.parametrize("rule_id", ["R-DAT-01", "R-DET-02"])
def test_data_capture_rules_fire_even_when_their_stage_is_unknown(rule_id):
    satisfy, _ = TRUTH[rule_id]
    stage = RULES[rule_id].stage
    facts = {**QUIET, **satisfy, f"stage_{stage}": "unknown", f"visibility_{stage}": 0.0}
    assert evaluate_rule(RULES[rule_id], facts, T).status == "fires"


@pytest.mark.parametrize("rule_id", sorted(r for r in TRUTH if RULES[r].do_not_fire_if))
def test_guard_blocks_a_low_visibility_stage(rule_id):
    satisfy, _ = TRUTH[rule_id]
    facts = {**QUIET, **satisfy, f"visibility_{RULES[rule_id].stage}": 0.4}
    assert evaluate_rule(RULES[rule_id], facts, T).status == "blocked"


@pytest.mark.parametrize("rule_id,fact", [("R-REF-03", "coordinator_in_use"), ("R-SYM-01", "late_stage_pattern"),
                                          ("R-DIG-01", "digital_pathway_in_use"), ("R-DET-01", "max_subgroup_gap_pp")])
def test_missing_data_means_needs_data_never_fires(rule_id, fact):
    satisfy, _ = TRUTH[rule_id]
    outcome = evaluate_rule(RULES[rule_id], {**QUIET, **satisfy, fact: None}, T)
    assert outcome.status == "needs data" and fact in " ".join(outcome.missing)


def test_kleene_logic_false_beats_unknown():
    """A known False condition decides 'not triggered' even if another condition has no data."""
    satisfy, _ = TRUTH["R-REF-03"]
    outcome = evaluate_rule(RULES["R-REF-03"], {**QUIET, **satisfy, "stage_referral": "ok", "coordinator_in_use": None}, T)
    assert outcome.status == "not triggered"


@pytest.mark.parametrize("text,expected", [
    ("stage_coverage < stage_coverage_target", True), ("stage_coverage >= 0.5", False),
    ("stage_detection == leak", False), ("max_subgroup_gap_pp >= subgroup_gap_trigger_pp", None),
])
def test_condition_language(text, expected):
    facts = {**QUIET, "stage_coverage": 0.419, "max_subgroup_gap_pp": None}
    assert evaluate_condition(text, facts, T) is expected


@pytest.mark.parametrize("text", ["__import__('os')", "stage_coverage < 0.7 or True", "nonexistent_fact > 1",
                                  "stage_coverage < ", "stage_coverage ~ 1"])
def test_condition_language_rejects_anything_else(text):
    with pytest.raises(ValueError):
        evaluate_condition(text, QUIET, T)


def test_every_rule_has_machine_conditions_over_known_facts():
    for rule in RULES.values():
        assert rule.when, rule.id
        for text in (*rule.when, *rule.when_any, *rule.do_not_fire_if):
            evaluate_condition(text, QUIET, T)  # raises on an unknown name or syntax
            assert text.split()[0] in FACT_NAMES


def test_hypothesis_rules_are_test_only():
    for rule in RULES.values():
        assert (rule.mode == "test") == (rule.evidence_grade == "hypothesis"), rule.id
    satisfy, _ = TRUTH["R-AUD-01"]
    assert evaluate_rule(RULES["R-AUD-01"], {**QUIET, **satisfy}, T).verb == "Test"


def test_national_lead_rules_never_ask_the_county_to_act_alone():
    satisfy, _ = TRUTH["R-REF-02"]
    outcome = evaluate_rule(RULES["R-REF-02"], {**QUIET, **satisfy}, T)
    assert RULES["R-REF-02"].owner_level == "national" and outcome.owner_label.startswith("National lead")


def test_rule_text_is_product_neutral():
    from equal_path.lint import neutrality_violations

    for rule in RULES.values():
        for field in (rule.trigger, rule.action, rule.owner, rule.kpi, rule.cost_ref, rule.note):
            assert neutrality_violations(field) == [], (rule.id, field)


# --- ranking and plans --------------------------------------------------------------------------

def test_ranking_puts_data_capture_first_then_gaps_then_other_data_capture():
    facts = {**QUIET, "stage_coverage": 0.41, "screening_stats_annual": 1,
             **TRUTH["R-TRT-02"][0], "gap_treatment": 0.05, **TRUTH["R-DET-01"][0], "gap_detection": 0.08}
    plan = county_plan(facts, T)
    assert [o.rule_id for o in plan.top] == ["R-DAT-01", "R-DET-01", "R-TRT-02"]
    assert plan.message == DATA_CAPTURE_FIRST


def test_no_verified_gap_says_so_and_offers_only_data_actions():
    plan = county_plan({**QUIET, "stage_coverage": 0.41, "screening_stats_annual": 1}, T)
    assert plan.message == NO_VERIFIED_GAP
    assert [o.rule_id for o in plan.top] == ["R-DAT-01", "R-DET-02"]


@pytest.fixture(scope="module")
def real():
    from equal_path.actions import run_actions

    return run_actions()


def test_every_county_with_low_stage_coverage_gets_data_capture_first(real):
    """F5 Expect: low stage coverage -> the data-capture action first. Pirkanmaa (72 %) is the exception."""
    for code, plan in real.plans.items():
        if code == "08":
            assert "R-DAT-01" not in [o.rule_id for o in plan.top]
        else:
            assert plan.top[0].rule_id == "R-DAT-01", code


def test_real_plans_follow_the_gap_locator(real):
    from equal_path.pathway import run_pathway

    stages = run_pathway().stages
    for code, plan in real.plans.items():
        leaks = {s for s in stages.columns if stages.loc[code, s] == "leak"}
        for outcome in plan.outcomes:
            rule = RULES[outcome.rule_id]
            if outcome.status == "fires" and not rule.data_capture:
                assert rule.stage in leaks, (code, rule.id)
        if not leaks:
            assert plan.message == NO_VERIFIED_GAP and all(RULES[o.rule_id].data_capture for o in plan.top)
        assert len(plan.top) <= 3


def test_low_participation_leaks_get_outreach_when_the_subgroup_gap_is_large(real):
    """R-DET-01 on real data, against an independent recomputation of the subgroup gaps."""
    from equal_path.observations import load_observations
    from equal_path.pathway import run_pathway

    store, result = load_observations(), run_pathway()
    for code, plan in real.plans.items():
        leaking = result.assessments[(result.assessments.code == code) & (result.assessments.state == "leak")
                                     & result.assessments.indicator_id.str.startswith("screening_participation")]
        gaps = []
        for indicator, period, value in zip(leaking.indicator_id, leaking.period, leaking.value):
            if value >= 0.80:
                continue
            rows = store[(store.indicator_id == indicator) & (store.county_id == code) & (store.period == period)
                         & (store.geo_level == "unit")].set_index("subgroup").value
            pairs = [("lang:domestic", "lang:other_or_missing"), ("edu:tertiary", "edu:primary_or_unknown")]
            gaps += [(rows[a] - rows[b]) * 100 for a, b in pairs if a in rows and b in rows]
        fired = "R-DET-01" in [o.rule_id for o in plan.outcomes if o.status == "fires"]
        assert fired == bool(gaps and max(gaps) >= T.subgroup_gap_trigger_pp), (code, gaps)


def test_kymenlaakso_lung_leak_triggers_the_peer_review_rule(real):
    assert "R-TRT-02" in [o.rule_id for o in real.plans["10"].outcomes if o.status == "fires"]


def test_same_input_same_output():
    from equal_path.actions import run_actions

    a, b = run_actions(), run_actions()
    assert {c: [(o.rule_id, o.status) for o in p.outcomes] for c, p in a.plans.items()} == \
           {c: [(o.rule_id, o.status) for o in p.outcomes] for c, p in b.plans.items()}


def test_stage_coverage_uses_the_most_local_published_level(real):
    """Pirkanmaa has its own value; Sisä-Suomi's other members use the area value; the rest use national."""
    facts = real.facts
    assert (round(facts["08"]["stage_coverage"], 3), facts["08"]["stage_coverage_level"]) == (0.719, "county")
    for code in ("07", "16"):
        assert (round(facts[code]["stage_coverage"], 3), facts[code]["stage_coverage_level"]) == (0.604, "cooperation area")
    assert (round(facts["21"]["stage_coverage"], 3), facts["21"]["stage_coverage_level"]) == (0.419, "national")


def test_outreach_needs_county_subgroup_data_and_says_so(real):
    """Participation by mother tongue and education is published nationally only, so R-DET-01 cannot be
    checked for the detection-leak counties: it must say 'needs data' with that reason, never fire."""
    for code in ("03", "09", "10", "14"):
        outcome = next(o for o in real.plans[code].outcomes if o.rule_id == "R-DET-01")
        assert outcome.status == "needs data" and "nationally only" in " ".join(outcome.missing), code


# --- fact helpers on synthetic data (real data never exercises some branches) ----------------------

def _store(rows):
    import pandas as pd

    keys = ("indicator_id", "county_id", "geo_level", "period", "subgroup", "value", "denominator")
    return pd.DataFrame([dict(zip(keys, r)) for r in rows])


def test_subgroup_gap_is_disadvantaged_group_below_and_takes_the_largest():
    import pandas as pd

    from equal_path.actions import _participation_facts

    ind = "screening_participation_cervical"
    store = _store([(ind, "01", "unit", "2024", "all", 0.70, None),
                    (ind, "01", "unit", "2024", "lang:domestic", 0.74, None), (ind, "01", "unit", "2024", "lang:other_or_missing", 0.55, None),
                    (ind, "01", "unit", "2024", "edu:tertiary", 0.76, None), (ind, "01", "unit", "2024", "edu:primary_or_unknown", 0.69, None)])
    assessments = pd.DataFrame([{"code": "01", "state": "leak", "indicator_id": ind, "period": "2024", "value": 0.70}])
    below, gap = _participation_facts(store, assessments, "01")
    assert below == 1 and gap == pytest.approx(19.0)   # 74 - 55 by mother tongue beats 76 - 69 by education
    assert _participation_facts(store, assessments.assign(value=0.85), "01") == (0, None)   # at/above 80 %: no outreach


@pytest.mark.parametrize("values,direction,expected", [
    ([0.10, 0.12, 0.15, 0.18, 0.20], "lower_better", 1),   # waits over 7 days rising: worse
    ([0.20, 0.18, 0.15, 0.12, 0.10], "lower_better", 0),
    ([0.80, 0.78, 0.75, 0.70, 0.69], "higher_better", 1),
])
def test_trend_worse_respects_the_indicator_direction(values, direction, expected):
    from types import SimpleNamespace

    from equal_path.actions import _trend_worse

    store = _store([("x", "01", "unit", str(2021 + i), "all", v, None) for i, v in enumerate(values)])
    assert _trend_worse(store, {"x": SimpleNamespace(direction=direction)}, "x", "01") == expected


def test_above_median_and_above_national():
    from equal_path.actions import _above_median, _above_national

    # median 27.5 and mean 40 differ, so county 03 (35) tells them apart
    store = _store([("d", c, "unit", "2025", "all", v, None) for c, v in (("01", 10.0), ("02", 20.0), ("03", 35.0), ("04", 95.0))]
                   + [("s", "01", "unit", "2025", "all", 0.13, None), ("s", "FI", "national", "2025", "all", 0.12, None),
                      ("s", "FI", "national", "2025", "site:x", 0.50, None)])
    assert [_above_median(store, "d", ["01", "02", "03", "04"], c) for c in ("01", "02", "03", "04")] == [0, 0, 1, 1]
    assert _above_national(store, "s", "01") == 1
    assert _above_median(store, "d", ["01", "02", "03", "04"], "99") is None


# --- review fixes (Step 6) ------------------------------------------------------------------------

def test_gap_without_a_checkable_gap_action_does_not_claim_gap_actions():
    """Review E-1: a verified gap whose only rule needs data must not be announced as 'actions for the gaps'."""
    from equal_path.actions import GAP_NEEDS_DATA

    facts = {**QUIET, "stage_coverage": 0.719, "screening_stats_annual": 1, "stage_detection": "leak",
             "leaking_participation_below_target": 1, "max_subgroup_gap_pp": None, "gap_detection": 0.04}
    plan = county_plan(facts, T)
    assert [o.rule_id for o in plan.top] == ["R-DET-02"] and plan.message == GAP_NEEDS_DATA


def test_every_fact_a_rule_uses_exists_for_every_county(real):
    """Review E-2: a renamed fact key would silently turn a firing rule into 'needs data'."""
    for code, facts in real.facts.items():
        assert FACT_NAMES <= set(facts), (code, FACT_NAMES - set(facts))


def test_kymenlaakso_plan_is_pinned(real):
    plan = real.plans["10"]
    assert {o.rule_id for o in plan.outcomes if o.status == "fires"} == {"R-DAT-01", "R-DET-02", "R-TRT-01", "R-TRT-02"}
    assert [o.rule_id for o in plan.top] == ["R-DAT-01", "R-TRT-01", "R-TRT-02"]


def test_verified_gap_sizes_are_the_smaller_of_the_two_references(real):
    """Review E-3: the gap printed on the card is the verified (smaller) gap of the largest leak."""
    assert real.facts["10"]["gap_treatment"] == pytest.approx(0.052, abs=5e-4)
    assert real.facts["10"]["gap_detection"] == pytest.approx(0.035, abs=5e-4)
    assert real.facts["14"]["gap_detection"] == pytest.approx(0.057, abs=5e-4)


@pytest.mark.parametrize("rule_id,arm", [("R-REF-01", {"slow_symptom_route": 1}), ("R-TRT-02", {"treatment_mix_deviates": 1})])
def test_second_when_any_arm_fires_on_its_own(rule_id, arm):
    """Review E-4: each 'any' arm alone is enough."""
    stage = RULES[rule_id].stage
    assert evaluate_rule(RULES[rule_id], {**QUIET, f"stage_{stage}": "leak", **arm}, T).status == "fires"


def test_boundaries_follow_the_spec():
    """Review E-4: a subgroup gap of exactly 5 pp fires (>=); visibility exactly 0.5 is not blocked."""
    satisfy, _ = TRUTH["R-DET-01"]
    assert evaluate_rule(RULES["R-DET-01"], {**QUIET, **satisfy, "max_subgroup_gap_pp": 5.0}, T).status == "fires"
    assert evaluate_rule(RULES["R-DET-01"], {**QUIET, **satisfy, "visibility_detection": 0.5}, T).status == "fires"


GUARDS = {  # oracle: each rule is guarded on its own stage's visibility; R-REF-01 also on diagnosis (approved Stage 1)
    "R-DET-01": ["visibility_detection < min_stage_visibility"], "R-DET-02": [], "R-DAT-01": [],
    "R-REF-01": ["visibility_referral < min_stage_visibility", "visibility_diagnosis < min_stage_visibility"],  # Stage 1
    "R-REF-02": ["visibility_referral < min_stage_visibility"],
    "R-REF-03": ["visibility_referral < min_stage_visibility"], "R-SYM-01": ["visibility_diagnosis < min_stage_visibility"],
    "R-TRT-01": ["visibility_treatment < min_stage_visibility"], "R-TRT-02": ["visibility_treatment < min_stage_visibility"],
    "R-GER-01": ["visibility_referral < min_stage_visibility"], "R-DIG-01": ["visibility_referral < min_stage_visibility"],
    "R-AUD-01": ["visibility_timing < min_stage_visibility"],
}


def test_guards_are_exactly_the_own_stage_visibility():
    assert {r.id: list(r.do_not_fire_if) for r in RULES.values()} == GUARDS


def test_low_access_needs_a_practical_gap(real):
    """Review E-6: 'low access' means at least the practical gap (3 pp) worse than national, not any difference."""
    from equal_path.pathway import run_pathway

    a = run_pathway().assessments
    for code, facts in real.facts.items():
        rows = a[(a.code == code) & (a.indicator_id == "primary_care_access") & a.gap_national.notna()]
        expected = None if rows.empty else int((rows.gap_national >= T.min_practical_gap_pp / 100).any())
        assert facts["primary_care_worse_than_national"] == expected, code


def test_primary_care_trend_is_not_used_across_the_definition_break(real):
    """Review E-7: the series breaks at the 9/2023 and 1/2025 law changes; the fact stays unknown with that reason."""
    assert all(f["primary_care_trend_worse"] is None for f in real.facts.values())
    satisfy, _ = TRUTH["R-REF-02"]
    outcome = evaluate_rule(RULES["R-REF-02"], {**QUIET, **satisfy, "primary_care_trend_worse": None}, T)
    assert "definition changed" in " ".join(outcome.missing_reasons)
