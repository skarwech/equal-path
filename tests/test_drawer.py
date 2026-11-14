"""F8 sources drawer: every figure on the county page appears in the drawer with its source.

The coverage test reads numbers off the rendered page (Streamlit AppTest), not off the drawer
builder, so it cannot pass by construction. Provenance tests recompute each row's source,
locator or derivation from the store and catalog independently of drawer.py.
"""

import re
import statistics
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from equal_path.drawer import DRAWER_COLUMNS, SPEC, county_figures, numbers_in

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
IDENTIFIER_COLUMNS = {"Twin", "Code", "Rule"}   # unit codes and rule ids are identifiers, not figures
CODES = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11",
         "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "90"]
PAGE_ELEMENT_TYPES = {"tab", "markdown", "caption", "arrow_data_frame", "selectbox", "expander", "flex_container", "column",
                      "download_button"}   # the button carries a label only, no figures


@pytest.fixture(scope="module")
def inputs():
    from equal_path.config import load_indicator_catalog, load_thresholds
    from equal_path.glidepath import calibration, run_glidepaths
    from equal_path.observations import load_observations
    from equal_path.pathway import run_pathway

    store = load_observations()
    return dict(result=run_pathway(store), store=store, catalog={i.id: i for i in load_indicator_catalog()},
                glidepaths=run_glidepaths(store), calib=calibration(store), thresholds=load_thresholds())


@pytest.fixture(scope="module")
def actions(inputs):
    from equal_path.actions import run_actions

    return run_actions(inputs["store"], inputs["result"])


@pytest.fixture(scope="module")
def drawers(inputs):
    return {code: county_figures(code=code, **inputs) for code in CODES}


def test_numbers_in_parses_signs_ranges_and_periods():
    assert numbers_in("−5.6 and 78.7–80.8 in 2019-2023, 25/44 (57%)") == {-5.6, 78.7, 80.8, 2019.0, 2023.0, 25.0, 44.0, 57.0}
    assert numbers_in("not published") == set()


def test_every_row_cites_a_registered_source(drawers):
    from equal_path.sources import load_sources

    registered = set(load_sources().source_id)
    for frame in drawers.values():
        assert list(frame.columns) == list(DRAWER_COLUMNS)
        for sources in frame["Sources"]:
            ids = [s.strip() for s in sources.split(";") if s.strip()]
            assert ids and set(ids) <= registered, sources


def test_no_row_shows_a_missing_figure(drawers):
    """Review P-3: NaN values must not produce drawer rows ('nan', 'None' or empty)."""
    for frame in drawers.values():
        assert not frame.Shown.isin(["", "nan", "None"]).any()


def _ids(sources: str) -> set[str]:
    return {s.strip() for s in sources.split(";") if s.strip()}


def test_data_rows_cite_their_own_sources_not_the_rule_register(drawers, inputs):
    """Review G-5: only rule constants and confidence rows may cite the team's register; every data row
    cites the sources of exactly the indicators it is computed from."""
    from equal_path.visibility import stage_members

    catalog = inputs["catalog"]
    members = stage_members(catalog)
    for code, frame in drawers.items():
        for section, figure, sources in zip(frame.Section, frame.Figure, frame.Sources):
            if section == "Method" or figure.endswith("· confidence"):
                continue
            assert SPEC not in _ids(sources), (code, figure)
            match = re.match(r"(\w+) · (state|visibility|why grey)$", figure)
            if section == "Funnel" and match:
                expected = {s for m in members[match.group(1).lower()] for s in catalog[m].source_ids}
                assert _ids(sources) == expected, (code, figure)


def test_raw_values_match_the_store_with_locator(drawers, inputs):
    """Fidelity: each indicator value row equals the store value for that unit, period and series."""
    store = inputs["store"]
    for code, frame in drawers.items():
        rows = frame[frame.Figure.str.endswith(" · value")]
        assert len(rows) >= 8
        for figure, shown, period, sources, locator in zip(rows.Figure, rows.Shown, rows.Period, rows.Sources,
                                                          rows["Locator or derivation"]):
            indicator, subgroup = re.match(r"(\S+) \((.+)\) · value", figure).groups()
            hit = store[(store.indicator_id == indicator) & (store.county_id == code) & (store.period == period)
                        & (store.subgroup == subgroup) & (store.geo_level == "unit")]
            assert len(hit) == 1, figure
            assert float(shown) == round(float(hit.value.iloc[0]) * 100, 1)
            assert (sources, locator) == (hit.source_id.iloc[0], hit.locator.iloc[0])


