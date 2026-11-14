"""Shared helpers for loaders."""

from __future__ import annotations

import io

import pandas as pd

from equal_path.paths import DATA_DIR


def raw(family: str, file: str):
    return DATA_DIR / "raw" / family / file


def html_table(table_html: str) -> pd.DataFrame:
    """Read one <table>; flatten two-row headers to 'Group | N'. Cells stay as text."""
    frame = pd.read_html(io.StringIO(table_html), thousands=None, decimal=".", converters=None)[0]
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [" | ".join(dict.fromkeys(str(part) for part in col if not str(part).startswith("Unnamed"))) for col in frame.columns]
    return frame.astype(str)


def obs(geo_level, county_id, indicator_id, period, value, source_id, locator, subgroup="all",
        numerator=None, denominator=None, quality_flag="", ci_low=None, ci_high=None) -> dict:
    return {
        "geo_level": geo_level, "county_id": county_id, "indicator_id": indicator_id, "period": str(period),
        "subgroup": subgroup, "value": value, "numerator": numerator, "denominator": denominator,
        "quality_flag": quality_flag if value is not None else (quality_flag or "missing"),
        "source_id": source_id, "locator": locator, "ci_low": ci_low, "ci_high": ci_high,
    }
