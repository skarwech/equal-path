"""F5 action engine: evaluates the rule table (config/rules.yaml) against each county's facts.

Each rule has machine conditions over named facts ('when': all must hold; 'when_any': at least
one). Facts come from the gap locator, the store and the catalog. A fact with no public county
data is None, and conditions use three-valued (Kleene) logic: False beats unknown, so a rule
whose trigger cannot be checked reports 'needs data' instead of firing.

Design fixed before any county was evaluated:
- Gap rules require a verified gap (Leak) in their own stage, so no rule fires on an Unknown
  stage; the data-capture rules (R-DAT-01, R-DET-02) fire on their own data trigger (spec F5).
- Ranking: R-DAT-01 first (stage recording is the precondition for every other claim, spec F5),
  then gap rules by the size of their stage's verified gap, then the other data-capture rules.
  Top 3. With no verified gap anywhere the plan says so instead of forcing a recommendation.
"""

from __future__ import annotations

import operator
import re
import statistics
from dataclasses import dataclass, field

import pandas as pd

from equal_path.visibility import COMPOSITE_STAGES, SEPARATE_STAGES

STAGES = COMPOSITE_STAGES + SEPARATE_STAGES
SCREENING_TARGET = 0.80            # national goal: >= 80 % participation in every county (scope.yaml)
PRECONDITION_RULES = ("R-DAT-01",)  # spec F5: low stage coverage always gets the data-capture action first
NO_VERIFIED_GAP = "No verified gap; maintain and improve data"
DATA_CAPTURE_FIRST = "Stage recording comes first: without it no stage-level equity claim can be verified"
GAP_ACTIONS = "Actions for the verified gaps, largest gap first"
GAP_NEEDS_DATA = "Verified gap found, but no gap action can be checked yet (needs data); data actions first"
STATES = ("leak", "watch", "ok", "unknown")

# Facts with no public county-level data: always unknown, with the reason shown as 'needs data'.
NO_PUBLIC_DATA = {
    "coordinator_in_use": "use of a named care coordinator is not published by county",
    "stage12_below_twin": "stage I-II share is published nationally only",
    "slow_symptom_route": "symptom-to-referral times are not recorded (strategy 2.5)",
    "late_stage_pattern": "stage distribution is published nationally only",
    "low_symptom_awareness": "symptom awareness is not measured by county",
    "treatment_mix_deviates": "lung first-line treatment mix is not published by county",
    "digital_pathway_in_use": "digital pathway use is not published by county",
    "public_private_delay_suspected": "access times are not published by county",
}
# Facts that can be computed in principle but have no value for some counties: the reason, if known.
MISSING_REASON = {
    "max_subgroup_gap_pp": "participation by mother tongue and education is published nationally only",
    "primary_care_trend_worse": "the care-guarantee definition changed in 9/2023 and 1/2025, so there is no comparable trend",
}
FACT_NAMES = frozenset(
    {f"stage_{s}" for s in STAGES} | {f"visibility_{s}" for s in STAGES} | {f"gap_{s}" for s in STAGES}
    | {"stage_coverage", "screening_stats_annual", "leaking_participation_below_target", "max_subgroup_gap_pp",
       "primary_care_trend_worse", "distance_above_median", "lung_curative_leak", "share_75_above_national",
       "primary_care_worse_than_national"} | set(NO_PUBLIC_DATA)
)
_OPS = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge, "==": operator.eq, "!=": operator.ne}
_CONDITION = re.compile(r"^([a-z_0-9]+) (<=|>=|==|!=|<|>) ([a-z_0-9.]+)$")
OWNER_LABEL = {"national": "National lead, county supports", "joint": "Joint, national body and county",
               "county": "County"}


def _operand(token: str, thresholds):
    if re.fullmatch(r"-?\d+(\.\d+)?", token):
        return float(token)
    if token in STATES:
        return token
    if hasattr(thresholds, token) and isinstance(getattr(thresholds, token), (int, float)):
        return float(getattr(thresholds, token))
    raise ValueError(f"unknown value {token!r}")


def evaluate_condition(text: str, facts: dict, thresholds) -> bool | None:
    """'fact op value' -> True / False / None (fact unknown). Nothing else is accepted (no eval)."""
    match = _CONDITION.match(text.strip())
    if not match:
        raise ValueError(f"not a condition: {text!r}")
    name, op, token = match.groups()
    if name not in FACT_NAMES:
        raise ValueError(f"unknown fact {name!r}")
    right = _operand(token, thresholds)
    left = facts.get(name)
    if left is None or (isinstance(left, float) and pd.isna(left)):
        return None
    if isinstance(right, str) != isinstance(left, str):
        raise ValueError(f"type mismatch in {text!r}")
    return bool(_OPS[op](left, right))


def _all(values) -> bool | None:
    values = list(values)
    return False if False in values else (None if None in values else True)


def _any(values) -> bool | None:
    values = list(values)
    return True if True in values else (None if None in values else False)


