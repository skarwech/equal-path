"""Typed, immutable loaders for everything in config/.

All models are frozen and reject unknown keys, so a typo or a silently added
knob fails loudly instead of changing behaviour.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from equal_path.paths import (
    ANCHORS_FILE,
    INDICATORS_FILE,
    REFERENCE_TIMES_FILE,
    RULES_FILE,
    SCOPE_FILE,
    THRESHOLDS_FILE,
    THRESHOLDS_LOCK,
)


class _Frozen(BaseModel):
    """Immutable, no unknown keys, no lax coercion (true -> 1, "30" -> 30, .inf)."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)


class StageWeights(_Frozen):
    """F1: fixed weights combining the four pathway stages into one 0-100 visibility score."""

    detection: float = Field(ge=0, le=1)
    referral: float = Field(ge=0, le=1)
    diagnosis: float = Field(ge=0, le=1)
    treatment: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _sum_to_one(self) -> "StageWeights":
        total = self.detection + self.referral + self.diagnosis + self.treatment
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"visibility stage weights must sum to 1, got {total}")
        return self


class Thresholds(_Frozen):
    status: Literal["frozen", "draft"]
    frozen_at: str = Field(min_length=1)
    stage_coverage_target: float = Field(gt=0, le=1)
    stage_coverage_partial_min: float = Field(gt=0, le=1)
    min_denominator: int = Field(gt=0)
    min_practical_gap_pp: float = Field(gt=0)
    min_stage_visibility: float = Field(ge=0, le=1)
    subgroup_gap_trigger_pp: float = Field(gt=0)
    twin_stability_jaccard: float = Field(ge=0, le=1)
    min_annual_points_glidepath: int = Field(ge=2)
    min_monthly_points_early_warning: int = Field(ge=2)
    early_warning_detection_months_at_1sd: int = Field(gt=0)
    early_warning_detection_rate_min: float = Field(gt=0, le=1)
    early_warning_false_alarm_rate_max_per_year: float = Field(gt=0, le=1)
    false_leak_rate_max: float = Field(gt=0, le=1)
    reconciliation_counts_rel_tol: float = Field(gt=0)
    reconciliation_pct_abs_tol_pp: float = Field(gt=0)
    simulator_backcast_tol: float = Field(gt=0)
    analyst_brief_max_words: int = Field(gt=0)
    validator_regeneration_attempts: int = Field(ge=0)
    wilson_z: float = Field(gt=0)
    twin_k: int = Field(gt=0)
    no_good_twin_percentile: float = Field(gt=0, le=100)
    twin_noise_fraction: float = Field(gt=0)
    monte_carlo_draws: int = Field(gt=0)
    simulator_interval: float = Field(gt=0, lt=1)
    glidepath_target_year: int = Field(ge=2026)
    early_warning_baseline_months: int = Field(gt=0)
    visibility_stage_weights: StageWeights


class Goal3Indicator(_Frozen):
    id: str
    label: str
    target: str
    source_id: str
    locator: str


class Scope(_Frozen):
    anchor_cancer: str
    secondary_cancer: str | None
    secondary_cancer_candidates: tuple[str, ...]
    unit_count: int
    excluded_units: tuple[str, ...]
    pathway_stages: tuple[str, ...]
    cross_stage: str
    data_rule: str
    goal3_indicators: tuple[Goal3Indicator, ...]
    related_targets: tuple[Goal3Indicator, ...] = ()


class Citation(_Frozen):
    id: str
    locator: str


class Rule(_Frozen):
    id: str = Field(pattern=r"^R-[A-Z]{3}-\d{2}$")
    stage: Literal["detection", "referral", "diagnosis", "treatment", "timing"]
    trigger: str
    action: str
    owner: str
    owner_level: Literal["county", "joint", "national"]
    kpi: str
    cost_ref: str
    evidence_grade: Literal["strategy-endorsed", "study-supported", "hypothesis"]
    mode: Literal["implement", "test"]
    data_capture: bool
    sources: tuple[Citation, ...]
    do_not_fire_if: tuple[str, ...] = ()
    note: str = ""


class ReconcileRule(_Frozen):
    """How Step 2 recomputes this anchor from the observations store."""

    indicator_id: str  # for method "min", an fnmatch pattern such as screening_participation_*
    period: str
    method: Literal["sum", "weighted_share", "direct", "min"]
    unit: Literal["count", "share"] = "count"
    subgroup: str = "all"
    expected_subgroups: tuple[str, ...] = ()
    geo_level: str = "national"
    county_id: str = "FI"


class Indicator(_Frozen):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    stage: Literal["detection", "referral", "diagnosis", "treatment", "timing", "covariate", "context"]
    label: str
    definition: str
    direction: Literal["higher_better", "lower_better", "context"]
    unit: Literal["share", "ratio", "count", "weeks", "per_km2", "eur", "km", "persons"]
    period_type: Literal["year", "month", "pooled", "snapshot"]
    cancer: str
    goal3_link: str | None
    status: Literal["available", "partial", "not_public", "to_verify"]
    source_ids: tuple[str, ...]
    limitation: str = ""


class Anchor(_Frozen):
    """A published figure to reconcile against: a point value, or a range/bound."""

    id: str
    label: str
    value: float | None = None
    low: float | None = None
    high: float | None = None
    unit: Literal["count", "share"]
    period: str
    level: Literal["national", "cooperation_area", "unit"]
    source_id: str
    note: str = ""
    reconcile: ReconcileRule | None = None

    @model_validator(mode="after")
    def _value_or_bound(self) -> "Anchor":
        if self.value is None and self.low is None and self.high is None:
            raise ValueError(f"anchor {self.id!r} needs a value or a bound (low/high)")
        if self.low is not None and self.high is not None and self.low > self.high:
            raise ValueError(f"anchor {self.id!r}: low > high")
        return self


