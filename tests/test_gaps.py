"""F2 gap locator on synthetic fixtures: planted gaps, noise, invariance, sign, visibility gate."""

import math

import numpy as np
import pytest

from equal_path.gaps import SeriesInput, assess_series, bonferroni_z, signed_gap, stage_state, wilson_interval

CODES = [f"{i:02d}" for i in range(1, 22)] + ["90"]
TWINS = {code: tuple(c for c in CODES if c != code)[:3] for code in CODES}  # fixed synthetic twins
GOOD = {code: True for code in CODES}
T = dict(z=1.96, min_gap_pp=3.0, min_den=30)


def _series(values, dens, direction="higher_better", ci=None, national=None):
    return SeriesInput(indicator_id="x", subgroup="all", stage="detection", direction=direction,
                       values=dict(zip(CODES, values)), denominators=dict(zip(CODES, dens)) if dens else {},
                       ci=ci or {}, national=national)


def test_wilson_matches_formula():
    lo, hi = wilson_interval(0.8, 100, 1.96)
    z, p, n = 1.96, 0.8, 100
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    assert (lo, hi) == (pytest.approx(centre - half), pytest.approx(centre + half))


def test_self_reference_gap_is_exactly_zero():
    assert signed_gap(0.73, 0.73, "higher_better") == 0.0 and signed_gap(0.4, 0.4, "lower_better") == 0.0


def test_sign_positive_means_worse():
    assert signed_gap(0.70, 0.80, "higher_better") == pytest.approx(0.10)  # lower participation = worse
    assert signed_gap(0.50, 0.40, "lower_better") == pytest.approx(0.10)   # longer waits = worse


def test_planted_gaps_8pp_leaks_1_5pp_does_not():
    values = [0.75] * 22
    values[0] = 0.67   # 8 pp below
    values[1] = 0.735  # 1.5 pp below
    result = assess_series(_series(values, [2000] * 22), TWINS, GOOD, **T)
    assert result["01"].state == "leak"
    assert result["02"].state in ("ok", "watch") and result["02"].state != "leak"


def test_noise_false_leak_rate_at_most_5_percent_in_every_cell():
    """Per county, not pooled: small-n cells are where a missing significance test would show."""
    rng = np.random.default_rng(20261114)
    dens = [int(n) for n in np.geomspace(100, 40000, 22)]
    leaks = dict.fromkeys(CODES, 0)
    for _ in range(1000):
        values = [rng.binomial(n, 0.75) / n for n in dens]
        for code, result in assess_series(_series(values, dens), TWINS, GOOD, **T).items():
            leaks[code] += result.state == "leak"
    assert max(leaks.values()) / 1000 <= 0.05


def test_bonferroni_z_for_stage_multiplicity():
    assert bonferroni_z(1.96, 1) == pytest.approx(1.96, abs=1e-3)
    assert bonferroni_z(1.96, 5) == pytest.approx(2.576, abs=1e-3)  # one-sided 0.025 / 5
    assert bonferroni_z(1.96, 3) > bonferroni_z(1.96, 2) > 1.96


def test_order_invariance():
    rng = np.random.default_rng(1)
    values = list(rng.uniform(0.6, 0.85, 22))
    a = assess_series(_series(values, [3000] * 22), TWINS, GOOD, **T)
    order = list(reversed(range(22)))
    shuffled = SeriesInput("x", "all", "detection", "higher_better",
                           {CODES[i]: values[i] for i in order}, {CODES[i]: 3000 for i in order}, {}, None)
    b = assess_series(shuffled, TWINS, GOOD, **T)
    assert {k: (v.state, v.gap_national) for k, v in a.items()} == {k: (v.state, v.gap_national) for k, v in b.items()}


def test_leak_must_hold_under_both_references():
    values = [0.75] * 22
    values[0] = 0.67
    twins = dict(TWINS, **{"01": ("02", "03", "04")})
    # twins of 01 are equally low -> no gap vs twin median -> watch, not leak
    for code in ("02", "03", "04"):
        values[CODES.index(code)] = 0.67
    result = assess_series(_series(values, [2000] * 22), twins, GOOD, **T)
    assert result["01"].state == "watch"


