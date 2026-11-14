"""End-to-end smoke tests: the Streamlit app renders fully and its badges are wired to real state."""

import itertools
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import equal_path.config
import equal_path.geography
import equal_path.observations
import equal_path.paths
import equal_path.trust
import equal_path.viz

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
PATHWAY_TABS = ["County pathway", "All counties"]
SPINE_TABS = ["Coverage", "Reconciliation", "Indicator catalog"]
CONFIG_TABS = ["Scope & Goal 3", "Threshold register", "Action library", "Sources", "Anchors", "Reference times"]
EXPECTED_TABS = PATHWAY_TABS + SPINE_TABS + CONFIG_TABS
# unit table + county indicators + twins + all-counties + coverage + reconciliation + catalog
# + Goal 3 + related + thresholds + rules + sources + anchors + times
EXPECTED_DATAFRAMES = 17  # + glidepath table + sources drawer (F8) + county rule table (F5)


def _run():
    return AppTest.from_file(str(APP), default_timeout=60).run()


_STAMPS = itertools.count()


def _fresh_cache(monkeypatch):
    """Force a cache miss for this test's run (the app keys its cache on input_stamp)."""
    key = ("test", next(_STAMPS))
    monkeypatch.setattr(equal_path.trust, "input_stamp", lambda paths: key)


@pytest.fixture
def app():
    return _run()


def _metric(at, label):
    return next(m for m in at.metric if m.label == label)


def _table(at, column):
    """The first dataframe that has `column` (robust to section order)."""
    return next(d.value for d in at.dataframe if column in d.value.columns)


def test_renders_fully_without_exception_or_error(app):
    assert not app.exception, [e.value for e in app.exception]
    assert not app.error, [e.value for e in app.error]
    assert [t.label for t in app.tabs] == EXPECTED_TABS
    assert all(len(tab.children) > 0 for tab in app.tabs), [len(t.children) for t in app.tabs]
    assert len(app.dataframe) == EXPECTED_DATAFRAMES


def test_headline_metrics(app):
    assert _metric(app, "Units on map").value == "22 / 22"
    assert _metric(app, "Cooperation areas").value == "5"
    assert _metric(app, "Action rules").value == "12"


def test_thresholds_badge_reads_frozen(app):
    assert _metric(app, "Thresholds").value == "Frozen"


def test_thresholds_badge_reads_not_frozen_when_lock_breaks(monkeypatch):
    monkeypatch.setattr(equal_path.config, "thresholds_are_frozen", lambda *a, **k: False)
    at = _run()
    assert _metric(at, "Thresholds").value == "NOT FROZEN"
    assert any("edited after freeze" in str(c.value) for c in at.caption)
    assert any("NOT frozen" in str(e.value) for e in at.error)
    assert not any("Frozen before any county result" in str(c.value) for c in at.caption)


def test_failing_report_shows_red_failing_caption(monkeypatch, tmp_path):
    report = tmp_path / "report.xml"
    report.write_text(
        '<testsuites><testsuite name="x" tests="10" failures="3" errors="0" skipped="0" '
        'timestamp="2026-11-13T22:00:00"/></testsuites>',
        encoding="utf-8",
    )
    monkeypatch.setattr(equal_path.paths, "TEST_REPORT", report)
    at = _run()
    assert _metric(at, "Tests passing").value == "7 / 10"
    assert any(":red[3 failing]" in str(c.value) for c in at.caption)


def test_missing_report_shows_not_run(monkeypatch, tmp_path):
    monkeypatch.setattr(equal_path.paths, "TEST_REPORT", tmp_path / "absent.xml")
    at = _run()
    assert _metric(at, "Tests").value == "not run"


def test_map_is_configured_for_offline_and_no_zoom(app):
    config = json.loads(app.get("plotly_chart")[0].proto.config)
    assert config["topojsonURL"] == "/app/static/topojson/"
    assert config["scrollZoom"] is False


