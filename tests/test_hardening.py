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
    captions = " ".join(str(c.value) for c in at.caption if str(c.value).startswith("Written by"))   # not the header badge
    assert "from the offline cache" in captions and "passed the number validator" in captions


def test_cold_start_is_under_10_seconds():
    """Spec F8: cold start under 10 s, in a fresh process incl. imports, network blocked (review O-7)."""
    import subprocess
    import sys

    started = time.perf_counter()
    out = subprocess.run([sys.executable, "-B", str(APP.parents[1] / "scripts" / "cold_start.py"), "--no-write"],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stdout + out.stderr
    report = json.loads(out.stdout.strip().splitlines()[-1])
    assert report["cold_start_seconds_offline"] < 10.0 and report["exceptions"] == 0
    assert time.perf_counter() - started < 30


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
    assert figures["anchors_failed"] == sum(r.status == "fail" for r in results)
    assert figures["anchors_total"] == len(results) == 11 and figures["anchors_not_checked"] == 2   # review P-4
    assert figures["briefings_passed"] == 22 and figures["briefings"] == 22 and figures["briefings_from_cache"] == 22
    assert figures["unsupported_numbers_shown"] == 0
    summary = read_test_summary(TEST_REPORT)
    assert (figures["tests_passed"], figures["tests_total"]) == (summary.passed, summary.total)


def test_trust_figures_change_with_their_inputs(run):
    from types import SimpleNamespace

    figures = trust_figures([SimpleNamespace(status="pass"), SimpleNamespace(status="fail")], run,
                            SimpleNamespace(passed=7, total=9))
    assert (figures["anchors_passed"], figures["anchors_failed"], figures["anchors_total"], figures["tests_passed"],
            figures["tests_total"]) == (1, 1, 2, 7, 9)


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
    assert report["validator_rejections"] == 0 and report["exceptions"] == 0
    assert report["not_from_cache"] == 0 and report["cache_entries_missing"] == 0
    assert not report["gate_met"]   # one run is not the five-run gate


def test_rehearsal_counts_rejections_when_the_validator_fails(monkeypatch):
    """Not vacuous: a failing validator must show up as rejections for every demo render."""
    import equal_path.analyst as analyst
    from equal_path.analyst import Validation
    from equal_path.hardening import rehearse

    monkeypatch.setattr(analyst, "validate", lambda text, facts: Validation(False, ("forced",)))
    assert rehearse(runs=1)["validator_rejections"] == len(DEMO_COUNTIES)



# --- review fixes (Step 8) -------------------------------------------------------------------------

def test_rehearsal_fails_without_the_cache(monkeypatch):
    """Review O-1: no cache means the page shows the template, which the rehearsal must count."""
    import equal_path.hardening as hardening

    monkeypatch.setattr(hardening, "load_cache", lambda path=None: {})
    report = hardening.rehearse(runs=1)
    assert report["not_from_cache"] == len(DEMO_COUNTIES) and report["cache_entries_missing"] == len(DEMO_COUNTIES)


def test_block_network_counts_refusals_and_covers_more_paths():
    """Review O-6."""
    with block_network() as block:
        for call in (lambda: socket.gethostbyname("example.com"), lambda: socket.socket().connect_ex(("127.0.0.1", 9)),
                     lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b"x", ("127.0.0.1", 9))):
            with pytest.raises(OSError):
                call()
    assert block.refused == 3


def _entry(code="10"):
    return dict(load_cache()[code])


def test_edited_words_or_text_hash_are_never_shown(run):
    """Review O-2: edited words (not only numbers) are refused."""
    from equal_path.analyst import briefing_facts
    from equal_path.hardening import _sha

    facts = briefing_facts("10", run)
    entry = _entry()
    words = entry["text"].replace("Top action: Implement", "Top action: Close the county unit; implement")
    assert cached_briefing(facts, {"10": {**entry, "text": words, "text_hash": _sha(words)}}, "10") is None
    assert cached_briefing(facts, {"10": {**entry, "text_hash": "edited"}}, "10") is None


def test_corrupt_or_malformed_cache_falls_back(tmp_path, run):
    """Review O-5."""
    from equal_path.analyst import briefing_facts

    bad = tmp_path / "briefings.json"
    bad.write_text("{not json", encoding="utf-8")
    assert load_cache(bad) == {}
    facts = briefing_facts("10", run)
    assert cached_briefing(facts, {"10": {"text": 5}}, "10") is None and cached_briefing(facts, {"10": "x"}, "10") is None


def test_cache_wins_over_a_failing_live_client(monkeypatch):
    """Review O-3: SDK and credentials present but no network: the current cache entry is still shown."""
    import sys

    import equal_path.analyst as analyst

    sys.path.insert(0, str(Path(__file__).parent))
    from test_analyst import FakeClient

    monkeypatch.setattr(analyst, "make_client", lambda: FakeClient([ConnectionError("offline")] * 3))
    with block_network():
        at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert any(str(c.value).startswith("Written by") and "from the offline cache" in str(c.value) for c in at.caption)


