"""Data spine (F0): the long-format observations store, its validation, and reconciliation.

Section 7.2 columns, plus `geo_level` and `subgroup` in the unique key and a `locator`
saying where in the source each value was read. Shares are always on the 0-1 scale.
Cooperation-area, national, Åland and unknown-residence rows are kept apart from the 22
units and are never copied onto unit rows.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable, Literal, Mapping

import pandas as pd
from pydantic import BaseModel, ConfigDict, model_validator

OBS_COLUMNS: tuple[str, ...] = (
    "geo_level", "county_id", "indicator_id", "period", "subgroup",
    "value", "numerator", "denominator", "quality_flag", "source_id", "locator", "ci_low", "ci_high",
)
KEY: tuple[str, ...] = ("geo_level", "county_id", "indicator_id", "period", "subgroup")
NUMERIC = ("value", "numerator", "denominator", "ci_low", "ci_high")

AREA_CODES = frozenset({"YTA1", "YTA2", "YTA3", "YTA4", "YTA5"})
GEO_CODES: dict[str, frozenset[str] | None] = {
    "unit": None,  # the 22 unit codes, supplied by the caller
    "cooperation_area": AREA_CODES,
    "national": frozenset({"FI"}),
    "excluded_unit": frozenset({"91"}),  # Åland: reconciliation only
    "unknown_residence": frozenset({"UNK"}),  # reconciliation only
}
QUALITY_FLAGS = frozenset({
    "suppressed", "missing", "transcribed", "provider_based", "cooperation_area_level",
    "low_coverage", "provisional", "small_denominator", "derived",
})
SHARE_TOLERANCE = 0.001  # published shares are rounded to 0.1 %
RATIO_MAX = 1.5  # relative survival can exceed 1, but not by much
NON_NEGATIVE_UNITS = frozenset({"count", "persons", "eur", "km", "per_km2", "weeks"})
PERIOD = re.compile(r"^\d{4}(-\d{4}|-\d{2})?$")
SUBGROUP = re.compile(r"^(all|[a-z_]+:[a-z0-9_]+(\|[a-z_]+:[a-z0-9_]+)*)$")


def make_observations(rows: Iterable[Mapping]) -> pd.DataFrame:
    """Build a frame with exactly OBS_COLUMNS, numeric columns as float."""
    frame = pd.DataFrame(list(rows), columns=list(OBS_COLUMNS))
    for column in NUMERIC:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype(float)
    for column in ("quality_flag", "locator", "subgroup"):
        frame[column] = frame[column].fillna("").astype(str)
    return frame


def _flags(text: str) -> list[str]:
    return [flag for flag in (part.strip() for part in text.split(";")) if flag]


def _row_problems(row: pd.Series, catalog: Mapping, unit_codes: set[str], source_ids: set[str]) -> list[str]:
    where = f"{row.indicator_id}/{row.geo_level}:{row.county_id}/{row.period}/{row.subgroup}"
    problems = []
    if row.source_id not in source_ids:
        problems.append(f"{where}: unknown source_id {row.source_id!r}")
    if row.indicator_id not in catalog:
        problems.append(f"{where}: indicator not in catalog")
    allowed = GEO_CODES.get(row.geo_level, "invalid")
    if allowed == "invalid":
        problems.append(f"{where}: invalid geo_level {row.geo_level!r}")
    elif row.county_id not in (unit_codes if allowed is None else allowed):
        problems.append(f"{where}: {row.county_id!r} is not a valid unit code for {row.geo_level}")
    if not PERIOD.match(str(row.period)):
        problems.append(f"{where}: period {row.period!r} is not YYYY, YYYY-YYYY or YYYY-MM")
    if not SUBGROUP.match(str(row.subgroup)):
        problems.append(f"{where}: subgroup {row.subgroup!r} does not match 'all' or 'key:value|key:value'")
    if not str(row.locator).strip():
        problems.append(f"{where}: empty locator")
    listed = catalog.get(row.indicator_id, {}).get("source_ids")
    if listed and row.source_id not in listed:
        problems.append(f"{where}: {row.source_id} is not a listed source for this indicator")
    unknown_flags = set(_flags(row.quality_flag)) - QUALITY_FLAGS
    if unknown_flags:
        problems.append(f"{where}: unknown quality_flag {sorted(unknown_flags)}")
    if math.isnan(row.value) and not {"suppressed", "missing"} & set(_flags(row.quality_flag)):
        problems.append(f"{where}: missing value without a suppressed/missing flag")
    if not math.isnan(row.value) and {"suppressed", "missing"} & set(_flags(row.quality_flag)):
        problems.append(f"{where}: flagged suppressed/missing but carries a value")
    if any(math.isinf(x) for x in (row.value, row.numerator, row.denominator, row.ci_low, row.ci_high)):
        problems.append(f"{where}: values must be finite")
    unit = catalog.get(row.indicator_id, {}).get("unit")
    if unit == "ratio" and not math.isnan(row.value) and not 0 <= row.value <= RATIO_MAX:
        problems.append(f"{where}: ratio {row.value} outside 0-{RATIO_MAX} (missed /100?)")
    if unit in NON_NEGATIVE_UNITS and not math.isnan(row.value) and row.value < 0:
        problems.append(f"{where}: negative {unit} {row.value}")
    if math.isnan(row.numerator) != math.isnan(row.denominator) and unit == "share":
        problems.append(f"{where}: numerator and denominator must both be given (or neither)")
    if math.isnan(row.ci_low) != math.isnan(row.ci_high):
        problems.append(f"{where}: confidence interval needs both bounds")
    elif not math.isnan(row.ci_low) and not math.isnan(row.value) and not row.ci_low <= row.value <= row.ci_high:
        problems.append(f"{where}: value outside its confidence interval")
    is_share = catalog.get(row.indicator_id, {}).get("unit") == "share"
    if is_share and not math.isnan(row.value) and not 0 <= row.value <= 1:
        problems.append(f"{where}: share {row.value} outside 0-1")
    if not math.isnan(row.denominator) and row.denominator <= 0:
        problems.append(f"{where}: denominator must be > 0")
    if not math.isnan(row.numerator) and not math.isnan(row.denominator):
        if row.numerator > row.denominator:
            problems.append(f"{where}: numerator > denominator")
        elif is_share and row.denominator > 0 and not math.isnan(row.value):
            if abs(row.value - row.numerator / row.denominator) > SHARE_TOLERANCE:
                problems.append(f"{where}: value disagrees with numerator/denominator")
    return problems


def validate_observations(
    frame: pd.DataFrame, catalog: Mapping, unit_codes: Iterable[str], source_ids: Iterable[str]
) -> list[str]:
    """Every contract breach as a readable line; empty list means the store is valid."""
    if tuple(frame.columns) != OBS_COLUMNS:
        return [f"columns {list(frame.columns)} != {list(OBS_COLUMNS)}"]
    units, sources = set(unit_codes), set(source_ids)
    problems = [p for _, row in frame.iterrows() for p in _row_problems(row, catalog, units, sources)]
    duplicates = frame[frame.duplicated(list(KEY), keep=False)]
    if not duplicates.empty:
        keys = sorted({tuple(r) for r in duplicates[list(KEY)].itertuples(index=False)})
        problems.append(f"duplicate keys: {keys[:5]}")
    return problems


# ---------------------------------------------------------------- reconciliation


class ReconcileSpec(BaseModel):
    """How an anchor is recomputed from the store."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    indicator_id: str
    period: str
    method: Literal["sum", "weighted_share", "direct"]
    unit: Literal["count", "share"] = "count"
    subgroup: str = "all"
    expected_subgroups: tuple[str, ...] = ()
    geo_level: str = "national"   # 'direct' compares the row at this level and code
    county_id: str = "FI"

    @model_validator(mode="after")
    def _consistent(self) -> "ReconcileSpec":
        if self.subgroup == "*" and not self.expected_subgroups:
            raise ValueError("subgroup '*' needs expected_subgroups, so a missing programme cannot pass")
        if self.method == "sum" and self.unit == "share":
            raise ValueError("summing shares is meaningless; use weighted_share")
        return self


