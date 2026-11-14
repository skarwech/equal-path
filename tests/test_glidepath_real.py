"""F4 glidepath on the real screening participation series (2020-2024)."""

import pytest

from equal_path.glidepath import calibration, run_glidepaths


@pytest.fixture(scope="module")
def paths():
    return run_glidepaths()


def test_one_glidepath_per_unit_and_programme(paths):
    assert len(paths) == 22 * 3
    assert set(paths.programme) == {"breast", "cervical", "colorectal"}


def test_colorectal_has_too_few_years(paths):
    assert set(paths[paths.programme == "colorectal"].state) == {"insufficient data"}


def test_breast_and_cervical_use_five_years(paths):
    rows = paths[paths.programme.isin(["breast", "cervical"])]
    assert (rows.n_points == 5).all()


def test_pohjois_karjala_cervical_is_not_on_track(paths):
    """Bug detector: 67.8 % in 2024 against an 80 % goal."""
    row = paths[(paths.code == "14") & (paths.programme == "cervical")].iloc[0]
    assert row.latest == pytest.approx(0.678) and row.state != "on track"


def test_calibration_reports_coverage_and_label():
    result = calibration()
    assert result.series == 44
    assert 0.0 <= result.coverage <= 1.0
    assert result.label == ("validated" if 0.65 <= result.coverage <= 0.95 else "indicative")