@dataclass(frozen=True)
class RuleOutcome:
    rule_id: str
    status: str                 # fires | not triggered | needs data | blocked
    verb: str                   # Implement | Test
    owner_label: str
    missing: tuple[str, ...]    # unknown facts, each with the reason there is no data
    rank: tuple = ()
    missing_reasons: tuple[str, ...] = ()


def evaluate_rule(rule, facts: dict, thresholds) -> RuleOutcome:
    trigger = _all(evaluate_condition(c, facts, thresholds) for c in rule.when)
    if rule.when_any:
        trigger = _all([trigger, _any(evaluate_condition(c, facts, thresholds) for c in rule.when_any)])
    blocked = any(evaluate_condition(c, facts, thresholds) is not False for c in rule.do_not_fire_if)
    if trigger is False:
        status = "not triggered"
    elif blocked:
        status = "blocked"
    else:
        status = "fires" if trigger else "needs data"
    used = [c.split()[0] for c in (*rule.when, *rule.when_any)]
    unknown = [n for n in dict.fromkeys(used) if facts.get(n) is None]
    reasons = tuple(NO_PUBLIC_DATA.get(n) or MISSING_REASON.get(n, "no value for this county") for n in unknown)
    needs = status == "needs data"
    return RuleOutcome(rule.id, status, "Test" if rule.mode == "test" else "Implement",
                       f"{OWNER_LABEL[rule.owner_level]}: {rule.owner}",
                       tuple(f"{n} ({r})" for n, r in zip(unknown, reasons)) if needs else (),
                       missing_reasons=reasons if needs else ())


@dataclass(frozen=True)
class Plan:
    outcomes: tuple[RuleOutcome, ...]   # every rule, in rule-file order
    top: tuple[RuleOutcome, ...]        # at most 3 fired rules, ranked
    message: str


def county_plan(facts: dict, thresholds, rules=None) -> Plan:
    from equal_path.config import load_rules

    rules = rules or load_rules()
    by_id = {r.id: r for r in rules}
    outcomes = tuple(evaluate_rule(r, facts, thresholds) for r in rules)

    def rank(o: RuleOutcome) -> tuple:
        rule = by_id[o.rule_id]
        if o.rule_id in PRECONDITION_RULES:
            return (0, 0.0, o.rule_id)
        if not rule.data_capture:
            return (1, -float(facts.get(f"gap_{rule.stage}") or 0.0), o.rule_id)
        return (2, 0.0, o.rule_id)

    fired = sorted((o for o in outcomes if o.status == "fires"), key=rank)
    verified_gap = any(facts.get(f"stage_{s}") == "leak" for s in STAGES)
    if not verified_gap:
        message = NO_VERIFIED_GAP
    elif any(o.rule_id in PRECONDITION_RULES for o in fired):
        message = DATA_CAPTURE_FIRST
    elif any(not by_id[o.rule_id].data_capture for o in fired[:3]):
        message = GAP_ACTIONS
    else:
        message = GAP_NEEDS_DATA
    return Plan(outcomes, tuple(fired[:3]), message)


# --- facts from the real data ------------------------------------------------------------------

def _latest_unit(store, indicator, code, subgroup="all"):
    rows = store[(store.indicator_id == indicator) & (store.county_id == code) & (store.geo_level == "unit")
                 & (store.subgroup == subgroup) & store.value.notna()]
    return None if rows.empty else float(rows.sort_values("period").value.iloc[-1])


def _stage_coverage(store, code, area_code) -> tuple[float | None, str, str, str]:
    rows = store[(store.indicator_id == "stage_recording_coverage") & (store.subgroup == "all") & store.value.notna()]
    area_key = str(area_code) if str(area_code).startswith("YTA") else f"YTA{area_code}"   # units.csv: '3'; store: 'YTA3'
    for level, key in (("unit", code), ("cooperation_area", area_key), ("national", "FI")):
        hit = rows[(rows.geo_level == level) & (rows.county_id == key)]
        if len(hit):
            label = {"unit": "county", "cooperation_area": "cooperation area", "national": "national"}[level]
            row = hit.sort_values("period").iloc[-1]
            return float(row.value), label, row.source_id, row.locator
    return None, "not published", "", ""


SUBGROUP_PAIRS = (("lang:domestic", "lang:other_or_missing"), ("edu:tertiary", "edu:primary_or_unknown"))


def _participation_facts(store, assessments, code) -> tuple[int, float | None]:
    leaking = assessments[(assessments.code == code) & (assessments.state == "leak")
                          & assessments.indicator_id.str.startswith("screening_participation")]
    below = leaking[leaking.value < SCREENING_TARGET]
    gaps = []
    for indicator, period in zip(below.indicator_id, below.period):
        rows = store[(store.indicator_id == indicator) & (store.county_id == code) & (store.period == period)
                     & (store.geo_level == "unit") & store.value.notna()].set_index("subgroup").value
        gaps += [(rows[a] - rows[b]) * 100 for a, b in SUBGROUP_PAIRS if a in rows and b in rows]
    return int(len(below) > 0), (max(gaps) if gaps else None)


