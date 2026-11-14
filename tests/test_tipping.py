"""Section 7.4 tipping point for stage rankings under missing stage data."""

import pytest

from equal_path.tipping import tipping_point


def test_formula_matches_definition_and_reports_pp():
    p_a, c_a, p_b, c_b = 0.60, 0.40, 0.55, 0.70
    result = tipping_point(p_a, c_a, p_b, c_b)
    d = (p_a - p_b) / (c_b - c_a)
    assert result.d_star == pytest.approx(d) and result.d_star_pp == pytest.approx(d * 100)
    assert p_a - (1 - c_a) * d == pytest.approx(p_b - (1 - c_b) * d)  # the ranking flips exactly at d*
    assert result.feasible


def test_negative_d_star_means_the_ranking_cannot_flip():
    result = tipping_point(0.60, 0.50, 0.55, 0.40)
    assert result.d_star < 0 and not result.feasible


def test_d_star_larger_than_the_early_share_is_infeasible():
    result = tipping_point(0.60, 0.40, 0.55, 0.41)  # d* = 5.0: unknown-stage early share would be negative
    assert not result.feasible


def test_equal_coverage_has_no_tipping_point():
    assert tipping_point(0.6, 0.5, 0.55, 0.5) is None


@pytest.mark.parametrize("bad", [(-0.1, 0.5, 0.5, 0.4), (0.5, 1.2, 0.5, 0.4), (0.5, 0.5, 1.5, 0.4)])
def test_inputs_must_be_shares(bad):
    with pytest.raises(ValueError):
        tipping_point(*bad)
