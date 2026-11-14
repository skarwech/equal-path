"""Display formatting shared by the county page and the sources drawer, so both print identical strings."""

from __future__ import annotations

import statistics

import pandas as pd

BADGE = {  # status colours always paired with a symbol and a word (never colour alone)
    "leak": ":red[▲ Leak]",
    "watch": ":orange[◆ Watch]",
    "ok": ":green[✓ OK]",
    "unknown": ":gray[○ Unknown]",
}
STATE_WORD = {"leak": "▲ Leak", "watch": "◆ Watch", "ok": "✓ OK", "unknown": "○ Unknown"}


def pct(value) -> float | None:
    return None if value is None or pd.isna(value) else round(float(value) * 100, 1)


def share_pct(value) -> float | None:
    """A projected share for display: capped to 0-100 % (a linear trend can extrapolate past 100 %)."""
    return None if value is None or pd.isna(value) else pct(min(max(float(value), 0.0), 1.0))


def share_interval(low, high) -> str:
    return "" if pd.isna(low) or pd.isna(high) else f"{share_pct(low):.1f}–{share_pct(high):.1f}"


def interval_text(interval) -> str:
    if interval is None or (isinstance(interval, float) and pd.isna(interval)):
        return "not published"
    low, high = interval
    return f"{low * 100:.1f}–{high * 100:.1f}"


def typical_twin_distance(twins: dict) -> float:
    """Median over all units of each unit's nearest-twin distance."""
    return statistics.median(t.distances[0] for t in twins.values())


def national_row(store: pd.DataFrame, indicator_id: str, subgroup: str = "all"):
    """The published national row for the latest period of one series; None if there is none.
    More than one candidate row is an error, never resolved by row order (review P-1)."""
    rows = store[(store.indicator_id == indicator_id) & (store.geo_level == "national") & (store.subgroup == subgroup)
                 & store.value.notna()]
    if rows.empty:
        return None
    latest = rows[rows.period == max(rows.period)]
    if len(latest) != 1:
        raise ValueError(f"{len(latest)} national rows for {indicator_id} ({subgroup}), period {latest.period.iloc[0]}")
    return latest.iloc[0]


def national_value(store: pd.DataFrame, indicator_id: str, subgroup: str = "all") -> float | None:
    row = national_row(store, indicator_id, subgroup)
    return None if row is None else float(row.value)
