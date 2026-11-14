"""F4 glidepath: is a county's screening participation on course for the 80 % goal by 2035?

Theil-Sen trend on the annual series; case-resampling bootstrap (fixed seed) of the projected
value in the target year; interval = thresholds.simulator_interval (80 %). States:
on track (the Theil-Sen line AND the median bootstrap projection reach the target),
off track (upper bound < target), uncertain (otherwise), target met (latest value already
>= target), insufficient data (fewer than min_annual_points_glidepath points).
Requiring the robust line as well as the bootstrap median stops one final-year jump from
turning a flat or falling series 'on track' (review GP-1, real case unit 21 cervical). With 5
annual points one outlier year can still widen the interval enough to soften 'off track' to
'uncertain'; tests check it never reverses the verdict. Calibration: fit on all but the last
year and check that the interval covers the held-out value in 65-95 % of series; otherwise
the glidepath is labelled 'indicative'.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd

STATES = ("insufficient data", "target met", "on track", "off track", "uncertain")
SCREENING_TARGET = 0.80          # national goal: >= 80 % participation in every county (scope.yaml)
PROGRAMMES = {"breast": "screening_participation_breast", "cervical": "screening_participation_cervical",
              "colorectal": "screening_participation_colorectal"}
BOOTSTRAP_DRAWS = 2000
SEED = 20261114


@dataclass(frozen=True)
class Glidepath:
    state: str
    latest: float | None
    latest_year: int | None
    slope: float | None
    required_slope: float | None
    projection: float | None
    low: float | None
    high: float | None
    n_points: int
    point_projection: float | None = None   # Theil-Sen line at the target year (robust point estimate)


def theil_sen(years, values) -> tuple[float, float]:
    """Median of pairwise slopes; intercept = median of (y - slope * x)."""
    pairs = [(y2 - y1) / (x2 - x1) for (x1, y1), (x2, y2) in combinations(zip(years, values), 2) if x2 != x1]
    slope = statistics.median(pairs)
    intercept = statistics.median(y - slope * x for x, y in zip(years, values))
    return slope, intercept


def _bootstrap(years: np.ndarray, values: np.ndarray, at_year: int, draws: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out, attempts = [], 0
    n = len(years)
    while len(out) < draws and attempts < draws * 20:
        attempts += 1
        idx = rng.integers(0, n, n)
        if len(set(years[idx])) < 2:
            continue  # degenerate resample: no slope can be estimated
        slope, intercept = theil_sen(years[idx], values[idx])
        out.append(intercept + slope * at_year)
    return np.array(out)


def glidepath(years, values, target: float, target_year: int, draws: int, interval: float, seed: int,
              min_points: int) -> Glidepath:
    order = np.argsort(years)
    years, values = np.asarray(years, dtype=float)[order], np.asarray(values, dtype=float)[order]
    n = len(years)
    if n < min_points:
        return Glidepath("insufficient data", float(values[-1]) if n else None, int(years[-1]) if n else None,
                         None, None, None, None, None, n)
    latest, latest_year = float(values[-1]), int(years[-1])
    slope, intercept = theil_sen(years, values)
    point = intercept + slope * target_year
    projections = _bootstrap(years, values, target_year, draws, seed)
    tail = (1 - interval) / 2
    low, high = (float(q) for q in np.quantile(projections, [tail, 1 - tail]))
    median_projection = float(np.median(projections))
    if latest >= target:
        return Glidepath("target met", latest, latest_year, slope, None, median_projection, low, high, n, point)
    required = (target - latest) / (target_year - latest_year)
    if median_projection >= target and point >= target:
        state = "on track"
    elif high < target:
        state = "off track"
    else:
        state = "uncertain"
    return Glidepath(state, latest, latest_year, slope, required, median_projection, low, high, n, point)


def _series(store: pd.DataFrame, indicator: str) -> dict[str, list[tuple[int, float]]]:
    rows = store[(store.indicator_id == indicator) & (store.geo_level == "unit") & (store.subgroup == "all")
                 & store.value.notna()]
    out: dict[str, list[tuple[int, float]]] = {}
    for code, period, value in zip(rows.county_id, rows.period, rows.value):
        out.setdefault(code, []).append((int(period), float(value)))
    return {code: sorted(points) for code, points in out.items()}


def run_glidepaths(store: pd.DataFrame | None = None) -> pd.DataFrame:
    from equal_path.config import load_thresholds
    from equal_path.observations import load_observations

    store = load_observations() if store is None else store
    t = load_thresholds()
    records = []
    for programme, indicator in PROGRAMMES.items():
        for code, points in sorted(_series(store, indicator).items()):
            years, values = zip(*points)
            result = glidepath(years, values, SCREENING_TARGET, t.glidepath_target_year, BOOTSTRAP_DRAWS,
                               t.simulator_interval, SEED, t.min_annual_points_glidepath)
            records.append({"code": code, "programme": programme, "years": f"{years[0]}-{years[-1]}", **result.__dict__})
    return pd.DataFrame(records)


@dataclass(frozen=True)
class Calibration:
    series: int
    covered: int
    coverage: float
    label: str


def calibration(store: pd.DataFrame | None = None) -> Calibration:
    """Fit on all but the last year; does the interval at the last year cover the observed value?"""
    from equal_path.config import load_thresholds
    from equal_path.observations import load_observations

    store = load_observations() if store is None else store
    t = load_thresholds()
    tail = (1 - t.simulator_interval) / 2
    covered = total = 0
    for programme in ("breast", "cervical"):
        for points in _series(store, PROGRAMMES[programme]).values():
            if len(points) - 1 < t.min_annual_points_glidepath:
                continue
            years, values = (np.array(v, dtype=float) for v in zip(*points))
            predicted = _bootstrap(years[:-1], values[:-1], int(years[-1]), BOOTSTRAP_DRAWS, SEED)
            low, high = np.quantile(predicted, [tail, 1 - tail])
            covered += bool(low <= values[-1] <= high)
            total += 1
    coverage = covered / total if total else 0.0
    return Calibration(total, covered, coverage, "validated" if 0.65 <= coverage <= 0.95 else "indicative")