def _national_row(store, catalog, indicator, period, subgroup):
    rows = store[(store.indicator_id == indicator) & (store.geo_level == "national") & (store.period == period)
                 & (store.subgroup == subgroup) & store.value.notna() & store.source_id.isin(catalog[indicator].source_ids)]
    return rows.iloc[0] if len(rows) == 1 else None


def test_derived_indicator_rows_state_how_they_were_made(drawers, inputs):
    """Review P-4/P-7: national rows cite the published row or say 'pooled'; the interval derivation says
    published CI exactly when the unit row has one; the twin median names exactly the twins it used."""
    store, catalog, result, t = inputs["store"], inputs["catalog"], inputs["result"], inputs["thresholds"]
    for code, frame in drawers.items():
        for figure, shown, period, sources, how in zip(frame.Figure, frame.Shown, frame.Period, frame.Sources,
                                                      frame["Locator or derivation"]):
            m = re.match(r"(\S+) \((.+)\) · (national|test interval|twin median)$", figure)
            if not m:
                continue
            indicator, subgroup, kind = m.groups()
            if kind == "national":
                row = _national_row(store, catalog, indicator, period, subgroup)
                expected = (row.source_id, row.locator) if row is not None else (sources, "pooled over all unit rows, weighted by n")
                assert (sources, how) == expected, (code, figure)
            elif kind == "test interval":
                unit = store[(store.indicator_id == indicator) & (store.county_id == code) & (store.period == period)
                             & (store.subgroup == subgroup) & (store.geo_level == "unit")].iloc[0]
                assert how.startswith("published 95 % CI") == pd.notna(unit.ci_low), (code, figure)
            else:
                rows = store[(store.indicator_id == indicator) & (store.period == period) & (store.subgroup == subgroup)
                             & (store.geo_level == "unit") & store.value.notna()].set_index("county_id")
                used = [tw for tw in result.twins[code].twins
                        if tw in rows.index and bool(result.observable.loc[tw, indicator])
                        and (pd.isna(rows.denominator[tw]) or rows.denominator[tw] >= t.min_denominator)]
                assert re.search(r"\(units ([^)]*)\)", how).group(1) == ", ".join(used), (code, figure)
                assert float(shown) == round(statistics.median(rows.value[tw] for tw in used) * 100, 1)


def test_national_stage_recording_coverage_is_all_sites(inputs, drawers):
    """Review P-1: the national figure is the all-sites row (41.9 %), not the first row the store returns."""
    from equal_path.display import national_value

    assert national_value(inputs["store"], "stage_recording_coverage") == pytest.approx(0.419)
    row = drawers["90"].set_index("Figure").loc["National stage-recording coverage"]
    assert row.Shown == "41.9 %" and row["Locator or derivation"].endswith("All sites together")


def test_typical_twin_distance_is_the_median(inputs):
    """Review P-2: 'typical' was the upper-middle of 22 values; it is now the median, as the drawer says."""
    from equal_path.display import typical_twin_distance

    twins = inputs["result"].twins
    assert typical_twin_distance(twins) == statistics.median(t.distances[0] for t in twins.values())


def test_glidepath_rows_cite_the_goal_and_the_latest_year(drawers, inputs):
    """Review P-5/P-11: the 80 % goal cites the national strategy; 'latest' cites that year's row only."""
    store = inputs["store"]
    for code, frame in drawers.items():
        target = frame.set_index("Figure").loc["Glidepath target"]
        assert "S_STRATEGY" in _ids(target.Sources)
        for figure, sources, how in zip(frame.Figure, frame.Sources, frame["Locator or derivation"]):
            if figure.endswith("· needed (pp/yr)"):
                assert "S_STRATEGY" in _ids(sources)
            if figure.endswith("· latest"):
                programme = figure.split(" · ")[0]
                rows = store[(store.indicator_id == f"screening_participation_{programme}") & (store.county_id == code)
                             & (store.geo_level == "unit") & (store.subgroup == "all") & store.value.notna()]
                assert how == rows.sort_values("period").locator.iloc[-1]


