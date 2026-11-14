"""Step 8 hardening: cached analyst text, offline mode, cold start, trust / limitations / data-gap panels, rehearsal."""

import json
import socket
import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from equal_path.hardening import (
    BRIEFINGS_FILE, DEMO_COUNTIES, block_network, cached_briefing, data_gaps, facts_hash, limitations, load_cache,
    trust_figures,
)

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
CODES = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11",
         "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "90"]


@pytest.fixture(scope="module")
def run():
    from equal_path.actions import run_actions

    return run_actions()


# --- cached analyst text ---------------------------------------------------------------------------

def test_cache_covers_every_county_and_is_current(run):
    """Spec F8 offline: cached analyst text for every county; a data change without rebuilding fails here."""
    from equal_path.analyst import briefing_facts, validate

    cache = load_cache()
    assert set(cache) == set(CODES)
    for code in CODES:
        facts = briefing_facts(code, run)
        entry = cache[code]
        assert entry["facts_hash"] == facts_hash(facts), f"{code}: rebuild with scripts/cache_briefings.py"
        assert validate(entry["text"], facts).ok


def test_stale_or_unvalidated_cache_entries_are_never_shown(run):
    from equal_path.analyst import briefing_facts

    facts = briefing_facts("10", run)
    entry = load_cache()["10"]
    assert cached_briefing(facts, {"10": entry}, "10") is not None
    assert cached_briefing(facts, {"10": {**entry, "facts_hash": "stale"}}, "10") is None
    assert cached_briefing(facts, {"10": {**entry, "text": entry["text"].replace("5.2 pp", "9.9 pp")}}, "10") is None


def test_cache_file_is_plain_json_with_provenance():
    data = json.loads(BRIEFINGS_FILE.read_text(encoding="utf-8"))
    for entry in data.values():
        assert {"facts_hash", "text", "source", "model", "generated_on"} <= set(entry)


# --- offline mode -----------------------------------------------------------------------------------

def test_block_network_really_blocks():
    with block_network():
        with pytest.raises(OSError):
            socket.create_connection(("example.com", 80), timeout=1)


@pytest.mark.parametrize("code", CODES)
def test_every_county_loads_offline_with_cached_analyst_text(code):
    """Spec F8 Offline mode (P0): with the network disabled, all 22 counties load and cached text appears."""
    from equal_path.geography import load_units

    names = dict(zip(load_units()["code"], load_units()["short_fi"]))
    with block_network():
        at = AppTest.from_file(str(APP), default_timeout=60)
        at.session_state["county"] = f"{code} {names[code]}"
        at.run()
    assert not at.exception, [e.value for e in at.exception]
    captions = " ".join(str(c.value) for c in at.caption)
    assert "from the offline cache" in captions and "passed the number validator" in captions


def test_cold_start_is_under_10_seconds(monkeypatch):
    """Spec F8: cold start under 10 s (fresh data cache, network blocked)."""
    import itertools

    import equal_path.trust

    key = ("cold", next(itertools.count()), time.time())
    monkeypatch.setattr(equal_path.trust, "input_stamp", lambda paths: key)
    started = time.perf_counter()
    with block_network():
        at = AppTest.from_file(str(APP), default_timeout=60).run()
    elapsed = time.perf_counter() - started
    assert not at.exception and elapsed < 10.0, elapsed


# --- trust, limitations and data-gap panels ------------------------------------------------------------

def test_trust_figures_come_from_the_actual_runs(run):
    """Spec F8 Trust panel: counties reconciled, tests passing, unsupported numbers blocked; not hard-coded."""
    from equal_path.config import load_anchors, load_thresholds
    from equal_path.observations import load_observations, reconcile_anchors
    from equal_path.paths import TEST_REPORT
    from equal_path.trust import read_test_summary

    figures = trust_figures(reconcile_anchors(load_observations(), load_anchors(), load_thresholds()), run,
                            read_test_summary(TEST_REPORT))
    results = reconcile_anchors(load_observations(), load_anchors(), load_thresholds())
    assert figures["anchors_passed"] == sum(r.status == "pass" for r in results)
    assert figures["anchors_checked"] == sum(r.status in ("pass", "fail") for r in results)
    assert figures["briefings_passed"] == 22 and figures["briefings"] == 22
    assert figures["unsupported_numbers_shown"] == 0
    summary = read_test_summary(TEST_REPORT)
    assert (figures["tests_passed"], figures["tests_total"]) == (summary.passed, summary.total)


def test_trust_figures_change_with_their_inputs(run):
    from types import SimpleNamespace

    figures = trust_figures([SimpleNamespace(status="pass"), SimpleNamespace(status="fail")], run,
                            SimpleNamespace(passed=7, total=9))
    assert (figures["anchors_passed"], figures["anchors_checked"], figures["tests_passed"], figures["tests_total"]) == (1, 2, 7, 9)


def test_data_gap_panel_lists_what_is_missing():
    from equal_path.config import load_indicator_catalog
    from equal_path.observations import load_observations

    gaps = data_gaps(load_indicator_catalog(), load_observations())
    timing = gaps[gaps.Stage == "timing"]
    assert len(timing) == 3 and (timing["Units with a value"] == "0 of 22").all()
    assert set(gaps.Status) <= {"not_public", "partial", "to_verify", "available"}
    assert "stage_one_two_share" in set(gaps.Indicator)


def test_limitations_are_computed_not_typed(run):
    from equal_path.glidepath import calibration

    texts = [text for text, _ in limitations(run)]
    calib = calibration()
    assert any(f"{calib.covered}/{calib.series}" in t for t in texts)
    assert any("Pirkanmaa" in t and "own stage-recording" in t for t in texts)
    assert any("second" in t.lower() and "cancer" in t.lower() for t in texts)
    assert all(source for _, source in limitations(run))


def test_app_shows_the_three_panels():
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert "Trust" in " ".join(m.label for m in at.metric)
    labels = [t.label for t in at.tabs]
    assert {"Data gaps", "Limitations"} <= set(labels)


# --- rehearsal --------------------------------------------------------------------------------------

def test_rehearsal_runs_offline_with_zero_rejections():
    """Spec: rehearsals finish with zero validator rejections on the demo counties (one run here; the script runs 5)."""
    from equal_path.hardening import rehearse

    report = rehearse(runs=1)
    assert report["runs"] == 1 and report["counties"] == list(DEMO_COUNTIES)
    assert report["validator_rejections"] == 0 and report["exceptions"] == 0 and report["network_blocked"]
