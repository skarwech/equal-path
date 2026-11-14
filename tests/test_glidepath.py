"""F4 glidepath: Theil-Sen trend, bootstrap projection, states, robustness, calibration."""

import numpy as np
import pandas as pd
import pytest

from equal_path.glidepath import STATES, _bootstrap, glidepath, theil_sen

KW = dict(target=0.80, target_year=2035, draws=2000, interval=0.80, seed=20261114, min_points=4)
YEARS = [2020, 2021, 2022, 2023, 2024]


def test_perfectly_linear_series_recovers_its_slope_exactly():
    slope, intercept = theil_sen(YEARS, [0.70 + 0.012 * (y - 2020) for y in YEARS])
    assert slope == pytest.approx(0.012, abs=1e-12)
    assert intercept + slope * 2020 == pytest.approx(0.70, abs=1e-12)


def test_fewer_than_four_points_is_insufficient_data():
    result = glidepath([2022, 2023, 2024], [0.70, 0.71, 0.72], **KW)
    assert result.state == "insufficient data" and result.slope is None


def test_already_at_target_has_no_required_slope():
    result = glidepath(YEARS, [0.80, 0.81, 0.82, 0.82, 0.83], **KW)
    assert result.state == "target met" and result.required_slope is None


def test_required_slope_formula():
    result = glidepath(YEARS, [0.70, 0.70, 0.71, 0.71, 0.72], **KW)
    assert result.required_slope == pytest.approx((0.80 - 0.72) / (2035 - 2024))


@pytest.mark.parametrize(
    "values,expected",
    [
        ([0.700, 0.715, 0.730, 0.745, 0.760], "on track"),     # +1.5 pp/yr, steady: reaches 80 % well before 2035
        ([0.700, 0.698, 0.701, 0.699, 0.700], "off track"),    # flat at 70 %: upper interval stays below 80 %
        ([0.700, 0.720, 0.710, 0.730, 0.720], "uncertain"),    # slow noisy rise: interval straddles 80 %
    ],
)
def test_state_rules(values, expected):
    assert glidepath(YEARS, values, **KW).state == expected
    assert glidepath(YEARS, values, **KW).state in STATES


OPPOSITE = {"on track": "off track", "off track": "on track"}
# Flat-to-falling just below target, like the real unit 21 cervical series before its 2024 jump.
NEAR_TARGET_FALLING = [0.728, 0.733, 0.725, 0.719, 0.719]


@pytest.mark.parametrize("year_index", range(5))
@pytest.mark.parametrize("shift", [0.10, 0.079, 0.05, -0.05, -0.10])
def test_single_outlier_year_up_to_10pp_never_reverses_the_verdict(year_index, shift):
    """Spec F4 asks that one +/-10 pp outlier year never flips the class. With 5 annual points any
    80 % interval (bootstrap or Sen's analytic CI) widens past the target, so 'off track' can soften
    to 'uncertain' (disclosed limitation). What must hold: the verdict never reverses (on track <->
    off track), and the trend keeps Theil-Sen's bounded influence: one bad year changes 4 of the 10
    pairwise slopes, so the fitted slope stays inside the range of the 6 slopes between clean years.
    (The 2035 point projection itself can still move ~6 pp: an 11-year extrapolation amplifies it.)"""
    for values in ([0.700, 0.715, 0.730, 0.745, 0.760], [0.700, 0.698, 0.701, 0.699, 0.700], NEAR_TARGET_FALLING):
        base = glidepath(YEARS, values, **KW)
        shocked = list(values)
        shocked[year_index] += shift
        result = glidepath(YEARS, shocked, **KW)
        if shocked[-1] >= KW["target"] > values[-1]:
            assert result.state == "target met"  # the observed latest value really is above target
            continue
        assert result.state != OPPOSITE.get(base.state), (values, year_index, shift)
        clean = [(values[j] - values[i]) / (YEARS[j] - YEARS[i])
                 for i in range(5) for j in range(i + 1, 5) if year_index not in (i, j)]
        assert min(clean) - 1e-12 <= result.slope <= max(clean) + 1e-12, (values, year_index, shift)


