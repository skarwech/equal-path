"""F6 screening scenario model: sourced baselines, reproducibility and monotonicity."""

import pytest

from equal_path.observations import load_observations
from equal_path.simulator import PROGRAMMES, screening_baseline, simulate_screening


@pytest.mark.parametrize("programme", list(PROGRAMMES))
def test_real_2024_baseline_uses_complete_county_data(programme):
    baseline, problem = screening_baseline(load_observations(), "10", programme)

    assert problem == ""
    assert baseline is not None
    assert baseline.eligible > 0
    assert 0 <= baseline.attended <= baseline.eligible
    assert baseline.pooled_attended >= baseline.attended
    assert 0 <= baseline.pooled_detections <= baseline.pooled_attended
    assert baseline.participation == pytest.approx(baseline.attended / baseline.eligible)


def test_baseline_target_produces_exactly_zero_incremental_outputs():
    baseline, problem = screening_baseline(load_observations(), "10", "Breast")
    assert problem == "" and baseline is not None

    result = simulate_screening(baseline, baseline.participation, assumed_early_stage_share=0.5)

    assert result.additional_attendees == 0
    assert result.additional_detections_low == result.additional_detections_median == result.additional_detections_high == 0
    assert result.early_stage_low == result.early_stage_median == result.early_stage_high == 0


def test_simulation_is_reproducible_and_outputs_are_monotonic():
    baseline, problem = screening_baseline(load_observations(), "10", "Breast")
    assert problem == "" and baseline is not None

    target = max(baseline.participation, 0.8)
    first = simulate_screening(baseline, target, assumed_early_stage_share=0.5)
    repeated = simulate_screening(baseline, target, assumed_early_stage_share=0.5)
    full = simulate_screening(baseline, 1.0, assumed_early_stage_share=0.5)

    assert first == repeated
    assert full.additional_attendees >= first.additional_attendees
    assert full.additional_detections_low >= first.additional_detections_low
    assert full.additional_detections_median >= first.additional_detections_median
    assert full.additional_detections_high >= first.additional_detections_high
    assert full.early_stage_low >= first.early_stage_low
    assert full.early_stage_median >= first.early_stage_median
    assert full.early_stage_high >= first.early_stage_high


def test_simulator_rejects_inputs_outside_scenario_bounds():
    baseline, problem = screening_baseline(load_observations(), "10", "Breast")
    assert problem == "" and baseline is not None

    with pytest.raises(ValueError, match="target participation"):
        simulate_screening(baseline, baseline.participation - 0.01)
    with pytest.raises(ValueError, match="target participation"):
        simulate_screening(baseline, 1.01)
    with pytest.raises(ValueError, match="early-stage share"):
        simulate_screening(baseline, baseline.participation, 1.01)
