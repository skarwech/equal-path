"""Map builder and trust-badge test-report parser."""

import pytest

from equal_path.geography import load_unit_geojson, load_units
from equal_path.trust import TestSummary, read_test_summary
from equal_path.viz import HIGHLIGHT, MAP_CONFIG, NEUTRAL, unit_map_figure


@pytest.fixture(scope="module")
def figure_inputs():
    return load_units(), load_unit_geojson()


def test_map_has_22_locations_keyed_by_code(figure_inputs):
    units, geojson = figure_inputs
    trace = unit_map_figure(units, geojson).data[0]
    assert len(trace.locations) == 22
    assert set(trace.locations) == set(units["code"])
    assert trace.featureidkey == "properties.code"


def test_highlight_marks_only_that_area(figure_inputs):
    units, geojson = figure_inputs
    trace = unit_map_figure(units, geojson, highlight_area="Sisä-Suomi").data[0]
    highlighted = {code for code, z in zip(trace.locations, trace.z) if z == 1}
    assert highlighted == {"07", "08", "16"}


def test_no_highlight_is_all_neutral(figure_inputs):
    units, geojson = figure_inputs
    trace = unit_map_figure(units, geojson).data[0]
    assert set(trace.z) == {0}
    assert trace.colorscale[0][1] == NEUTRAL and trace.colorscale[-1][1] == HIGHLIGHT


def test_map_topojson_is_served_locally():
    """Offline mode: Plotly must not fetch world_110m.json from cdn.plot.ly."""
    from equal_path.paths import ROOT

    url = MAP_CONFIG["topojsonURL"]
    assert url.startswith("/app/static/") and "://" not in url
    local = ROOT / "app" / "static" / url.removeprefix("/app/static/") / "world_110m.json"
    assert local.is_file() and local.stat().st_size > 100_000


def test_unknown_highlight_rejected(figure_inputs):
    units, geojson = figure_inputs
    with pytest.raises(ValueError):
        unit_map_figure(units, geojson, highlight_area="Atlantis")


JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" errors="1" failures="2" skipped="3" tests="40"
 time="1.5" timestamp="2026-11-13T21:30:00"></testsuite></testsuites>"""


def test_read_test_summary_counts(tmp_path):
    report = tmp_path / "report.xml"
    report.write_text(JUNIT, encoding="utf-8")
    summary = read_test_summary(report)
    assert summary == TestSummary(total=40, failed=3, skipped=3, passed=34, timestamp="2026-11-13T21:30:00")
    assert not summary.all_green


def test_missing_report_returns_none(tmp_path):
    assert read_test_summary(tmp_path / "absent.xml") is None


def test_corrupt_report_returns_none(tmp_path):
    report = tmp_path / "bad.xml"
    report.write_text("<not-xml", encoding="utf-8")
    assert read_test_summary(report) is None


MULTI_SUITE = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
 <testsuite name="a" errors="0" failures="0" skipped="0" tests="5" timestamp="2026-11-13T21:00:00"/>
 <testsuite name="b" errors="0" failures="2" skipped="1" tests="3" timestamp="2026-11-13T21:01:00"/>
</testsuites>"""


def test_failures_in_any_suite_are_counted(tmp_path):
    report = tmp_path / "multi.xml"
    report.write_text(MULTI_SUITE, encoding="utf-8")
    summary = read_test_summary(report)
    assert (summary.total, summary.failed, summary.skipped, summary.passed) == (8, 2, 1, 5)
    assert not summary.all_green


@pytest.mark.parametrize(
    "attribute",
    ['tests="x"', 'tests=""', 'failures="1"', 'tests="5" failures="-1"', 'tests="5" skipped="-1"',
     'tests="2" failures="3"', 'tests="3" failures="2" skipped="2"'],
)
def test_malformed_counts_return_none(tmp_path, attribute):
    report = tmp_path / "bad_attr.xml"
    report.write_text(f'<testsuites><testsuite name="a" {attribute}/></testsuites>', encoding="utf-8")
    assert read_test_summary(report) is None


