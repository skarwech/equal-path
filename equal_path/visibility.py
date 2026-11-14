"""F1 visibility score: how much of each county's pathway is observable from public data.

Rules (config/visibility.yaml): stage membership from the catalog; equal weights within a
stage; the four pathway stages combine with the frozen stage weights into 0-100; timing is a
separate row. Observable = real, current, unit-level, adequately sized data (see
`observable_matrix`); injected or area-only values never make a county visible.
"""

from __future__ import annotations

import re
from typing import Iterable, Mapping

import pandas as pd

COMPOSITE_STAGES = ("detection", "referral", "diagnosis", "treatment")
SEPARATE_STAGES = ("timing",)
OBSERVABLE_STATUSES = frozenset({"available", "partial"})
OBSERVABLE_SOURCES = frozenset({"retrieved", "verified"})


def _get(entry, key):
    return entry[key] if isinstance(entry, Mapping) else getattr(entry, key)


def stage_members(catalog: Mapping) -> dict[str, tuple[str, ...]]:
    """Catalog indicators per stage, in catalog order (covariates and context excluded)."""
    members: dict[str, list[str]] = {stage: [] for stage in COMPOSITE_STAGES + SEPARATE_STAGES}
    for indicator_id, entry in catalog.items():
        stage = _get(entry, "stage")
        if stage in members:
            members[stage].append(indicator_id)
    return {stage: tuple(ids) for stage, ids in members.items()}


def within_stage_weights(members: Mapping[str, Iterable[str]]) -> dict[str, dict[str, float]]:
    weights = {}
    for stage, ids in members.items():
        ids = list(ids)
        weights[stage] = {i: 1.0 / len(ids) for i in ids} if ids else {}
    return weights


def period_end(period: str) -> int:
    """Sort key: the last year mentioned ('2019-2023' -> 2023, '2024-06' -> 2024)."""
    years = re.findall(r"\d{4}", str(period))
    return int(years[-1]) if years else -1


def latest_period(rows: pd.DataFrame) -> str | None:
    if rows.empty:
        return None
    periods = sorted(set(rows.period), key=lambda p: (period_end(p), p))
    return periods[-1]


def headline_rows(store: pd.DataFrame, indicator_id: str) -> pd.DataFrame:
    """Unit rows of the latest period; subgroup 'all' when the indicator has one."""
    rows = store[(store.indicator_id == indicator_id) & (store.geo_level == "unit")]
    period = latest_period(rows[rows.value.notna()])  # an all-missing newer release does not blank older data
    rows = rows[rows.period == period]
    if (rows.subgroup == "all").any():
        rows = rows[rows.subgroup == "all"]
    return rows


def observable_matrix(store: pd.DataFrame, catalog: Mapping, unit_codes: Iterable[str],
                      min_denominator: float, registry: Mapping[str, str]) -> pd.DataFrame:
    """Boolean unit x indicator matrix for every stage member."""
    codes = list(unit_codes)
    members = stage_members(catalog)
    indicators = [i for ids in members.values() for i in ids]
    matrix = pd.DataFrame(False, index=codes, columns=indicators)
    for indicator_id in indicators:
        entry = catalog[indicator_id]
        if _get(entry, "status") not in OBSERVABLE_STATUSES:
            continue
        listed = set(_get(entry, "source_ids"))
        rows = headline_rows(store, indicator_id)
        rows = rows[rows.value.notna() & rows.source_id.isin(listed)
                    & rows.source_id.map(lambda s: registry.get(s) in OBSERVABLE_SOURCES)]
        rows = rows[rows.denominator.isna() | (rows.denominator >= min_denominator)]
        visible = set(rows.county_id)
        matrix[indicator_id] = [code in visible for code in codes]
    return matrix


def visibility_scores(observable: pd.DataFrame, members: Mapping[str, Iterable[str]],
                      stage_weights: Mapping[str, float]) -> pd.DataFrame:
    """Per-stage visibility (0-1), timing separately, and the 0-100 composite score."""
    weights = within_stage_weights(members)
    out = pd.DataFrame(index=observable.index)
    for stage in COMPOSITE_STAGES + SEPARATE_STAGES:
        stage_w = weights.get(stage, {})
        out[stage] = sum(observable[i].astype(float) * w for i, w in stage_w.items()) if stage_w else 0.0
    out["score"] = 100.0 * sum(out[stage] * stage_weights[stage] for stage in COMPOSITE_STAGES)
    return out


def coverage_tier(value: float | None, target: float, partial_min: float) -> str:
    """F1 stage-recording coverage tier (thresholds.yaml); None = not published for this unit."""
    if value is None or pd.isna(value):
        return "not published"
    if value >= target:
        return "target"
    return "partial" if value >= partial_min else "low"
