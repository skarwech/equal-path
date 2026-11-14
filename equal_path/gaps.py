"""F2 gap locator: per county, per indicator series, compare with the national value and the
twin median; a Leak must be significant, practically meaningful, adequately observed and hold
under both references (national only when the county has no good twin).

Significance: Wilson interval from numerator/denominator (shares only), else the published CI
(widened proportionally on each side to the stage's z); with neither (e.g. HPV coverage,
primary-care waits) a gap can only reach Watch. Within a stage the per-series level is
Bonferroni-adjusted (`bonferroni_z`) so the stage-level false-Leak rate stays within the spec.
The twin median needs at least two usable twin values; otherwise the twin reference is
unavailable and the state is capped at Watch (national-only judgement is reserved for counties
with no good twin).
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from scipy.stats import norm

PUBLISHED_CI_Z = 1.96   # published CIs are 95 %
MIN_TWIN_VALUES = 2

STATES = ("leak", "watch", "ok", "unknown")


def wilson_interval(p: float, n: float, z: float) -> tuple[float, float]:
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def bonferroni_z(z: float, tests: int) -> float:
    """z for one-sided level (1 - Phi(z)) / tests: e.g. 1.96 with 5 tests -> 2.576."""
    if tests <= 1:
        return z
    return float(norm.ppf(1 - (1 - norm.cdf(z)) / tests))


def signed_gap(value: float, reference: float, direction: str) -> float:
    """Positive = worse than the reference, whatever the indicator's direction."""
    if direction == "higher_better":
        return reference - value
    if direction == "lower_better":
        return value - reference
    raise ValueError(f"no gap for direction {direction!r}")


@dataclass(frozen=True)
class SeriesInput:
    indicator_id: str
    subgroup: str
    stage: str
    direction: str
    values: Mapping[str, float]                      # unit code -> value (share or ratio)
    denominators: Mapping[str, float]                # unit code -> n (may be empty)
    ci: Mapping[str, tuple[float, float]]            # unit code -> published CI (may be empty)
    national: float | None                           # published national value, if any
    period: str = ""
    unit: str = "share"                              # 'share' (Wilson allowed) or 'ratio' (published CI only)
    excluded: Mapping[str, str] = field(default_factory=dict)  # unit code -> why F1 does not count it


@dataclass(frozen=True)
class Assessment:
    code: str
    indicator_id: str
    subgroup: str
    stage: str
    value: float | None
    interval: tuple[float, float] | None
    national: float | None
    twin_median: float | None
    gap_national: float | None
    gap_twin: float | None
    state: str
    reason: str
    references: tuple[str, ...] = field(default_factory=tuple)


def _national(series: SeriesInput) -> float | None:
    if series.national is not None:
        return series.national
    codes = sorted(c for c in series.values if c in series.denominators and not math.isnan(series.values[c]))
    if codes and len(codes) == len(series.values):  # order-independent: sorted codes, exact float sums
        num = math.fsum(series.values[c] * series.denominators[c] for c in codes)
        return num / math.fsum(series.denominators[c] for c in codes)
    return None


def _judge(gap: float, interval, reference: float, direction: str, min_gap_pp: float) -> tuple[bool, bool]:
    practical = gap * 100 >= min_gap_pp - 1e-9
    if interval is None:
        return practical, False
    low, high = interval
    significant = high < reference if direction == "higher_better" else low > reference
    return practical, significant


def _usable(value, n, min_den) -> bool:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return False
    return n is None or (isinstance(n, float) and math.isnan(n)) or n >= min_den


def _interval(series: SeriesInput, code: str, value: float, n, z: float):
    if code in series.ci:
        low, high = series.ci[code]
        if not low <= value <= high:
            return None  # inconsistent source row: no significance claim
        scale = z / PUBLISHED_CI_Z
        half = (high - low) / 2
        below = (value - low) or half   # a value on a bound still widens that side
        above = (high - value) or half
        return value - below * scale, value + above * scale
    if series.unit == "share" and n is not None and not math.isnan(n) and 0.0 <= value <= 1.0:
        return wilson_interval(value, n, z)
    return None


def assess_series(series: SeriesInput, twins: Mapping[str, Iterable[str]], good_twin: Mapping[str, bool],
                  z: float, min_gap_pp: float, min_den: float) -> dict[str, Assessment]:
    national = _national(series)
    out = {}
    for code, why in series.excluded.items():
        out[code] = Assessment(code=code, indicator_id=series.indicator_id, subgroup=series.subgroup, stage=series.stage,
                               value=None, interval=None, national=national, twin_median=None, gap_national=None,
                               gap_twin=None, state="unknown", reason=why)
    for code in sorted(series.values):
        value = series.values[code]
        n = series.denominators.get(code)
        base = dict(code=code, indicator_id=series.indicator_id, subgroup=series.subgroup, stage=series.stage,
                    national=national)
        if value is None or (isinstance(value, float) and math.isnan(value)):
            out[code] = Assessment(value=None, interval=None, twin_median=None, gap_national=None, gap_twin=None,
                                   state="unknown", reason="no value", **base)
            continue
        if n is not None and not math.isnan(n) and n < min_den:
            out[code] = Assessment(value=value, interval=None, twin_median=None, gap_national=None, gap_twin=None,
                                   state="unknown", reason=f"denominator {n:.0f} < {min_den:.0f}", **base)
            continue
        interval = _interval(series, code, value, n, z)
        twin_values = [series.values[t] for t in twins.get(code, ())
                       if t in series.values and _usable(series.values[t], series.denominators.get(t), min_den)]
        has_good_twin = bool(good_twin.get(code))
        twin_median = statistics.median(twin_values) if has_good_twin and len(twin_values) >= MIN_TWIN_VALUES else None
        twin_missing = has_good_twin and twin_median is None
        national_missing = national is None
        used = {name: ref for name, ref in (("national", national), ("twin median", twin_median)) if ref is not None}
        gaps = {name: signed_gap(value, ref, series.direction) for name, ref in used.items()}
        verdicts = {name: _judge(gaps[name], interval, used[name], series.direction, min_gap_pp) for name in used}
        if not used:
            state, reason = "unknown", "no reference"
        elif all(p and s for p, s in verdicts.values()) and not twin_missing and not national_missing:
            state, reason = "leak", "significant and >= practical gap vs " + " and ".join(used)
        elif any(p or s for p, s in verdicts.values()):
            state = "watch"
            if national_missing:
                reason = "national reference unavailable"
            elif twin_missing:
                reason = "twin reference unavailable (fewer than 2 twins with usable values)"
            elif interval is None:
                reason = "no uncertainty published"
            else:
                reason = "only some leak conditions hold"
        else:
            state, reason = "ok", "within practical gap or not significant"
        out[code] = Assessment(value=value, interval=interval, twin_median=twin_median,
                               gap_national=gaps.get("national"), gap_twin=gaps.get("twin median"),
                               state=state, reason=reason, references=tuple(used), **base)
    return out


def low_visibility(visibility: float, min_stage_visibility: float) -> bool:
    """The one 'too little observable' test: F2's Leak gate, map hatching and the confidence badge all use it."""
    return visibility < min_stage_visibility


def stage_state(visibility: float, indicator_states: Iterable[str], min_stage_visibility: float) -> str:
    states = set(indicator_states)
    if low_visibility(visibility, min_stage_visibility):
        return "watch" if states & {"leak", "watch"} else "unknown"
    for state in ("leak", "watch", "ok"):
        if state in states:
            return state
    return "unknown"