def test_report_without_suites_returns_none(tmp_path):
    report = tmp_path / "empty.xml"
    report.write_text("<testsuites/>", encoding="utf-8")
    assert read_test_summary(report) is None


def test_map_interaction_locked():
    assert MAP_CONFIG["scrollZoom"] is False
    assert MAP_CONFIG["displayModeBar"] is False


def test_map_layout_locked_and_hover_row(figure_inputs):
    units, geojson = figure_inputs
    figure = unit_map_figure(units, geojson)
    assert figure.layout.dragmode is False
    trace = figure.data[0]
    row = dict(zip(trace.locations, trace.customdata.tolist()))["08"]
    assert row == ["Pirkanmaa", "Sisä-Suomi", "Pirkanmaa wellbeing services county", 0]


def test_zero_test_report_is_not_green():
    assert not TestSummary(total=0, failed=0, skipped=0, passed=0, timestamp="").all_green


def test_input_fingerprint_detects_edit_add_delete(tmp_path):
    from equal_path.trust import fingerprint_is_current, write_fingerprint

    watched = tmp_path / "src"
    watched.mkdir()
    (watched / "a.py").write_text("a = 1\n", encoding="utf-8")
    (watched / "b.py").write_text("b = 1\n", encoding="utf-8")
    stamp = tmp_path / "fingerprint.json"
    report = tmp_path / "report.xml"
    report.write_text(JUNIT, encoding="utf-8")
    write_fingerprint(stamp, [watched], root=tmp_path, report=report, full_run=True)
    assert fingerprint_is_current(stamp, [watched], root=tmp_path, report=report)

    (watched / "a.py").write_text("a = 2\n", encoding="utf-8")
    assert not fingerprint_is_current(stamp, [watched], root=tmp_path, report=report)
    write_fingerprint(stamp, [watched], root=tmp_path, report=report, full_run=True)

    (watched / "b.py").unlink()
    assert not fingerprint_is_current(stamp, [watched], root=tmp_path, report=report)
    write_fingerprint(stamp, [watched], root=tmp_path, report=report, full_run=True)

    (watched / "c.py").write_text("c = 1\n", encoding="utf-8")
    assert not fingerprint_is_current(stamp, [watched], root=tmp_path, report=report)
    assert not fingerprint_is_current(tmp_path / "absent.json", [watched], root=tmp_path, report=report)


def test_input_fingerprint_ignores_bytecode(tmp_path):
    from equal_path.trust import fingerprint_is_current, write_fingerprint

    watched = tmp_path / "src"
    (watched / "__pycache__").mkdir(parents=True)
    (watched / "a.py").write_text("a = 1\n", encoding="utf-8")
    stamp = tmp_path / "fingerprint.json"
    report = tmp_path / "report.xml"
    report.write_text(JUNIT, encoding="utf-8")
    write_fingerprint(stamp, [watched], root=tmp_path, report=report, full_run=True)
    (watched / "__pycache__" / "a.cpython-313.pyc").write_bytes(b"\x00")
    assert fingerprint_is_current(stamp, [watched], root=tmp_path, report=report)


def test_input_stamp_changes_with_files(tmp_path):
    import os

    from equal_path.trust import input_stamp

    path = tmp_path / "x.yaml"
    path.write_text("a: 1\n", encoding="utf-8")
    before = input_stamp([path, tmp_path / "missing.parquet"])
    os.utime(path, ns=(10**18, 10**18))
    assert input_stamp([path, tmp_path / "missing.parquet"]) != before


def _fingerprint_fixture(tmp_path):
    watched = tmp_path / "src"
    watched.mkdir()
    (watched / "a.py").write_text("a = 1\n", encoding="utf-8")
    report = tmp_path / "report.xml"
    report.write_text(JUNIT, encoding="utf-8")
    return watched, report, tmp_path / "fingerprint.json"


def test_fingerprint_bound_to_report_and_full_run(tmp_path):
    from equal_path.trust import fingerprint_is_current, write_fingerprint

    watched, report, stamp = _fingerprint_fixture(tmp_path)
    write_fingerprint(stamp, [watched], root=tmp_path, report=report, full_run=True)
    assert fingerprint_is_current(stamp, [watched], root=tmp_path, report=report)
    report.write_text(JUNIT.replace('tests="40"', 'tests="41"'), encoding="utf-8")
    assert not fingerprint_is_current(stamp, [watched], root=tmp_path, report=report)


