"""F8 sources drawer: every figure on the county page appears in the drawer with its source.

The coverage test reads numbers off the rendered page (Streamlit AppTest), not off the drawer
builder, so it cannot pass by construction.
"""

import re
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from equal_path.drawer import DRAWER_COLUMNS, county_figures, numbers_in

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
IDENTIFIER_COLUMNS = {"Twin", "Code"}   # unit codes are identifiers, not figures


@pytest.fixture(scope="module")
def inputs():
    from equal_path.config import load_indicator_catalog, load_thresholds
    from equal_path.glidepath import calibration, run_glidepaths
    from equal_path.observations import load_observations
    from equal_path.pathway import run_pathway

    store = load_observations()
    return dict(result=run_pathway(store), store=store, catalog={i.id: i for i in load_indicator_catalog()},
                glidepaths=run_glidepaths(store), calib=calibration(store), thresholds=load_thresholds())


def test_numbers_in_parses_signs_ranges_and_periods():
    assert numbers_in("−5.6 and 78.7–80.8 in 2019-2023, 25/44 (57%)") == {-5.6, 78.7, 80.8, 2019.0, 2023.0, 25.0, 44.0, 57.0}
    assert numbers_in("not published") == set()


def test_every_row_cites_a_registered_source(inputs):
    from equal_path.sources import load_sources

    registered = set(load_sources().source_id)
    for code in ("90", "08", "21"):
        frame = county_figures(code=code, **inputs)
        assert list(frame.columns) == list(DRAWER_COLUMNS)
        for sources in frame["Sources"]:
            ids = [s.strip() for s in sources.split(";") if s.strip()]
            assert ids and set(ids) <= registered, sources


def test_raw_values_match_the_store_with_locator(inputs):
    """Fidelity: each indicator value row equals the store value for that unit, period and series."""
    store = inputs["store"]
    frame = county_figures(code="21", **inputs)
    rows = frame[frame.Figure.str.endswith(" · value")]
    assert len(rows) >= 8
    for figure, shown, period, locator in zip(rows.Figure, rows.Shown, rows.Period, rows["Locator or derivation"]):
        indicator, subgroup = re.match(r"(\S+) \((.+)\) · value", figure).groups()
        hit = store[(store.indicator_id == indicator) & (store.county_id == "21") & (store.period == period)
                    & (store.subgroup == subgroup) & (store.geo_level == "unit")]
        assert len(hit) == 1, figure
        assert float(shown) == round(float(hit.value.iloc[0]) * 100, 1)
        assert locator == hit.locator.iloc[0]


def _page_numbers(at: AppTest) -> set[float]:
    tab = at.tabs[0]  # "County pathway"
    found: set[float] = set()
    for frame in tab.dataframe:
        df: pd.DataFrame = frame.value
        if "Locator or derivation" in df.columns:
            continue  # the drawer itself
        for column in df.columns:
            if column in IDENTIFIER_COLUMNS:
                continue
            for cell in df[column]:
                if isinstance(cell, (int, float)) and not pd.isna(cell):
                    found.add(round(float(cell), 6))
                elif isinstance(cell, str):
                    found |= numbers_in(cell)
    for element in [*tab.markdown, *tab.caption]:
        found |= numbers_in(str(element.value))
    return found


def _drawer_numbers(at: AppTest) -> set[float]:
    drawer = next(d.value for d in at.tabs[0].dataframe if "Locator or derivation" in d.value.columns)
    out: set[float] = set()
    for shown, period in zip(drawer.Shown, drawer.Period):
        out |= numbers_in(str(shown)) | numbers_in(str(period))
    return out


@pytest.mark.parametrize("code", ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11",
                                  "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "90"])
def test_every_displayed_figure_appears_in_the_sources_drawer(code, inputs):
    """Spec F8 gates, for 22 of 22 county pages: every displayed figure is in the drawer, and each funnel
    stage shows the gap locator's state for that county."""
    from equal_path.geography import load_units

    labels = {c: f"{c} {name}" for c, name in zip(load_units()["code"], load_units()["short_fi"])}
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["county"] = labels[code]
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    from equal_path.display import STATE_WORD

    stages = inputs["result"].stages.loc[code]
    cards = {str(m.value).split("**")[1].lower(): str(m.value) for m in at.tabs[0].markdown
             if str(m.value).startswith("**") and "confidence" in str(m.value)}
    assert set(cards) == set(stages.index)
    for stage, state in stages.items():
        assert STATE_WORD[state] in cards[stage], (code, stage, state)
    page = _page_numbers(at)
    assert len(page) >= 50 and len(at.tabs[0].dataframe) == 4  # non-trivial harvest: 3 page tables + the drawer
    missing = page - _drawer_numbers(at)
    assert not missing, sorted(missing)
