"""Run F1 (visibility) and F2 (gap locator, with the twin core) over the observations store."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from equal_path.config import load_indicator_catalog, load_thresholds
from equal_path.gaps import SeriesInput, assess_series, bonferroni_z, stage_state
from equal_path.geography import UNIT_CODES
from equal_path.observations import load_observations
from equal_path.sources import load_sources
from equal_path.twins import Twins, better_twins, covariate_matrix, stability, twin_sets
from equal_path.visibility import (
    COMPOSITE_STAGES, SEPARATE_STAGES, coverage_tier, headline_rows, observable_matrix, stage_members,
    visibility_scores,
)

ASSESSED_UNITS = frozenset({"share", "ratio"})
NO_LEAK_ALL_UNKNOWN = "cannot localise; the data gap is the finding"
NO_LEAK = "no verified leak"


@dataclass(frozen=True)
class PathwayResult:
    visibility: pd.DataFrame            # unit x (stages, timing, score)
    observable: pd.DataFrame            # unit x indicator (bool)
    twins: dict[str, Twins]
    assessments: pd.DataFrame           # one row per unit x indicator series
    stages: pd.DataFrame                # unit x stage -> leak / watch / ok / unknown
    primary_leak: dict[str, str]
    coverage_tiers: dict[str, str]
    z_by_stage: dict[str, float]
    twin_stability: dict[str, float]


def eligible_series(store: pd.DataFrame, catalog: dict, observable: pd.DataFrame,
                    min_denominator: float = 30) -> list[SeriesInput]:
    """Series F2 can judge: pathway stage, a direction, a share or ratio. Uses F1's headline period,
    headline subgroups (from unit rows) and observable units, so F1 and F2 never disagree; units
    F1 does not count come back as 'unknown' rows with the reason."""
    series = []
    for indicator_id, entry in catalog.items():
        if entry.stage not in COMPOSITE_STAGES or entry.direction == "context" or entry.unit not in ASSESSED_UNITS:
            continue
        if entry.status not in ("available", "partial") or indicator_id not in observable:
            continue
        headline = headline_rows(store, indicator_id)
        if headline.empty:
            continue
        period = headline.period.iloc[0]
        visible = set(observable.index[observable[indicator_id]])
        rows = store[(store.indicator_id == indicator_id) & (store.period == period) & store.source_id.isin(entry.source_ids)]
        for subgroup in sorted(set(headline.subgroup)):
            part = rows[rows.subgroup == subgroup]
            all_units = part[(part.geo_level == "unit") & part.value.notna()]
            units = all_units[all_units.county_id.isin(visible)]
            excluded = {}
            for code, n in zip(all_units.county_id, all_units.denominator):
                if code not in visible:
                    excluded[code] = (f"denominator {n:.0f} < {min_denominator:.0f}" if pd.notna(n) and n < min_denominator
                                      else "not observable (source or catalog status)")
            national = part[(part.geo_level == "national") & part.value.notna()]
            if len(national) == 1:
                national_value = float(national.value.iloc[0])
            elif len(all_units) and all_units.denominator.notna().all():  # pooled over every unit row, visible or not
                national_value = float((all_units.value * all_units.denominator).sum() / all_units.denominator.sum())
            else:
                national_value = None
            series.append(SeriesInput(
                indicator_id=indicator_id, subgroup=subgroup, stage=entry.stage, direction=entry.direction,
                values=dict(zip(units.county_id, units.value)),
                denominators={c: d for c, d in zip(units.county_id, units.denominator) if pd.notna(d)},
                ci={c: (lo, hi) for c, lo, hi in zip(units.county_id, units.ci_low, units.ci_high) if pd.notna(lo)},
                national=national_value, period=period, unit=entry.unit, excluded=excluded,
            ))
    return series


def stage_z(series: list[SeriesInput], z: float) -> dict[str, float]:
    """Bonferroni within a stage: per-series level / number of testable series in that stage."""
    testable = {}
    for s in series:
        if s.denominators or s.ci:
            testable[s.stage] = testable.get(s.stage, 0) + 1
    return {stage: bonferroni_z(z, testable.get(stage, 1)) for stage in COMPOSITE_STAGES}


def _primary(code: str, stages: pd.Series, assessments: pd.DataFrame) -> str:
    leaking = [s for s in COMPOSITE_STAGES if stages[s] == "leak"]
    if not leaking:
        return NO_LEAK_ALL_UNKNOWN if all(stages[s] == "unknown" for s in COMPOSITE_STAGES) else NO_LEAK
    rows = assessments[(assessments.code == code) & (assessments.state == "leak") & assessments.stage.isin(leaking)]
    # verified gap = the smaller of the gaps under the references used
    rows = rows.assign(verified=rows[["gap_national", "gap_twin"]].min(axis=1, skipna=True))
    best = rows.sort_values(["verified", "stage", "indicator_id"], ascending=[False, True, True]).iloc[0]
    return f"{best.stage}: {best.indicator_id} ({best.subgroup}) {best.verified * 100:.1f} pp worse"


def run_pathway(store: pd.DataFrame | None = None) -> PathwayResult:
    store = load_observations() if store is None else store
    catalog = {i.id: i for i in load_indicator_catalog()}
    thresholds = load_thresholds()
    registry = dict(zip(load_sources().source_id, load_sources().status))
    codes = list(UNIT_CODES)

    observable = observable_matrix(store, catalog, codes, thresholds.min_denominator, registry)
    members = stage_members(catalog)
    visibility = visibility_scores(observable, members, thresholds.visibility_stage_weights.model_dump())

    covariates = covariate_matrix(store, codes)
    twins = twin_sets(covariates, thresholds.twin_k, thresholds.no_good_twin_percentile)
    twin_stability = stability(covariates, thresholds.twin_k, thresholds.twin_noise_fraction, draws=200, seed=20261114)
    twin_lists = {code: t.twins for code, t in twins.items()}
    good = {code: t.good for code, t in twins.items()}

    records = []
    series_list = eligible_series(store, catalog, observable, thresholds.min_denominator)
    z_by_stage = stage_z(series_list, thresholds.wilson_z)
    for series in series_list:
        for assessment in assess_series(series, twin_lists, good, z_by_stage[series.stage],
                                        thresholds.min_practical_gap_pp, thresholds.min_denominator).values():
            better = (better_twins(assessment.value, twin_lists[assessment.code], series.values, series.direction)
                      if assessment.value is not None else ())
            records.append({**assessment.__dict__, "period": series.period, "direction": series.direction,
                            "better_twins": better})
    assessments = pd.DataFrame(records)

    stages = pd.DataFrame(index=codes, columns=list(COMPOSITE_STAGES + SEPARATE_STAGES), dtype=object)
    for code in codes:
        for stage in COMPOSITE_STAGES + SEPARATE_STAGES:
            states = assessments.loc[(assessments.code == code) & (assessments.stage == stage), "state"] if not assessments.empty else []
            stages.loc[code, stage] = stage_state(float(visibility.loc[code, stage]), list(states), thresholds.min_stage_visibility)

    coverage = store[(store.indicator_id == "stage_recording_coverage") & (store.geo_level == "unit")].set_index("county_id")
    tiers = {code: coverage_tier(coverage.value.get(code), thresholds.stage_coverage_target, thresholds.stage_coverage_partial_min)
             for code in codes}
    primary = {code: _primary(code, stages.loc[code], assessments) for code in codes}
    return PathwayResult(visibility, observable, twins, assessments, stages, primary, tiers, z_by_stage, twin_stability)