def test_partial_run_fingerprint_is_never_current(tmp_path):
    from equal_path.trust import fingerprint_is_current, write_fingerprint

    watched, report, stamp = _fingerprint_fixture(tmp_path)
    write_fingerprint(stamp, [watched], root=tmp_path, report=report, full_run=False)
    assert not fingerprint_is_current(stamp, [watched], root=tmp_path, report=report)


def test_fingerprint_without_report_is_never_current(tmp_path):
    from equal_path.trust import fingerprint_is_current, write_fingerprint

    watched, report, stamp = _fingerprint_fixture(tmp_path)
    write_fingerprint(stamp, [watched], root=tmp_path, report=tmp_path / "absent.xml", full_run=True)
    assert not fingerprint_is_current(stamp, [watched], root=tmp_path, report=tmp_path / "absent.xml")


@pytest.mark.parametrize("junk", [".DS_Store", "a.py.swp", "a.py~", ".a.py.swo"])
def test_fingerprint_ignores_os_and_editor_junk(tmp_path, junk):
    from equal_path.trust import fingerprint_is_current, write_fingerprint

    watched, report, stamp = _fingerprint_fixture(tmp_path)
    write_fingerprint(stamp, [watched], root=tmp_path, report=report, full_run=True)
    (watched / junk).write_bytes(b"junk")
    assert fingerprint_is_current(stamp, [watched], root=tmp_path, report=report)


def test_unreadable_files_mean_not_current_and_no_summary(tmp_path):
    import os

    from equal_path.trust import fingerprint_is_current, write_fingerprint

    watched, report, stamp = _fingerprint_fixture(tmp_path)
    write_fingerprint(stamp, [watched], root=tmp_path, report=report, full_run=True)
    os.chmod(watched / "a.py", 0)
    os.chmod(report, 0)
    try:
        assert not fingerprint_is_current(stamp, [watched], root=tmp_path, report=report)
        assert read_test_summary(report) is None
    finally:
        os.chmod(watched / "a.py", 0o644)
        os.chmod(report, 0o644)


def test_raw_and_processed_data_are_watched():
    from equal_path.paths import DATA_DIR, OBSERVATIONS_FILE, RAW_GEO_DIR, STALENESS_WATCHED

    for path in (RAW_GEO_DIR, OBSERVATIONS_FILE, DATA_DIR / "raw" / "screening"):
        assert any(path.is_relative_to(watched) for watched in STALENESS_WATCHED), path


def test_every_app_module_is_watched():
    """An edit to the county page (app/pathway_view.py) must mark the badge stale, not only streamlit_app.py."""
    from equal_path.paths import ROOT, STALENESS_WATCHED

    for path in (ROOT / "app" / "pathway_view.py", ROOT / "app" / "streamlit_app.py", ROOT / "app" / "static" / "topojson"):
        assert any(path.is_relative_to(watched) for watched in STALENESS_WATCHED), path


FULL = dict(from_testpaths=True, keyword="", markexpr="", collectonly=False, xmlpath="evidence/test_report.xml")


@pytest.mark.parametrize(
    "override,expected",
    [
        ({}, True),
        ({"from_testpaths": False}, False),  # explicit paths, e.g. pytest tests/test_lint.py
        ({"keyword": "lint"}, False),
        ({"markexpr": "integration"}, False),
        ({"collectonly": True}, False),
        ({"xmlpath": None}, False),  # -o addopts="" -> no report written
        ({"xmlpath": "elsewhere.xml"}, False),
    ],
)
def test_full_run_detection(tmp_path, override, expected):
    from equal_path.trust import is_full_reported_run

    options = {**FULL, **override}
    if options["xmlpath"]:
        options["xmlpath"] = str(tmp_path / options["xmlpath"])
    report = tmp_path / "evidence/test_report.xml"
    assert is_full_reported_run(report=report, **options) is expected
