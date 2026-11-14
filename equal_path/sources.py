"""Source registry: every number shown anywhere must resolve to a row here."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from equal_path.paths import SOURCES_FILE

REQUIRED_COLUMNS: tuple[str, ...] = (
    "source_id",
    "title",
    "publisher",
    "url",
    "retrieved_on",
    "period_covered",
    "limitation",
    "status",
    "verification_note",
)


def load_sources(path: Path = SOURCES_FILE) -> pd.DataFrame:
    """Load the registry as strings; fail fast if columns drift from the contract."""
    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read {path.name}: {exc}") from exc
    if tuple(frame.columns) != REQUIRED_COLUMNS:
        raise ValueError(f"{path.name}: columns {list(frame.columns)} != {list(REQUIRED_COLUMNS)}")
    return frame


def source_ids(path: Path = SOURCES_FILE) -> frozenset[str]:
    return frozenset(load_sources(path)["source_id"])