class ReferenceInterval(_Frozen):
    id: str
    label: str
    limit_weeks: float = Field(gt=0)
    limit_text: str


class ReferenceTimes(_Frozen):
    binding: bool
    source_id: str
    locator: str
    note: str
    intervals: tuple[ReferenceInterval, ...]


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate mapping keys instead of keeping the last one."""


def _construct_unique_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    seen: set[Any] = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping", node.start_mark, f"found duplicate key {key!r}", key_node.start_mark
            )
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)


def _as_tuples(node: Any) -> Any:
    """Lists become tuples (immutable, and what strict tuple fields require)."""
    if isinstance(node, list):
        return tuple(_as_tuples(item) for item in node)
    if isinstance(node, dict):
        return {key: _as_tuples(value) for key, value in node.items()}
    return node


def _read_yaml(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return _as_tuples(yaml.load(handle, Loader=_UniqueKeyLoader))  # noqa: S506 (SafeLoader subclass)
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot read {path.name}: {exc}") from exc


def _read_list(path: Path) -> tuple:
    data = _read_yaml(path)
    if not isinstance(data, tuple):
        raise ValueError(f"{path.name} must hold a list of entries, got {type(data).__name__}")
    return data


def _validate(model: type[BaseModel], data: Any, path: Path) -> Any:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"{path.name} is invalid:\n{exc}") from exc


def load_thresholds(path: Path = THRESHOLDS_FILE) -> Thresholds:
    return _validate(Thresholds, _read_yaml(path), path)


def load_scope(path: Path = SCOPE_FILE) -> Scope:
    return _validate(Scope, _read_yaml(path), path)


def load_rules(path: Path = RULES_FILE) -> tuple[Rule, ...]:
    return tuple(_validate(Rule, item, path) for item in _read_list(path))


def load_anchors(path: Path = ANCHORS_FILE) -> tuple[Anchor, ...]:
    return tuple(_validate(Anchor, item, path) for item in _read_list(path))


def load_indicator_catalog(path: Path = INDICATORS_FILE) -> tuple[Indicator, ...]:
    return tuple(_validate(Indicator, item, path) for item in _read_list(path))


def load_reference_times(path: Path = REFERENCE_TIMES_FILE) -> ReferenceTimes:
    return _validate(ReferenceTimes, _read_yaml(path), path)


def thresholds_digest(path: Path = THRESHOLDS_FILE) -> str:
    """SHA-256 of the file with line endings normalised (CRLF checkouts keep the lock)."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def read_lock_digest(path: Path = THRESHOLDS_LOCK) -> str:
    return path.read_text(encoding="utf-8").strip()


def thresholds_are_frozen(source: Path = THRESHOLDS_FILE, lock: Path = THRESHOLDS_LOCK) -> bool:
    """True only if the file is valid, declares status 'frozen' and matches its lock."""
    try:
        return load_thresholds(source).status == "frozen" and thresholds_digest(source) == read_lock_digest(lock)
    except (OSError, ValueError):
        return False


def write_lock(path: Path = THRESHOLDS_LOCK, source: Path = THRESHOLDS_FILE) -> str:
    """Record the frozen digest. Refuses invalid files and files not marked 'frozen'."""
    status = load_thresholds(source).status
    if status != "frozen":
        raise ValueError(f"{source.name} has status '{status}'; only status 'frozen' can be locked (draft is never locked)")
    digest = thresholds_digest(source)
    path.write_text(digest + "\n", encoding="utf-8")
    return digest


_FROZEN_AT_LINE = re.compile(r'^frozen_at: .*$', re.MULTILINE)


def freeze(source: Path = THRESHOLDS_FILE, lock: Path = THRESHOLDS_LOCK, when: str | None = None) -> str:
    """Stamp `frozen_at` with the actual time, then lock. Used by scripts/freeze_thresholds.py."""
    stamp = when or datetime.now(timezone.utc).isoformat(timespec="seconds")
    text = source.read_text(encoding="utf-8")
    if not _FROZEN_AT_LINE.search(text):
        raise ValueError(f"{source.name} has no frozen_at line to stamp")
    source.write_text(_FROZEN_AT_LINE.sub(f'frozen_at: "{stamp}"', text, count=1), encoding="utf-8")
    return write_lock(lock, source)


APPENDIX_B_FIELDS = frozenset({
    "stage_coverage_target", "stage_coverage_partial_min", "min_denominator", "min_practical_gap_pp",
    "min_stage_visibility", "subgroup_gap_trigger_pp", "twin_stability_jaccard", "min_annual_points_glidepath",
    "min_monthly_points_early_warning", "early_warning_detection_months_at_1sd", "early_warning_detection_rate_min",
    "early_warning_false_alarm_rate_max_per_year", "false_leak_rate_max", "reconciliation_counts_rel_tol",
    "reconciliation_pct_abs_tol_pp", "simulator_backcast_tol", "analyst_brief_max_words",
    "validator_regeneration_attempts",
})
SECTION_8_FIELDS = frozenset({
    "wilson_z", "twin_k", "no_good_twin_percentile", "twin_noise_fraction", "monte_carlo_draws",
    "simulator_interval", "glidepath_target_year",
})
METADATA_FIELDS = frozenset({"status", "frozen_at"})


def threshold_provenance() -> dict[str, str]:
    """Where each threshold comes from, for the register's Provenance column."""
    def label(name: str) -> str:
        if name in APPENDIX_B_FIELDS:
            return "Appendix B"
        if name in SECTION_8_FIELDS:
            return "Section 8 method constant"
        if name in METADATA_FIELDS:
            return "Register metadata"
        return "Team-set (not in spec)"

    return {name: label(name) for name in Thresholds.model_fields}