def test_no_good_twin_falls_back_to_national_only():
    values = [0.75] * 22
    values[0] = 0.67
    for code in ("02", "03", "04"):
        values[CODES.index(code)] = 0.67
    result = assess_series(_series(values, [2000] * 22), TWINS, dict(GOOD, **{"01": False}), **T)
    assert result["01"].state == "leak" and result["01"].twin_median is None


def test_small_denominator_is_greyed_not_assessed():
    values = [0.75] * 22
    values[0] = 0.40
    dens = [2000] * 22
    dens[0] = 20
    assert assess_series(_series(values, dens), TWINS, GOOD, **T)["01"].state == "unknown"


def test_no_uncertainty_information_means_watch_at_most():
    values = [0.75] * 22
    values[0] = 0.60  # big gap but no n and no CI published
    assert assess_series(_series(values, None), TWINS, GOOD, **T)["01"].state == "watch"


def test_published_ci_is_used_for_significance():
    values = [0.65] * 22
    values[0] = 0.55
    ci = {code: (v - 0.02, v + 0.02) for code, v in zip(CODES, values)}
    assert assess_series(_series(values, None, ci=ci, national=0.65), TWINS, GOOD, **T)["01"].state == "leak"
    wide = {code: (v - 0.2, v + 0.2) for code, v in zip(CODES, values)}
    assert assess_series(_series(values, None, ci=wide, national=0.65), TWINS, GOOD, **T)["01"].state == "watch"


def test_lower_better_direction():
    values = [0.40] * 22
    values[0] = 0.55  # more waiting = worse
    ci = {code: (v - 0.01, v + 0.01) for code, v in zip(CODES, values)}
    assert assess_series(_series(values, None, direction="lower_better", ci=ci, national=0.40), TWINS, GOOD, **T)["01"].state == "leak"


@pytest.mark.parametrize(
    "visibility,states,expected",
    [
        (0.49, ["leak"], "watch"),      # never Leak below the visibility gate
        (0.49, ["ok"], "unknown"),
        (0.50, ["leak"], "leak"),       # exactly at the gate passes
        (0.80, ["ok", "watch"], "watch"),
        (0.80, ["ok"], "ok"),
        (0.80, ["unknown"], "unknown"),
        (0.80, [], "unknown"),
    ],
)
def test_stage_state_rules(visibility, states, expected):
    assert stage_state(visibility, states, min_stage_visibility=0.5) == expected


def test_significantly_better_county_is_ok_not_watch():
    values = [0.75] * 22
    values[0] = 0.85  # clearly better than national and twins
    assert assess_series(_series(values, [2000] * 22), TWINS, GOOD, **T)["01"].state == "ok"


def test_tiny_but_significant_gap_is_not_a_leak():
    values = [0.75] * 22
    values[0] = 0.735  # 1.5 pp worse; with n = 200,000 it is statistically significant
    result = assess_series(_series(values, [200_000] * 22), TWINS, GOOD, **T)["01"]
    assert result.interval[1] < 0.75  # significant...
    assert result.state != "leak"      # ...but below the 3 pp practical threshold


def test_four_pp_gap_at_small_n_is_watch_not_leak():
    values = [0.75] * 22
    values[0] = 0.71  # 4 pp worse: practical, but n = 200 cannot show significance
    assert assess_series(_series(values, [200] * 22), TWINS, GOOD, **T)["01"].state == "watch"


def test_twin_median_is_robust_to_one_outlier_twin():
    values = [0.75] * 22
    values[CODES.index("04")] = 0.40  # one twin of 01 is an outlier
    result = assess_series(_series(values, [2000] * 22), TWINS, GOOD, **T)["01"]
    assert result.twin_median == pytest.approx(0.75)


