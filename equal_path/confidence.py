"""F8 county page: a confidence badge per stage, and why a stage is grey (Unknown).

The spec names a confidence badge but does not define it. This rule uses only thresholds frozen
before any county result was loaded, so no number was chosen after seeing results:
  low     the stage is too little observable: low_visibility(), the same test as F2's Leak gate
  high    observable enough, every judged series has a published n or CI (significance testable),
          and the county has a good, stable twin set (Jaccard >= twin_stability_jaccard)
  medium  otherwise; every downgrade lists its reason
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from equal_path.coverage import AREA_ONLY, NONE, SUPPRESSED, VALUE, coverage_matrix
from equal_path.gaps import low_visibility
from equal_path.visibility import COMPOSITE_STAGES, SEPARATE_STAGES, stage_members

LEVELS = ("high", "medium", "low")
CAUSE = {
    AREA_ONLY: "area or national level only",
    SUPPRESSED: "suppressed or missing",
    NONE: "no public data loaded",
    VALUE: "value not usable here (n < 30, not the latest period, or source not retrieved)",
}


@dataclass(frozen=True)
class Confidence:
    level: str
    reasons: tuple[str, ...] = ()


def _has_interval(value) -> bool:
    return isinstance(value, tuple)


def stage_confidence(visibility: float, rows: pd.DataFrame, twins_good: bool, stability: float, *,
                     min_stage_visibility: float, min_stability: float) -> Confidence:
    """`rows`: this county's assessed series in this stage (columns state, interval)."""
    if low_visibility(visibility, min_stage_visibility):
        return Confidence("low", (f"only {visibility:.0%} of the stage is observable (below {min_stage_visibility:.0%})",))
    reasons = []
    judged = rows[rows.state != "unknown"] if len(rows) else rows
    if judged.empty:
        reasons.append("no indicator in this stage could be judged")
    else:
        untestable = sum(not _has_interval(i) for i in judged.interval)
        if untestable:
            reasons.append(f"{untestable} of {len(judged)} judged series have no published n or CI, "
                           "so significance cannot be tested")
    if not twins_good:
        reasons.append("no good twin: national reference only")
    elif stability < min_stability:
        reasons.append(f"twin set unstable (stability {stability:.2f} < {min_stability:g})")
    return Confidence("medium" if reasons else "high", tuple(reasons))


def county_confidence(result, code: str, thresholds) -> dict[str, Confidence]:
    out = {}
    for stage in COMPOSITE_STAGES + SEPARATE_STAGES:
        rows = result.assessments[(result.assessments.code == code) & (result.assessments.stage == stage)]
        out[stage] = stage_confidence(float(result.visibility.loc[code, stage]), rows, result.twins[code].good,
                                      result.twin_stability[code], min_stage_visibility=thresholds.min_stage_visibility,
                                      min_stability=thresholds.twin_stability_jaccard)
    return out


def _cause(entry, symbol: str) -> str:
    return "not published by county" if entry.status == "not_public" else CAUSE[symbol]


def stage_reason(result, store: pd.DataFrame, catalog: Mapping, code: str, stage: str, min_stage_visibility: float) -> str:
    """Why this county's stage is grey; '' when the stage is not Unknown."""
    if result.stages.loc[code, stage] != "unknown":
        return ""
    members = stage_members(catalog)[stage]
    observed = [m for m in members if m in result.observable.columns and bool(result.observable.loc[code, m])]
    visibility = float(result.visibility.loc[code, stage])
    lead = "Unknown: timing is a separate row (not in the score); " if stage in SEPARATE_STAGES else "Unknown: "
    if low_visibility(visibility, min_stage_visibility):
        text = (f"{lead}only {len(observed)} of {len(members)} indicators are observable ({visibility:.0%}, "
                f"below the {min_stage_visibility:.0%} needed to judge a stage).")
    else:
        rows = result.assessments[(result.assessments.code == code) & (result.assessments.stage == stage)]
        why = "; ".join(f"{catalog[i].label}: {r}" for i, r in zip(rows.indicator_id, rows.reason)) or "no assessable series"
        text = f"{lead}{len(observed)} of {len(members)} indicators observable, but none could be judged ({why})."
    if observed:
        text += " Observed: " + ", ".join(catalog[m].label for m in observed) + "."
    missing = [m for m in members if m not in observed]
    if missing:
        symbols = coverage_matrix(store, missing, {code: code})[code]
        text += " Missing: " + "; ".join(f"{catalog[m].label} ({_cause(catalog[m], symbols[m])})" for m in missing) + "."
    return text