def test_indicator_counts_follow_the_store(app):
    from equal_path.observations import indicator_counts

    counts = indicator_counts()
    table = _table(app, "Municipalities").set_index("Code")
    assert {code: int(table.loc[code, "Indicators loaded"]) for code in table.index} == {
        code: counts.get(code, 0) for code in table.index
    }
    banner = " ".join(str(i.value) for i in app.info)
    assert ("No indicator data loaded" in banner) == (not counts)


def test_unit_table_counts_are_numeric(app):
    table = _table(app, "Municipalities")
    assert table["Municipalities"].dtype.kind == "i"
    assert table["Municipalities"].sum() == 308 - 16  # mainland municipalities (Åland has 16)


def test_highlight_filters_table_to_area(app):
    app.selectbox[0].select("Sisä-Suomi").run()
    assert not app.exception and not app.error
    assert list(_table(app, "Municipalities")["Unit"]) == ["Kanta-Häme", "Pirkanmaa", "Etelä-Pohjanmaa"]


def test_cache_is_keyed_on_input_state(monkeypatch):
    first = _run()
    assert _metric(first, "Action rules").value == "12"
    eleven = equal_path.config.load_rules()[:11]
    monkeypatch.setattr(equal_path.config, "load_rules", lambda *a, **k: eleven)
    _fresh_cache(monkeypatch)
    assert _metric(_run(), "Action rules").value == "11"


def test_config_failure_shows_readable_error(monkeypatch):
    def broken(*args, **kwargs):
        raise ValueError("cannot read rules.yaml: found duplicate key 'id'")

    monkeypatch.setattr(equal_path.config, "load_rules", broken)
    _fresh_cache(monkeypatch)
    at = _run()
    assert not at.exception
    assert any("Configuration or reference data failed validation" in str(e.value) for e in at.error)
    assert any("rules.yaml" in str(e.value) for e in at.error)


def test_rendering_bug_surfaces_as_exception(monkeypatch):
    def broken(*args, **kwargs):
        raise KeyError("programming error")

    monkeypatch.setattr(equal_path.viz, "unit_map_figure", broken)
    at = _run()
    assert at.exception
    assert not any("failed validation" in str(e.value) for e in at.error)


def test_units_on_map_counts_drawn_units(monkeypatch):
    real = equal_path.geography.load_unit_geojson()
    partial = {**real, "features": real["features"][:21]}
    monkeypatch.setattr(equal_path.geography, "load_unit_geojson", lambda *a, **k: partial)
    _fresh_cache(monkeypatch)
    assert _metric(_run(), "Units on map").value == "21 / 22"


def test_indicator_counts_flow_into_table(monkeypatch):
    monkeypatch.setattr(equal_path.observations, "indicator_counts", lambda *a, **k: {"08": 2})
    _fresh_cache(monkeypatch)
    table = _table(_run(), "Municipalities").set_index("Unit")
    assert table.loc["Pirkanmaa", "Indicators loaded"] == 2
    assert table.drop(index="Pirkanmaa")["Indicators loaded"].eq(0).all()


def test_stale_caption_when_fingerprint_not_current(monkeypatch, tmp_path):
    monkeypatch.setattr(equal_path.paths, "TEST_FINGERPRINT", tmp_path / "absent.json")
    at = _run()
    assert any("stale" in str(c.value) for c in at.caption)


def test_no_stale_caption_when_fingerprint_current(monkeypatch):
    monkeypatch.setattr(equal_path.trust, "fingerprint_is_current", lambda *a, **k: True)
    at = _run()
    assert not any("stale" in str(c.value) for c in at.caption)


def test_zero_test_report_says_no_tests_ran(monkeypatch, tmp_path):
    report = tmp_path / "report.xml"
    report.write_text('<testsuites><testsuite name="x" tests="0" failures="0" errors="0" skipped="0"/></testsuites>', encoding="utf-8")
    monkeypatch.setattr(equal_path.paths, "TEST_REPORT", report)
    at = _run()
    assert any("no tests ran" in str(c.value) for c in at.caption)
    assert not any("0 failing" in str(c.value) for c in at.caption)