@dataclass(frozen=True)
class ReconcileResult:
    indicator_id: str
    period: str
    method: str
    published: float
    computed: float | None
    diff: float | None
    tolerance: str
    status: Literal["pass", "fail", "incomplete", "not_reconcilable", "no_data", "not_checked"]
    detail: str
    anchor_id: str = ""


RECONCILIATION_LEVELS = ("unit", "excluded_unit", "unknown_residence")


def _result(spec, published, computed, tolerance, status, detail) -> ReconcileResult:
    diff = None if computed is None else computed - published
    return ReconcileResult(spec.indicator_id, spec.period, spec.method, published, computed, diff, tolerance, status, detail)


def reconcile_one(
    frame: pd.DataFrame, spec: ReconcileSpec, published: float, counts_rel_tol: float, pct_abs_tol_pp: float
) -> ReconcileResult:
    """Recompute one published figure from the store. Never forces a pass."""
    rows = frame[(frame.indicator_id == spec.indicator_id) & (frame.period == spec.period)]
    if spec.subgroup != "*":  # "*" sums the listed subgroups (e.g. all screening programmes)
        rows = rows[rows.subgroup == spec.subgroup]
    is_share = spec.unit == "share" or spec.method == "weighted_share"
    tolerance = f"±{pct_abs_tol_pp} pp" if is_share else f"±{counts_rel_tol:.0%}"
    if rows.duplicated(list(KEY)).any():
        return _result(spec, published, None, tolerance, "incomplete", "duplicate rows for the same key")
    if spec.method == "direct":
        target = rows[(rows.geo_level == spec.geo_level) & (rows.county_id == spec.county_id) & rows.value.notna()]
        label = "national row" if spec.geo_level == "national" else f"{spec.geo_level} {spec.county_id} row"
        if target.empty:
            return _result(spec, published, None, tolerance, "no_data", f"no {label}")
        if len(target) != 1:
            return _result(spec, published, None, tolerance, "incomplete", f"{len(target)} rows for {label}, expected 1")
        computed, note = float(target.value.iloc[0]), label
    else:
        pool = rows[rows.geo_level.isin(RECONCILIATION_LEVELS)]
        if pool.empty:
            return _result(spec, published, None, tolerance, "no_data", "no unit rows")
        if spec.subgroup == "*":
            present, expected = set(pool.subgroup), set(spec.expected_subgroups)
            if present != expected:
                return _result(spec, published, None, tolerance, "incomplete",
                               f"missing subgroups {sorted(expected - present)}; unexpected {sorted(present - expected)}")
        if spec.method == "weighted_share" and (pool.numerator.isna().any() or pool.denominator.isna().any()):
            return _result(spec, published, None, tolerance, "not_reconcilable", "numerators/denominators not published")
        units = pool[pool.geo_level == "unit"]
        per_subgroup = units.groupby("subgroup").county_id.nunique()
        if per_subgroup.empty or (per_subgroup < 22).any() or units.value.isna().any():
            short = {k: int(v) for k, v in per_subgroup.items() if v < 22}
            return _result(spec, published, None, tolerance, "incomplete", f"units with values per subgroup below 22: {short}")
        if spec.method == "sum":
            computed = float(pool.value.sum())
        else:
            computed = float(pool.numerator.sum() / pool.denominator.sum())
        extra = sorted(set(pool.geo_level) - {"unit"})
        note = "22 units" + (" + " + ", ".join(extra) if extra else "")
        national = rows[(rows.geo_level == "national") & rows.value.notna()]
        if spec.method == "sum" and spec.subgroup != "*" and len(national) == 1:
            source_total = float(national.value.iloc[0])
            if abs(source_total - published) > 0.5:
                return _result(spec, published, computed, tolerance, "fail",
                               f"source national row {source_total:g} differs from the published figure")
            note += f"; source national {source_total:g}; residual {source_total - computed:g} (Åland + unknown residence)"
    if is_share:
        ok = abs(computed - published) * 100 <= pct_abs_tol_pp + 1e-12
    else:
        ok = abs(computed - published) <= counts_rel_tol * abs(published) + 1e-9
    return _result(spec, published, computed, tolerance, "pass" if ok else "fail", note)


# ---------------------------------------------------------------- parsing helpers

_MISSING_MARKERS = frozenset({"", "..", "...", "-", "–", "—", "x", "X", "n/a", "NA"})
_NUMBER = re.compile(r"^-?\d+(?:[.,]\d+)?$")


def parse_fi_number(text: str | float | int | None) -> float | None:
    """Parse Finnish-formatted numbers ('2 360', '67,8 %', '−1,5'); known missing markers -> None.

    Anything else ('<5', '12e3', 'nan', '1_000') raises, so a format change cannot slip through
    as a silently missing value.
    """
    if text is None:
        return None
    if isinstance(text, (int, float)):
        if isinstance(text, float) and not math.isfinite(text):
            raise ValueError(f"non-finite number {text!r}")
        return float(text)
    cleaned = str(text).strip()
    if cleaned in _MISSING_MARKERS:
        return None
    cleaned = re.sub(r"[\s\u00a0\u2009\u202f%]", "", cleaned).replace("\u2212", "-")
    if not cleaned.isascii() or not _NUMBER.match(cleaned):
        raise ValueError(f"unexpected number format {text!r}")
    return float(cleaned.replace(",", "."))
