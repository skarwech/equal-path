"""Display helpers of the county pathway page (no Streamlit session needed)."""

import pytest

from app.pathway_view import _better_label, _share_interval, _share_pct


@pytest.mark.parametrize("better,state,expected", [
    (("02", "03"), "leak", "Uusimaa, 03"),
    ((), "ok", "leader among peers"),
    (None, "ok", "no twin data"),        # review TW-1: no twin value is not leadership
    (None, "watch", "no twin data"),
    ((), "unknown", ""),
    (None, "unknown", ""),
])
def test_better_twin_label(better, state, expected):
    assert _better_label(better, state, {"02": "Uusimaa"}) == expected


@pytest.mark.parametrize("value,expected", [(1.097, 100.0), (0.8234, 82.3), (-0.04, 0.0), (None, None), (float("nan"), None)])
def test_projected_shares_are_shown_within_0_to_100(value, expected):
    """Review GP-2: a linear trend can extrapolate past 100 % participation; the display caps it."""
    assert _share_pct(value) == expected


def test_projected_interval_is_capped_and_blank_without_bounds():
    assert _share_interval(0.647, 1.396) == "64.7–100.0"
    assert _share_interval(float("nan"), float("nan")) == ""
