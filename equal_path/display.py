"""Display formatting shared by the county page and the sources drawer, so both print identical strings."""

from __future__ import annotations

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
    return sorted(t.distances[0] for t in twins.values())[len(twins) // 2]


def national_value(store: pd.DataFrame, indicator_id: str) -> float | None:
    rows = store[(store.indicator_id == indicator_id) & (store.geo_level == "national") & store.value.notna()]
    return float(rows.sort_values("period").value.iloc[-1]) if len(rows) else None
