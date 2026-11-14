"""Section 7.4 tipping point: how much later the unknown-stage cases would have to be
(d, in share points of early stage) before two units' stage I-II ranking flips.

Overall early share = p - (1 - c) * d, so A and B swap at d* = (p_A - p_B) / (c_B - c_A).
A flip is only possible for 0 < d* <= min(p_A, p_B) (the unknown-stage early share p - d
must stay a share); reported in percentage points (smaller = more fragile ranking).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TippingPoint:
    d_star: float
    d_star_pp: float
    feasible: bool


def tipping_point(p_a: float, c_a: float, p_b: float, c_b: float) -> TippingPoint | None:
    for name, value in (("p_a", p_a), ("c_a", c_a), ("p_b", p_b), ("c_b", c_b)):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be a share in 0-1, got {value}")
    if c_a == c_b:
        return None  # equal coverage: missing stage cannot change the ranking
    d_star = (p_a - p_b) / (c_b - c_a)
    return TippingPoint(d_star, d_star * 100, 0.0 < d_star <= min(p_a, p_b))
