"""F6 screening scenario calculator.

This is a sensitivity model, not a forecast. It extrapolates the observed 2024
screening yield to additional attendees and keeps stage mix as an explicit user
assumption because regional stage distributions are not available.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd


PERIOD = "2024"
UNIT_COUNT = 22
PROGRAMMES = {
    "Breast": {
        "id": "breast",
        "participation": "screening_participation_breast",
        "detection_subgroup": "prog:breast",
        "eligible_label": "invited",
    },
    "Cervical": {
        "id": "cervical",
        "participation": "screening_participation_cervical",
        "detection_subgroup": "prog:cervical_age",
        "eligible_label": "invited",
    },
    "Colorectal": {
        "id": "colorectal",
        "participation": "screening_participation_colorectal",
        "detection_subgroup": "prog:colorectal",
        "eligible_label": "picked for invitation",
    },
}


@dataclass(frozen=True)
class ScreeningBaseline:
    programme: str
    code: str
    eligible_label: str
    eligible: int
    attended: int
    participation: float
    county_detections: int
    pooled_attended: int
    pooled_detections: int
    participation_source: str
    participation_locator: str
    detection_source: str
    detection_locator: str

    @property
    def yield_per_attendee(self) -> float:
        return self.pooled_detections / self.pooled_attended


@dataclass(frozen=True)
class ScenarioResult:
    baseline: ScreeningBaseline
    target_participation: float
    assumed_early_stage_share: float
    additional_attendees: int
    detection_yield_low: float
    detection_yield_median: float
    detection_yield_high: float
    additional_detections_low: float
    additional_detections_median: float
    additional_detections_high: float
    early_stage_low: float
    early_stage_median: float
    early_stage_high: float
    draws: int
    interval: float


def _valid_values(rows: pd.DataFrame, column: str) -> bool:
    return not rows.empty and rows[column].notna().all()


def screening_baseline(store: pd.DataFrame, code: str, programme: str) -> tuple[ScreeningBaseline | None, str]:
    """Read a complete 2024 unit-level baseline without filling missing cells."""
    if programme not in PROGRAMMES:
        raise ValueError(f"unknown screening programme {programme!r}")
    spec = PROGRAMMES[programme]
    participation = store[
        (store.indicator_id == spec["participation"])
        & (store.period == PERIOD)
        & (store.subgroup == "all")
        & (store.geo_level == "unit")
    ]
    county = participation[participation.county_id == code]
    if len(county) != 1:
        return None, f"No single 2024 {programme.lower()} participation row is available for this county."
    county = county.iloc[0]
    if pd.isna(county.numerator) or pd.isna(county.denominator) or county.denominator <= 0:
        return None, f"The 2024 {programme.lower()} attendance numerator or denominator is missing."

    attendance_rows = participation
    if attendance_rows.county_id.nunique() != UNIT_COUNT or not _valid_values(attendance_rows, "numerator"):
        return None, f"The 2024 {programme.lower()} attendance total is incomplete across the 22 units."
    if not _valid_values(attendance_rows, "denominator") or (attendance_rows.denominator <= 0).any():
        return None, f"The 2024 {programme.lower()} eligible-population total is incomplete."

    detected = store[
        (store.indicator_id == "screening_cancers_detected")
        & (store.period == PERIOD)
        & (store.subgroup == spec["detection_subgroup"])
        & (store.geo_level == "unit")
    ]
    county_detected = detected[detected.county_id == code]
    if len(county_detected) != 1 or pd.isna(county_detected.iloc[0].value):
        return None, f"The 2024 {programme.lower()} cancer-detection count is missing for this county."
    if detected.county_id.nunique() != UNIT_COUNT or not _valid_values(detected, "value"):
        return None, f"The 2024 {programme.lower()} detection total is incomplete across the 22 units."

    eligible = int(county.denominator)
    attended = int(county.numerator)
    pooled_attended = int(attendance_rows.numerator.sum())
    pooled_detections = int(detected.value.sum())
    if attended < 0 or attended > eligible:
        return None, "The published attendance counts are inconsistent (attended exceeds invited/picked)."
    if pooled_attended <= 0 or pooled_detections < 0 or pooled_detections > pooled_attended:
        return None, "The pooled 2024 screening counts cannot support a detection-yield estimate."

    detection_rows = detected.sort_values("county_id")
    locators = sorted(set(detection_rows.locator.astype(str)))
    return ScreeningBaseline(
        programme=programme,
        code=code,
        eligible_label=spec["eligible_label"],
        eligible=eligible,
        attended=attended,
        participation=attended / eligible,
        county_detections=int(county_detected.iloc[0].value),
        pooled_attended=pooled_attended,
        pooled_detections=pooled_detections,
        participation_source=str(county.source_id),
        participation_locator=str(county.locator),
        detection_source="; ".join(sorted(set(detection_rows.source_id.astype(str)))),
        detection_locator="; ".join(locators),
    ), ""


def simulate_screening(
    baseline: ScreeningBaseline,
    target_participation: float,
    assumed_early_stage_share: float = 0.0,
    *,
    draws: int = 5_000,
    interval: float = 0.80,
    seed: int = 2026,
) -> ScenarioResult:
    """Run a reproducible Monte Carlo sensitivity scenario.

    Jeffreys Beta(0.5, 0.5) posterior draws represent uncertainty around the
    pooled 2024 observed cancer yield. Applying each draw to the same extra-
    attendee count keeps estimates and interval bounds monotonic as the target
    rises. The stage-mix share is supplied by the caller, not estimated from
    regional stage data.
    """
    if not math.isfinite(target_participation) or not baseline.participation <= target_participation <= 1:
        raise ValueError("target participation must be between the county baseline and 1")
    if not math.isfinite(assumed_early_stage_share) or not 0 <= assumed_early_stage_share <= 1:
        raise ValueError("assumed early-stage share must be between 0 and 1")
    if draws <= 0 or not 0 < interval < 1:
        raise ValueError("draws must be positive and interval must be between 0 and 1")

    extra = max(0, int(math.floor((target_participation - baseline.participation) * baseline.eligible + 0.5)))
    rng = np.random.default_rng(seed)
    yield_draws = rng.beta(
        baseline.pooled_detections + 0.5,
        baseline.pooled_attended - baseline.pooled_detections + 0.5,
        size=draws,
    )
    detection_draws = extra * yield_draws
    stage_draws = detection_draws * assumed_early_stage_share
    tail = (1 - interval) / 2
    q_low, q_median, q_high = (float(v) for v in np.quantile(yield_draws, [tail, 0.5, 1 - tail]))
    d_low, d_median, d_high = (float(v) for v in np.quantile(detection_draws, [tail, 0.5, 1 - tail]))
    s_low, s_median, s_high = (float(v) for v in np.quantile(stage_draws, [tail, 0.5, 1 - tail]))
    return ScenarioResult(
        baseline=baseline,
        target_participation=target_participation,
        assumed_early_stage_share=assumed_early_stage_share,
        additional_attendees=extra,
        detection_yield_low=q_low,
        detection_yield_median=q_median,
        detection_yield_high=q_high,
        additional_detections_low=d_low,
        additional_detections_median=d_median,
        additional_detections_high=d_high,
        early_stage_low=s_low,
        early_stage_median=s_median,
        early_stage_high=s_high,
        draws=draws,
        interval=interval,
    )
