"""Observations store (long format, section 7.2), built by scripts/build_observations.py."""

from __future__ import annotations

from dataclasses import replace
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable

import pandas as pd

from equal_path.config import Anchor, Thresholds
from equal_path.paths import OBSERVATIONS_FILE
from equal_path.spine import OBS_COLUMNS, ReconcileResult, ReconcileSpec, make_observations, reconcile_one


def load_observations(path: Path = OBSERVATIONS_FILE) -> pd.DataFrame:
    """The store, or an empty frame with the right columns when nothing is built yet."""
    if not path.exists():
        return make_observations([])
    try:
        frame = pd.read_parquet(path)
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read {path.name}: {exc}") from exc
    if tuple(frame.columns) != OBS_COLUMNS:
        raise ValueError(f"{path.name}: columns {list(frame.columns)} != {list(OBS_COLUMNS)}")
    return frame


def indicator_counts(path: Path = OBSERVATIONS_FILE) -> dict[str, int]:
    """Distinct indicators WITH A VALUE per unit; area/national rows never count for a unit."""
    frame = load_observations(path)
    units = frame[(frame.geo_level == "unit") & frame.value.notna()]
    counts = units.groupby("county_id")["indicator_id"].nunique()
    return {str(code): int(count) for code, count in counts.items()}


def status_problems(frame: pd.DataFrame, catalog: Iterable) -> list[str]:
    """Catalog status must match the store: available = all 22 units have a value;
    partial = values exist but not for all 22 units; not_public / to_verify = no values."""
    with_value = frame[frame.value.notna()]
    units = with_value[with_value.geo_level == "unit"].groupby("indicator_id").county_id.nunique()
    any_value = set(with_value.indicator_id)
    problems = []
    for indicator in catalog:
        n_units = int(units.get(indicator.id, 0))
        if indicator.status == "available" and n_units != 22:
            problems.append(f"{indicator.id}: marked available but {n_units} of 22 units have values")
        elif indicator.status == "partial" and (indicator.id not in any_value or n_units == 22):
            problems.append(f"{indicator.id}: marked partial but has {'no values' if indicator.id not in any_value else 'all 22 units'}")
        elif indicator.status in ("not_public", "to_verify") and indicator.id in any_value:
            problems.append(f"{indicator.id}: has values but is marked {indicator.status}")
    return problems


def _min_check(frame: pd.DataFrame, anchor: Anchor) -> ReconcileResult:
    """Bound anchors such as 'lowest county participation under 68 %'."""
    rule = anchor.reconcile
    rows = frame[frame.indicator_id.map(lambda i: fnmatch(i, rule.indicator_id)) & (frame.period == rule.period)
                 & (frame.subgroup == rule.subgroup) & (frame.geo_level == "unit") & frame.value.notna()]
    bound = anchor.high if anchor.high is not None else anchor.low
    if rows.empty:
        return ReconcileResult(rule.indicator_id, rule.period, "min", bound, None, None, "within bounds", "no_data", "", anchor.id)
    lowest = rows.loc[rows.value.idxmin()]
    ok = (anchor.low is None or lowest.value >= anchor.low) and (anchor.high is None or lowest.value < anchor.high)
    detail = f"lowest: {lowest.indicator_id} unit {lowest.county_id} = {lowest.value:.3f}"
    return ReconcileResult(rule.indicator_id, rule.period, "min", bound, float(lowest.value), float(lowest.value) - bound,
                           f"< {anchor.high}" if anchor.high is not None else f">= {anchor.low}", "pass" if ok else "fail", detail, anchor.id)


def reconcile_anchors(frame: pd.DataFrame, anchors: Iterable[Anchor], thresholds: Thresholds) -> list[ReconcileResult]:
    """One result per anchor. Anchors without a rule are reported as not_checked, never hidden."""
    results = []
    for anchor in anchors:
        rule = anchor.reconcile
        if rule is None:
            published = anchor.value if anchor.value is not None else (anchor.high if anchor.high is not None else anchor.low)
            results.append(ReconcileResult("", anchor.period, "-", published, None, None, "-", "not_checked",
                                           anchor.note or "no reconciliation rule", anchor.id))
            continue
        if rule.method == "min":
            results.append(_min_check(frame, anchor))
            continue
        spec = ReconcileSpec(**rule.model_dump())
        result = reconcile_one(frame, spec, published=anchor.value,
                               counts_rel_tol=thresholds.reconciliation_counts_rel_tol,
                               pct_abs_tol_pp=thresholds.reconciliation_pct_abs_tol_pp)
        results.append(replace(result, anchor_id=anchor.id))
    return results