def test_leak_rule_row_describes_the_test_actually_used(drawers):
    """Review P-6: leaks were judged on Wilson intervals at the stage's Bonferroni z, not only published CIs."""
    shown = drawers["10"].set_index("Figure").loc["Leak rule"].Shown
    assert "Bonferroni" in shown and "Wilson" in shown


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


def _element_types(node) -> set[str]:
    found = {getattr(node, "type", type(node).__name__)}
    for child in getattr(node, "children", {}).values():
        found |= _element_types(child)
    return found


@pytest.mark.parametrize("code", CODES)
def test_county_page_gates(code, inputs, actions):
    """Spec F8 gates, for 22 of 22 county pages: each funnel stage shows the gap locator's state and its
    confidence level, every grey stage shows its reason, and every displayed figure is in the drawer."""
    from equal_path.confidence import county_confidence, stage_reason
    from equal_path.display import STATE_WORD
    from equal_path.geography import load_units

    labels = {c: f"{c} {name}" for c, name in zip(load_units()["code"], load_units()["short_fi"])}
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["county"] = labels[code]
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    tab = at.tabs[0]
    # only element types the harvest below reads (review G-7): a new type must be added to the harvest first
    assert _element_types(tab) <= PAGE_ELEMENT_TYPES, _element_types(tab) - PAGE_ELEMENT_TYPES

    result, t = inputs["result"], inputs["thresholds"]
    stages, confidence = result.stages.loc[code], county_confidence(result, code, t)
    cards = {str(m.value).split("**")[1].lower(): str(m.value) for m in tab.markdown
             if str(m.value).startswith("**") and "confidence" in str(m.value)}
    assert set(cards) == set(stages.index)
    captions = {str(c.value) for c in tab.caption}
    for stage, state in stages.items():
        assert STATE_WORD[state] in cards[stage], (code, stage, state)
        assert f"confidence **{confidence[stage].level}**" in cards[stage], (code, stage)
        if state == "unknown":
            reason = stage_reason(result, inputs["store"], inputs["catalog"], code, stage, t.min_stage_visibility)
            assert f"○ {stage.capitalize()}: {reason}" in captions, (code, stage)

    # the Action Card on screen shows exactly the PDF's lines (spec F8: sampled text equals on-screen content)
    from equal_path.card import build_card, card_text_lines

    shown = [str(e.value) for e in (*tab.markdown, *tab.caption)]
    card = build_card(code, actions, __import__("datetime").date.today().isoformat())
    for line in card_text_lines(card):
        assert any(line in text for text in shown), (code, line)

    page = _page_numbers(at)
    assert len(page) >= 50 and len(tab.dataframe) == 5  # non-trivial harvest: 3 page tables + rules + the drawer
    missing = page - _drawer_numbers(at)
    assert not missing, sorted(missing)


def test_twin_median_derivation_excludes_twins_that_did_not_count():
    """On real data every twin median happens to use all 3 twins, so pin the exclusions synthetically:
    a twin with n < 30 and a twin F1 does not count must not be named."""
    from types import SimpleNamespace

    from equal_path.drawer import _twins_used

    store = pd.DataFrame([
        {"indicator_id": "x", "period": "2024", "subgroup": "all", "geo_level": "unit", "county_id": c, "value": v,
         "denominator": n} for c, v, n in (("01", 0.5, 100), ("02", 0.6, 12), ("03", 0.7, 100), ("04", 0.8, 100))])
    result = SimpleNamespace(twins={"01": SimpleNamespace(twins=("02", "03", "04"))},
                             observable=pd.DataFrame({"x": [True, True, True, False]}, index=["01", "02", "03", "04"]))
    used, with_n = _twins_used("01", result, store, "x", "2024", "all", 30)
    assert used == ["03"] and with_n