@pytest.mark.parametrize("usable_twins", [0, 1])
def test_too_few_usable_twin_values_caps_at_watch(usable_twins):
    values = [0.75] * 22
    values[0] = 0.60
    for i, code in enumerate(("02", "03", "04")):
        if i >= usable_twins:
            values[CODES.index(code)] = float("nan")
    series = _series(values, [2000] * 22)
    series = SeriesInput(**{**series.__dict__, "national": 0.75})  # published national value
    result = assess_series(series, TWINS, GOOD, **T)["01"]
    assert result.state == "watch" and result.twin_median is None
    assert "twin reference unavailable" in result.reason


def test_twins_below_min_denominator_do_not_count():
    values = [0.75] * 22
    values[0] = 0.60
    dens = [2000] * 22
    for code in ("02", "03"):
        dens[CODES.index(code)] = 10
    assert assess_series(_series(values, dens), TWINS, GOOD, **T)["01"].state == "watch"


def test_ratio_series_never_uses_wilson():
    series = SeriesInput("s", "site:x", "treatment", "higher_better", dict(zip(CODES, [0.6] * 21 + [0.3])),
                         dict(zip(CODES, [500] * 22)), {}, None, unit="ratio")
    result = assess_series(series, TWINS, GOOD, **T)["90"]
    assert result.interval is None and result.state == "watch"


def test_out_of_range_share_does_not_crash_wilson():
    values = [0.75] * 22
    values[0] = 1.02
    result = assess_series(_series(values, [2000] * 22), TWINS, GOOD, **T)["01"]
    assert result.interval is None


def test_stricter_stage_z_reduces_borderline_leaks():
    values = [0.75] * 22
    values[0] = 0.70  # 5 pp worse at n = 400: significant at 1.96, not at 2.576
    loose = assess_series(_series(values, [400] * 22), TWINS, GOOD, **T)["01"].state
    strict = assess_series(_series(values, [400] * 22), TWINS, GOOD, **dict(T, z=2.576))["01"].state
    assert (loose, strict) == ("leak", "watch")


def test_published_ci_is_widened_proportionally_on_each_side():
    values = [0.65] * 22
    values[0] = 0.55
    ci = {code: (v - 0.04, v + 0.08) for code, v in zip(CODES, values)}  # asymmetric
    result = assess_series(_series(values, None, ci=ci), TWINS, GOOD, **dict(T, z=1.96 * 2))["01"]
    assert result.interval == (pytest.approx(0.55 - 0.08), pytest.approx(0.55 + 0.16))


def test_twin_median_alone_never_makes_a_leak():
    """No national value (none published, pooling impossible): cap at Watch."""
    values = [0.75] * 22
    values[0] = 0.50
    series = SeriesInput("x", "all", "detection", "higher_better", dict(zip(CODES, values)),
                         {"01": 2000}, {}, None)  # denominators incomplete -> no pooled national
    result = assess_series(series, TWINS, GOOD, **T)["01"]
    assert result.state == "watch" and "national reference unavailable" in result.reason


def test_excluded_units_come_back_as_unknown_rows():
    values = [0.75] * 21
    series = SeriesInput("x", "all", "detection", "higher_better", dict(zip(CODES[1:], values)),
                         dict(zip(CODES[1:], [2000] * 21)), {}, 0.75, excluded={"01": "denominator 25 < 30"})
    result = assess_series(series, TWINS, GOOD, **T)
    assert result["01"].state == "unknown" and result["01"].reason == "denominator 25 < 30"


def test_value_on_a_ci_bound_still_widens_both_sides():
    values = [0.65] * 22
    values[0] = 0.60
    ci = {code: (v - 0.05, v + 0.05) for code, v in zip(CODES, values)}
    ci["01"] = (0.55, 0.60)  # value sits on the upper bound
    result = assess_series(_series(values, None, ci=ci), TWINS, GOOD, **dict(T, z=1.96 * 2))["01"]
    assert result.interval[1] > 0.60  # widened by the half-width, not stuck on the bound


def test_value_outside_its_ci_gives_no_interval():
    values = [0.65] * 22
    values[0] = 0.62
    ci = {code: (v - 0.05, v + 0.05) for code, v in zip(CODES, values)}
    ci["01"] = (0.55, 0.60)
    assert assess_series(_series(values, None, ci=ci), TWINS, GOOD, **T)["01"].interval is None