def test_banner_says_scope_pending():
    at = _run()
    banner = " ".join(str(i.value) for i in at.info)
    assert "second cancer pending" in banner


def test_banner_when_no_store(monkeypatch):
    monkeypatch.setattr(equal_path.observations, "indicator_counts", lambda *a, **k: {})
    _fresh_cache(monkeypatch)
    banner = " ".join(str(i.value) for i in _run().info)
    assert "No indicator data loaded" in banner


def test_action_library_shows_trigger_kpi_and_guards(app):
    columns = set(_table(app, "Owner level").columns)
    assert {"Trigger", "KPI", "Do not fire if", "Note"} <= columns


def test_threshold_register_shows_provenance(app):
    table = _table(app, "Provenance")
    assert list(table.columns) == ["Parameter", "Value", "Provenance"]
    assert set(table["Provenance"]) == {"Appendix B", "Section 8 method constant", "Team-set (not in spec)", "Register metadata"}


def test_coverage_matrix_has_every_catalog_indicator_and_unit(app):
    from equal_path.config import load_indicator_catalog

    matrix = _table(app, "Pirkanmaa")
    assert len(matrix) == len(load_indicator_catalog())
    assert len([c for c in matrix.columns if c not in ("Stage", "Indicator", "Status")]) == 22


def test_reconciliation_table_shows_computed_results(app):
    table = _table(app, "Computed")
    assert {"Anchor", "Published", "Computed", "Tolerance", "Status"} <= set(table.columns)
    assert not table["Status"].str.contains("fail").any()


def _pathway_county(at):
    return next(sb for sb in at.selectbox if sb.label == "County")


def test_pathway_defaults_to_helsinki_and_shows_five_stages(app):
    assert _pathway_county(app).value == "90 Helsinki"
    stage_text = " ".join(str(m.value) for m in app.markdown)
    for stage in ("Detection", "Referral", "Diagnosis", "Treatment", "Timing"):
        assert stage in stage_text


def test_selected_county_page_follows_the_results(app):
    """Pick a county that has a leak in the CURRENT results (no hard-coded county)."""
    from equal_path.pathway import run_pathway

    result = run_pathway()
    code, stage = next((c, s) for c in result.stages.index for s in ("treatment", "detection")
                       if result.stages.loc[c, s] == "leak")
    option = next(o for o in _pathway_county(app).options if o.startswith(code + " "))
    _pathway_county(app).select(option).run()
    assert not app.exception and not app.error
    table = _table(app, "Gap vs national (pp)")
    assert {"Test interval at stage level (%)", "Better twins"} <= set(table.columns)
    assert (table["State"] == "leak").any()
    assert any(stage in str(m.value).lower() and "leak" in str(m.value).lower() for m in app.markdown)


def test_all_counties_overview_lists_22_units(app):
    table = _table(app, "Visibility score")
    assert len(table) == 22 and {"Detection", "Timing", "Primary finding"} <= set(table.columns)


def test_pathway_states_are_wired_to_the_results(monkeypatch):
    import equal_path.pathway

    real = equal_path.pathway.run_pathway()
    forced = real.stages.copy()
    forced.loc["90", "referral"] = "leak"
    monkeypatch.setattr(equal_path.pathway, "run_pathway", lambda *a, **k: real.__class__(**{**real.__dict__, "stages": forced}))
    _fresh_cache(monkeypatch)
    at = _run()
    assert any("referral" in str(m.value).lower() and "leak" in str(m.value).lower() for m in at.markdown)


def test_tipping_point_and_provisional_twins_are_explained(app):
    captions = " ".join(str(c.value) for c in app.caption)
    assert "not computable" in captions
    assert "human review" in captions  # twins final, plausibility check still open
    assert "Bonferroni" in captions
    markdown = " ".join(str(m.value) for m in app.markdown)
    assert "typical nearest-twin distance" in markdown


def test_glidepath_table_is_labelled_indicative(app):
    table = _table(app, "Bootstrap median 2035 (%)")
    assert set(table["Programme"]) == {"breast", "cervical", "colorectal"}
    assert any("indicative" in str(c.value) for c in app.caption)