def test_cached_claude_text_keeps_its_provenance(monkeypatch, run, tmp_path):
    """Review O-4: a Claude entry from the cache shows the model and the cache date."""
    import equal_path.hardening as hardening
    from equal_path.analyst import briefing_facts, template_briefing
    from equal_path.hardening import _sha

    cache = load_cache()
    text = template_briefing(briefing_facts("90", run))
    cache["90"] = {**cache["90"], "source": "claude", "model": "claude-opus-5-5", "text": text, "text_hash": _sha(text)}
    monkeypatch.setattr(hardening, "load_cache", lambda path=None: cache)
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert any("Written by Claude (claude-opus-5-5) (from the offline cache, generated" in str(c.value) for c in at.caption)


def test_unsupported_number_on_the_page_shows_in_the_trust_figure(monkeypatch, run):
    """Review P-1: the figure is not zero by construction."""
    from types import SimpleNamespace

    import equal_path.hardening as hardening
    from equal_path.analyst import Briefing

    real = hardening.select_briefing

    def tampered(code, run_, cache=None, live=False):
        facts, b = real(code, run_, cache)
        return facts, Briefing(b.text + " Also 77.7 % [S_EQUAL_PATH_SPEC].", b.source, 0, note=b.note)

    monkeypatch.setattr(hardening, "select_briefing", tampered)
    figures = trust_figures([], run, SimpleNamespace(passed=1, total=1))
    assert figures["unsupported_numbers_shown"] == 22 and figures["briefings_passed"] == 0


def test_stale_cache_entry_lowers_the_cache_count(monkeypatch, run):
    """Review P-3: the badge checks what the page shows."""
    from types import SimpleNamespace

    import equal_path.hardening as hardening

    cache = load_cache()
    cache["10"] = {**cache["10"], "facts_hash": "stale"}
    monkeypatch.setattr(hardening, "load_cache", lambda path=None: cache)
    assert trust_figures([], run, SimpleNamespace(passed=1, total=1))["briefings_from_cache"] == 21


def test_trust_caption_follows_the_test_report(monkeypatch):
    """Review P-5: the header badge text changes with the actual test summary."""
    from types import SimpleNamespace

    import equal_path.trust

    monkeypatch.setattr(equal_path.trust, "read_test_summary",
                        lambda path=None: SimpleNamespace(passed=3, total=4, failed=1, all_green=False, timestamp="2026-11-14T00:00"))
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert any("tests 3/4" in str(c.value) for c in at.caption)


def test_data_gap_row_for_stage_coverage_is_true():
    """Review P-2/P-5: one unit value (Pirkanmaa), and the reason says so."""
    from equal_path.config import load_indicator_catalog
    from equal_path.observations import load_observations

    gaps = data_gaps(load_indicator_catalog(), load_observations()).set_index("Indicator")
    row = gaps.loc["stage_recording_coverage"]
    assert row["Units with a value"] == "1 of 22" and "Pirkanmaa" in row["Why"]


def test_data_gaps_are_selected_by_the_store_not_the_status():
    """Review P-6: an 'available' indicator missing a county still appears."""
    from types import SimpleNamespace

    import pandas as pd

    store = pd.DataFrame([{"geo_level": "unit", "county_id": f"{i:02d}", "indicator_id": "x", "value": 1.0} for i in range(21)])
    gaps = data_gaps([SimpleNamespace(id="x", stage="detection", label="X", status="available", limitation="")], store)
    assert list(gaps.Indicator) == ["x"] and gaps.iloc[0]["Units with a value"] == "21 of 22"


def test_limitation_counts_are_computed(run):
    """Review P-5/P-7/P-8: counts from the data; no crash without own coverage; the calibration label is computed."""
    from dataclasses import replace

    from equal_path.config import load_thresholds
    from equal_path.pathway import run_pathway

    result = run_pathway()
    texts = " ".join(t for t, _ in limitations(run, result))
    unstable = sum(v < load_thresholds().twin_stability_jaccard for v in result.twin_stability.values())
    assert f"in {unstable} of 22 counties" in texts
    grey = sum(f["stage_diagnosis"] == "unknown" for f in run.facts.values())
    assert f"Diagnosis cannot be judged in {grey} of 22" in texts
    no_own = replace(run, facts={c: {**f, "stage_coverage_level": "national"} for c, f in run.facts.items()})
    assert "No county has its own stage-recording figure" in " ".join(t for t, _ in limitations(no_own, result))


def test_glidepath_limitation_uses_the_calibration_label(monkeypatch, run):
    from types import SimpleNamespace

    import equal_path.glidepath as glidepath

    monkeypatch.setattr(glidepath, "calibration", lambda store=None: SimpleNamespace(covered=40, series=44, coverage=0.91,
                                                                                    label="validated"))
    assert any(t.startswith("Glidepaths are validated") for t, _ in limitations(run))