def _trend_worse(store, catalog, indicator, code) -> int | None:
    from equal_path.glidepath import theil_sen

    rows = store[(store.indicator_id == indicator) & (store.county_id == code) & (store.geo_level == "unit")
                 & (store.subgroup == "all") & store.value.notna()].sort_values("period")
    if len(rows) < 3:
        return None
    slope, _ = theil_sen([int(p[:4]) for p in rows.period], list(rows.value))
    return int(slope > 0) if catalog[indicator].direction == "lower_better" else int(slope < 0)


def _above_median(store, indicator, codes, code) -> int | None:
    values = {c: _latest_unit(store, indicator, c) for c in codes}
    known = [v for v in values.values() if v is not None]
    return None if values.get(code) is None or not known else int(values[code] > statistics.median(known))


def _above_national(store, indicator, code) -> int | None:
    share = _latest_unit(store, indicator, code)
    national = store[(store.indicator_id == indicator) & (store.geo_level == "national") & (store.subgroup == "all")
                     & store.value.notna()]
    return None if share is None or national.empty else int(share > float(national.sort_values("period").value.iloc[-1]))


def county_facts(code, result, store, catalog, units, thresholds=None) -> dict:
    from equal_path.config import load_thresholds

    thresholds = thresholds or load_thresholds()
    a = result.assessments
    unit = units.set_index("code").loc[code]
    facts: dict = {name: None for name in NO_PUBLIC_DATA}
    for stage in STAGES:
        facts[f"stage_{stage}"] = result.stages.loc[code, stage]
        facts[f"visibility_{stage}"] = float(result.visibility.loc[code, stage])
        leaks = a[(a.code == code) & (a.stage == stage) & (a.state == "leak")]
        facts[f"gap_{stage}"] = float(leaks[["gap_national", "gap_twin"]].min(axis=1).max()) if len(leaks) else 0.0
        facts[f"gap_sources_{stage}"] = "; ".join(sorted({s for i in leaks.indicator_id for s in catalog[i].source_ids}))
    (facts["stage_coverage"], facts["stage_coverage_level"], facts["stage_coverage_source"],
     facts["stage_coverage_locator"]) = _stage_coverage(store, code, unit.coop_area_code)
    periods = store.loc[store.indicator_id.str.startswith("screening_participation"), "period"]
    facts["screening_stats_annual"] = int(len(periods) > 0 and periods.str.fullmatch(r"\d{4}").all())
    facts["leaking_participation_below_target"], facts["max_subgroup_gap_pp"] = _participation_facts(store, a, code)
    # _trend_worse is ready, but the Sotkanet 6411 series breaks at the 9/2023 and 1/2025 law changes (catalog
    # limitation), so no comparable trend exists yet (review E-7)
    facts["primary_care_trend_worse"] = None
    facts["distance_above_median"] = _above_median(store, "cov_distance_university_hospital_km", result.stages.index, code)
    lung = a[(a.code == code) & (a.indicator_id == "lung_curative_route_share")]
    facts["lung_curative_leak"] = None if lung.empty else int((lung.state == "leak").any())
    facts["share_75_above_national"] = _above_national(store, "cov_share_aged_75_plus", code)
    access = a[(a.code == code) & (a.indicator_id == "primary_care_access") & a.gap_national.notna()]
    facts["primary_care_worse_than_national"] = (None if access.empty else
                                                 int((access.gap_national >= thresholds.min_practical_gap_pp / 100).any()))
    facts["visibility_score"] = float(result.visibility.loc[code, "score"])
    return facts


@dataclass(frozen=True)
class ActionRun:
    plans: dict
    facts: dict
    primary: dict
    names: dict
    coop_area: dict
    confidence: dict = field(default_factory=dict)   # code -> stage -> 'high' | 'medium' | 'low'


def run_actions(store: pd.DataFrame | None = None, result=None) -> ActionRun:
    from equal_path.config import load_indicator_catalog, load_rules, load_thresholds
    from equal_path.geography import load_units
    from equal_path.observations import load_observations
    from equal_path.pathway import run_pathway

    store = load_observations() if store is None else store
    result = run_pathway(store) if result is None else result
    catalog = {i.id: i for i in load_indicator_catalog()}
    units, thresholds, rules = load_units(), load_thresholds(), load_rules()
    facts = {code: county_facts(code, result, store, catalog, units, thresholds) for code in result.stages.index}
    plans = {code: county_plan(f, thresholds, rules) for code, f in facts.items()}
    from equal_path.confidence import county_confidence

    confidence = {code: {s: c.level for s, c in county_confidence(result, code, thresholds).items()} for code in facts}
    return ActionRun(plans, facts, dict(result.primary_leak), dict(zip(units.code, units.short_fi)),
                     dict(zip(units.code, units.coop_area_fi)), confidence)