def test_glidepath_table_shows_both_numbers_the_verdict_uses(app):
    """'On track' needs the Theil-Sen line and the bootstrap median at >= 80 %; both must be visible
    so a reader can see why e.g. a median of 80.3 % with a line of 75.4 % is only 'uncertain'."""
    table = _table(app, "Trend line 2035 (%)")
    assert "Bootstrap median 2035 (%)" in table.columns
    on_track = table[table.State == "on track"]
    assert (on_track["Trend line 2035 (%)"] >= 80).all() and (on_track["Bootstrap median 2035 (%)"] >= 80).all()


def test_twin_stability_and_early_warning_are_explained(app):
    markdown = " ".join(str(m.value) for m in app.markdown)
    assert "stability" in markdown.lower()
    assert any("early warning" in str(c.value).lower() for c in app.caption)


def test_overview_shows_twin_stability(app):
    assert "Twin stability" in _table(app, "Visibility score").columns


def test_every_county_page_renders(app):
    """Each county's page (twin drivers, glidepath, tables) renders without an exception."""
    for option in _pathway_county(app).options:
        _pathway_county(app).select(option).run()
        assert not app.exception, (option, [e.value for e in app.exception])


def test_overview_stage_columns_equal_the_gap_locator(app):
    """Review G-8: the All counties overview shows exactly the gap locator's states."""
    from equal_path.pathway import run_pathway

    stages = run_pathway().stages
    table = _table(app, "Visibility score").set_index("Code")
    for stage in stages.columns:
        assert table[stage.capitalize()].to_dict() == stages[stage].to_dict(), stage


def test_reset_map_view_rekeys_the_chart(app):
    """Review M-2: Streamlit turns on panning when map clicks are enabled; a reset re-draws the map."""
    before = app.session_state["_map_nonce"] if "_map_nonce" in app.session_state else 0
    next(b for b in app.button if b.label == "Reset map view").click().run()
    assert app.session_state["_map_nonce"] == before + 1


def test_action_library_shows_each_rules_machine_condition(app):
    from equal_path.config import load_rules

    table = _table(app, "Machine condition").set_index("ID")
    for rule in load_rules():
        assert all(c in table.loc[rule.id, "Machine condition"] for c in (*rule.when, *rule.when_any)), rule.id


def test_county_page_offers_the_action_card_pdf(app):
    assert any(b.label.startswith("Download Action Card") for b in app.get("download_button"))


def test_downloaded_pdf_is_the_selected_countys_card(monkeypatch):
    """Review W-3: the download button carries this county's card, the same lines as on screen."""
    import streamlit

    from equal_path.card import pdf_text_lines

    seen = {}
    real = streamlit.download_button

    def spy(label, data=None, file_name=None, **kwargs):
        if label.startswith("Download Action Card"):
            seen.update(data=data, file_name=file_name)
        return real(label, data=data, file_name=file_name, **kwargs)

    monkeypatch.setattr(streamlit, "download_button", spy)
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["county"] = "10 Kymenlaakso"
    at.run()
    lines = pdf_text_lines(seen["data"])
    assert seen["file_name"] == "equal-path-action-card-10.pdf" and lines[0] == "Equal Path Action Card: Kymenlaakso (10)"
    shown = [str(m.value).removeprefix("#### ") for m in at.markdown]
    assert lines[0] in shown and any("Hub-and-spoke" in line for line in lines)


def test_county_page_shows_the_validated_briefing():
    """F7 on the page: the briefing (template here: no API key in tests) with its validator status."""
    from equal_path.actions import run_actions
    from equal_path.analyst import briefing_facts, template_briefing

    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["county"] = "10 Kymenlaakso"
    at.run()
    shown = [str(m.value) for m in at.markdown]
    for line in template_briefing(briefing_facts("10", run_actions())).splitlines():
        assert line in shown, line
    captions = " ".join(str(c.value) for c in at.caption)
    assert "passed the number validator" in captions and "deterministic template" in captions
    assert "Access times for Kymenlaakso are not available here" in captions
