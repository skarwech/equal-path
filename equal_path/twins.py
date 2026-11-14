"""Twin core (F3, used by F2): nearest counties on structural covariates only.

Covariates are z-scored across the 22 units; distance is Euclidean; the k nearest (ties broken
by code) are the twins. A county whose nearest twin is farther than the given percentile of all
pairwise distances has no good twin and falls back to the national reference.

Transform rule (fixed before any twin set was inspected): covariates spanning orders of
magnitude are log-transformed before z-scoring (density log10(x), distance log10(1 + km)).
Stability (spec F3): every raw covariate value is multiplied by 1 + U(-noise, +noise)
independently; per county the mean Jaccard overlap of the noisy and the original twin set.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

COVARIATES = (
    "cov_share_aged_75_plus", "cov_education", "cov_income",
    "cov_population_density", "cov_foreign_language_share", "cov_distance_university_hospital_km",
)
# Density spans three orders of magnitude (Helsinki vs Lapland); on a raw scale one city would
# set the spread and density would carry almost no weight for the other counties.
LOG_COVARIATES = ("cov_population_density",)
LOG1P_COVARIATES = ("cov_distance_university_hospital_km",)  # host counties are close to 0 km
TIE_TOLERANCE = 1e-9  # distances closer than this are ties, broken by code (not by float noise)


@dataclass(frozen=True)
class Twins:
    code: str
    twins: tuple[str, ...]
    distances: tuple[float, ...]
    good: bool
    drivers: tuple[tuple[str, ...], ...]  # per twin: covariates ordered most-similar first


def covariate_matrix(store: pd.DataFrame, unit_codes) -> pd.DataFrame:
    from equal_path.visibility import headline_rows

    columns = {}
    for covariate in COVARIATES:
        rows = headline_rows(store, covariate).set_index("county_id")
        columns[covariate] = [rows.value.get(code) for code in unit_codes]
    matrix = pd.DataFrame(columns, index=list(unit_codes))
    if matrix.isna().any().any():
        missing = matrix.columns[matrix.isna().any()].tolist()
        raise ValueError(f"covariates missing for some units: {missing}")
    return matrix


def prepare(matrix: pd.DataFrame) -> pd.DataFrame:
    """Covariates as used for distance (before z-scoring): log10 for skewed ones."""
    unexpected = set(matrix.columns) - set(COVARIATES)
    if unexpected:
        raise ValueError(f"only structural covariate columns are allowed (no outcomes): {sorted(unexpected)}")
    prepared = matrix.sort_index()[list(COVARIATES)].astype(float)
    for column in LOG_COVARIATES:
        if (prepared[column] <= 0).any():
            raise ValueError(f"{column} must be positive to be log-transformed")
        prepared[column] = np.log10(prepared[column])
    for column in LOG1P_COVARIATES:
        if (prepared[column] < 0).any():
            raise ValueError(f"{column} must be non-negative")
        prepared[column] = np.log10(1 + prepared[column])
    return prepared


def _standardise(matrix: pd.DataFrame) -> pd.DataFrame:
    ordered = prepare(matrix)
    std = ordered.std(ddof=0).replace(0, 1.0)
    return (ordered - ordered.mean()) / std


def distance_matrix(matrix: pd.DataFrame) -> pd.DataFrame:
    z = _standardise(matrix)
    diff = z.values[:, None, :] - z.values[None, :, :]
    return pd.DataFrame(np.sqrt((diff ** 2).sum(axis=2)), index=z.index, columns=z.index)


def _order_with_ties(pairs: list[tuple[float, str]]) -> list[tuple[float, str]]:
    """Sort by distance; any run of distances within TIE_TOLERANCE of its first member is ordered by code."""
    pairs = sorted(pairs)
    ordered, group = [], []
    for pair in pairs:
        if group and pair[0] - group[0][0] > TIE_TOLERANCE:
            ordered += sorted(group, key=lambda p: p[1])
            group = []
        group.append(pair)
    return ordered + sorted(group, key=lambda p: p[1])


def twin_sets(matrix: pd.DataFrame, k: int, no_good_percentile: float) -> dict[str, Twins]:
    z = _standardise(matrix)
    distances = distance_matrix(matrix)
    upper = distances.values[np.triu_indices(len(distances), k=1)]
    cutoff = float(np.percentile(upper, no_good_percentile)) if upper.size else 0.0
    result = {}
    for code in distances.index:
        others = _order_with_ties([(float(distances.loc[code, other]), other) for other in distances.index if other != code])
        nearest = others[:k]
        drivers = tuple(
            tuple(sorted(COVARIATES, key=lambda c: (abs(z.loc[code, c] - z.loc[twin, c]), c))) for _, twin in nearest
        )
        result[code] = Twins(code, tuple(t for _, t in nearest), tuple(d for d, _ in nearest),
                             bool(nearest) and nearest[0][0] <= cutoff, drivers)
    return result


def stability(matrix: pd.DataFrame, k: int, noise_fraction: float, draws: int, seed: int) -> dict[str, float]:
    """Mean Jaccard overlap per county between original and noise-perturbed twin sets."""
    base = {code: set(t.twins) for code, t in twin_sets(matrix, k, 100).items()}
    rng = np.random.default_rng(seed)
    totals = dict.fromkeys(base, 0.0)
    for _ in range(draws):
        factors = rng.uniform(1 - noise_fraction, 1 + noise_fraction, size=matrix.shape)
        noisy = twin_sets(matrix * factors, k, 100)
        for code, original in base.items():
            new = set(noisy[code].twins)
            totals[code] += len(original & new) / len(original | new)
    return {code: total / draws for code, total in totals.items()}


def better_twins(value: float, twins: tuple[str, ...], values: dict, direction: str) -> tuple[str, ...] | None:
    """Twins that perform better on this indicator, best first; empty = leader among peers;
    None = no twin has a value, so nothing can be said about rank among peers."""
    known = [(values[t], t) for t in twins if t in values and values[t] is not None and not np.isnan(values[t])]
    if not known:
        return None
    better = [(v, t) for v, t in known if (v > value if direction == "higher_better" else v < value)]
    better.sort(key=lambda vt: (-vt[0] if direction == "higher_better" else vt[0], vt[1]))
    return tuple(t for _, t in better)
