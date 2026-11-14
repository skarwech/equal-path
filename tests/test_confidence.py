"""F8 county page: confidence badge per stage and the reason every grey (Unknown) stage gives."""

import pandas as pd
import pytest

from equal_path.confidence import stage_confidence, stage_reason
from equal_path.gaps import low_visibility, stage_state

KW = dict(min_stage_visibility=0.5, min_stability=0.6)


def _rows(*items):
    """(state, interval) per assessed series in one stage for one county."""
    return pd.DataFrame([{"state": s, "interval": i, "indicator_id": f"ind{k}", "reason": "r"} for k, (s, i) in enumerate(items)])


def test_one_low_visibility_predicate_shared_with_the_gap_locator():
    """Hatching, the badge and F2's Leak gate must agree at the boundary (Kymenlaakso treatment sits at 0.50)."""
    assert low_visibility(0.4999, 0.5) and not low_visibility(0.5, 0.5)
    assert stage_state(0.5, ["leak"], 0.5) == "leak" and stage_state(0.4999, ["leak"], 0.5) == "watch"
    assert stage_confidence(0.5, _rows(("ok", (0.1, 0.2))), True, 0.9, **KW).level == "high"
    assert stage_confidence(0.4999, _rows(("ok", (0.1, 0.2))), True, 0.9, **KW).level == "low"


@pytest.mark.parametrize(
    "visibility,rows,good,stability,level",
    [
        (0.86, _rows(("ok", (0.1, 0.2)), ("watch", (0.3, 0.4))), True, 0.73, "high"),
        (0.86, _rows(("ok", (0.1, 0.2)), ("ok", None)), True, 0.73, "medium"),   # one series has no n or CI
        (0.86, _rows(("ok", (0.1, 0.2))), True, 0.59, "medium"),                 # unstable twin set
        (0.86, _rows(("ok", (0.1, 0.2))), False, 0.90, "medium"),                # no good twin
        (0.86, _rows(("unknown", None)), True, 0.90, "medium"),                  # nothing could be judged
        (0.33, _rows(("ok", (0.1, 0.2))), True, 0.90, "low"),                    # too little observable
        (0.00, _rows(), True, 0.90, "low"),
    ],
)
def test_confidence_rule(visibility, rows, good, stability, level):
    result = stage_confidence(visibility, rows, good, stability, **KW)
    assert result.level == level
    assert (result.reasons == ()) == (level == "high")  # every downgrade says why


def test_confidence_reasons_name_the_cause():
    reasons = stage_confidence(0.86, _rows(("ok", None)), True, 0.59, **KW).reasons
    assert any("no published n or CI" in r for r in reasons)
    assert any("0.59" in r and "0.6" in r for r in reasons)


@pytest.fixture(scope="module")
def result():
    from equal_path.pathway import run_pathway

    return run_pathway()


@pytest.fixture(scope="module")
def catalog():
    from equal_path.config import load_indicator_catalog

    return {i.id: i for i in load_indicator_catalog()}


@pytest.fixture(scope="module")
def store():
    from equal_path.observations import load_observations

    return load_observations()


def test_every_grey_stage_explains_why(result, catalog, store):
    """Spec F8: every grey stage explains why, for every county, including the separate Timing row."""
    for code in result.stages.index:
        for stage, state in result.stages.loc[code].items():
            reason = stage_reason(result, store, catalog, code, stage, 0.5)
            if state == "unknown":
                assert reason and "Unknown" in reason, (code, stage)
            else:
                assert reason == "", (code, stage)


def test_pirkanmaa_diagnosis_is_grey_despite_one_observed_indicator(result, catalog, store):
    """Pirkanmaa has stage-recording coverage (value present, judged ok), yet the stage is Unknown:
    1 of 3 diagnosis indicators is not enough. 'No data' would be wrong; the reason must say so."""
    reason = stage_reason(result, store, catalog, "08", "diagnosis", 0.5)
    assert "1 of 3" in reason and "33%" in reason
    assert "Stage-recording coverage" in reason.split("Missing")[0]  # named as observed, not as missing
    assert "not published by county" in reason


def test_timing_reason_says_it_is_a_separate_row(result, catalog, store):
    reason = stage_reason(result, store, catalog, "90", "timing", 0.5)
    assert "separate row" in reason and "0 of 3" in reason


def test_diagnosis_confidence_is_low_everywhere_on_real_data(result):
    from equal_path.confidence import county_confidence
    from equal_path.config import load_thresholds

    t = load_thresholds()
    for code in result.stages.index:
        assert county_confidence(result, code, t)["diagnosis"].level == "low"