def test_point_projection_is_the_theil_sen_line():
    values = [0.70, 0.71, 0.73, 0.72, 0.74]
    slope, intercept = theil_sen(YEARS, values)
    assert glidepath(YEARS, values, **KW).point_projection == pytest.approx(intercept + slope * 2035)


def test_bootstrap_survives_degenerate_resamples_and_is_reproducible():
    a = glidepath(YEARS[:4], [0.70, 0.71, 0.70, 0.72], **KW)
    b = glidepath(YEARS[:4], [0.70, 0.71, 0.70, 0.72], **KW)
    assert a == b and a.low <= a.projection <= a.high


def test_uncertain_means_the_interval_straddles_the_target():
    result = glidepath(YEARS, [0.700, 0.720, 0.710, 0.730, 0.720], **KW)
    assert result.low < KW["target"] <= result.high and result.projection < KW["target"]


def test_a_final_year_jump_alone_cannot_make_a_falling_series_on_track():
    """Review GP-1: the real unit 21 cervical series (off track to 2023, then +7.9 pp in 2024) was
    called 'on track' because the bootstrap median jumped while the robust Theil-Sen line did not."""
    base = glidepath(YEARS, NEAR_TARGET_FALLING, **KW)
    jumped = glidepath(YEARS, [*NEAR_TARGET_FALLING[:-1], 0.798], **KW)
    assert base.state == "off track"
    assert jumped.point_projection < KW["target"]
    assert jumped.state == "uncertain"


def test_on_track_needs_the_theil_sen_line_and_the_bootstrap_median_to_reach_target():
    result = glidepath(YEARS, [0.700, 0.715, 0.730, 0.745, 0.760], **KW)
    assert result.state == "on track"
    assert result.point_projection >= KW["target"] and result.projection >= KW["target"]


def test_interval_is_the_central_80_percent_of_the_seeded_bootstrap():
    values = [0.70, 0.71, 0.73, 0.72, 0.74]
    result = glidepath(YEARS, values, **KW)
    draws = _bootstrap(np.array(YEARS, dtype=float), np.array(values), 2035, KW["draws"], KW["seed"])
    assert len(draws) == KW["draws"]
    assert (result.low, result.high) == tuple(float(q) for q in np.quantile(draws, [0.10, 0.90]))
    assert result.projection == float(np.median(draws))


def _screening_store(final_values: list[float]) -> pd.DataFrame:
    """Flat 70 % series for 2020-2023, then a chosen 2024 value per unit, plus one unit too short to use."""
    rows = []
    for unit, final in enumerate(final_values, start=1):
        for year, value in zip(YEARS, [0.70, 0.70, 0.70, 0.70, final]):
            rows.append((f"{unit:02d}", str(year), value))
    rows += [("99", str(year), 0.70) for year in YEARS[1:]]  # 4 points: 3 after holding one out
    return pd.DataFrame(
        [{"geo_level": "unit", "county_id": c, "indicator_id": "screening_participation_breast",
          "period": p, "subgroup": "all", "value": v} for c, p, v in rows]
    )


@pytest.mark.parametrize(
    "finals,covered,label",
    [([0.70, 0.70, 0.70, 0.90], 3, "validated"),     # 3 / 4 = 75 %: inside 65-95 %
     ([0.70, 0.90], 1, "indicative")],                # 1 / 2 = 50 %
)
def test_calibration_holds_out_the_last_year(monkeypatch, finals, covered, label):
    """Non-circular check (review T-2): the fit never sees the held-out year, the interval is
    evaluated at that year, and coverage counts only the held-out values it contains. A flat
    series has a zero-width interval at exactly 70 %, so a 90 % final year cannot be covered."""
    import equal_path.glidepath as gp

    seen = []
    real = gp._bootstrap

    def spy(years, values, at_year, draws, seed):
        seen.append((tuple(years), at_year))
        return real(years, values, at_year, draws, seed)

    monkeypatch.setattr(gp, "_bootstrap", spy)
    result = gp.calibration(_screening_store(finals))
    assert (result.series, result.covered, result.label) == (len(finals), covered, label)
    assert seen and all(years == (2020.0, 2021.0, 2022.0, 2023.0) and at == 2024 for years, at in seen)
