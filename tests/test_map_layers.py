"""F8 map: layers, low-visibility hatching, tooltip = table, and click-through to a county."""

from pathlib import Path

import pytest

from equal_path.gaps import low_visibility
from equal_path.map_layers import (
    INSET_UNITS, LAYERS, STATUS_COLOURS, apply_map_pick, STATUS_LABEL, hatch_segments, layer_frame, layer_table, point_in_ring, selected_county,
    sequential_colour,
)

SQUARE = {"type": "Polygon", "coordinates": [[[25, 62], [26, 62], [26, 63], [25, 63], [25, 62]]]}
WITH_HOLE = {"type": "Polygon", "coordinates": [
    [[25, 62], [27, 62], [27, 63], [25, 63], [25, 62]],
    [[25.8, 62.3], [26.2, 62.3], [26.2, 62.7], [25.8, 62.7], [25.8, 62.3]],
]}


@pytest.fixture(scope="module")
def result():
    from equal_path.pathway import run_pathway

    return run_pathway()


@pytest.fixture(scope="module")
def units():
    from equal_path.geography import load_units

    return load_units()


@pytest.fixture(scope="module")
def geojson():
    from equal_path.geography import load_unit_geojson

    return load_unit_geojson()


LITERAL_LABEL = {"leak": "▲ Leak", "watch": "◆ Watch", "ok": "✓ OK", "unknown": "○ Unknown"}  # not imported (review G-1)
LITERAL_COLOUR = {"leak": "#d03b3b", "watch": "#fab219", "ok": "#0ca30c", "unknown": "#c9c8c2"}
LITERAL_SYMBOL = {"leak": "▲", "watch": "◆", "ok": "✓", "unknown": "○"}
LITERAL_RAMP = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
                "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]


def _expected_display(result, layer, code):
    if layer == "Visibility score":
        return f"{result.visibility.loc[code, 'score']:.1f} / 100"
    stage = layer.lower()
    return f"{LITERAL_LABEL[result.stages.loc[code, stage]]} · visibility {result.visibility.loc[code, stage]:.0%}"


@pytest.mark.parametrize("layer", LAYERS)
def test_layer_values_come_from_the_pathway_result(result, layer):
    frame = layer_frame(result, layer, 0.5)
    assert sorted(frame.index) == sorted(result.stages.index) and len(frame) == 22
    for code in frame.index:
        assert frame.loc[code, "display"] == _expected_display(result, layer, code)
        vis = result.visibility.loc[code, "score"] / 100 if layer == "Visibility score" else result.visibility.loc[code, layer.lower()]
        assert frame.loc[code, "hatched"] == low_visibility(vis, 0.5)


@pytest.mark.parametrize("layer", LAYERS)
def test_tooltip_values_equal_the_table_values(result, units, geojson, layer):
    """Spec F8 gate: tooltip values equal the table values, in an automated comparison, for 22 of 22."""
    from equal_path.viz import unit_map_figure

    frame = layer_frame(result, layer, 0.5)
    figure = unit_map_figure(units, geojson, layer=frame, layer_name=layer)
    trace = figure.data[0]
    tooltip = {code: custom[-1] for code, custom in zip(trace.locations, trace.customdata)}
    table = layer_table(units, frame, layer).set_index("Code")[layer].to_dict()
    assert len(tooltip) == 22 and tooltip == table
    assert all(tooltip[code] == _expected_display(result, layer, code) for code in tooltip)
    assert "%{customdata[3]}" in trace.hovertemplate


def test_stage_layers_use_the_status_palette_with_symbols(result):
    assert STATUS_COLOURS == LITERAL_COLOUR and STATUS_LABEL == LITERAL_LABEL
    frame = layer_frame(result, "Treatment", 0.5)
    for code in frame.index:
        state = result.stages.loc[code, "treatment"]
        assert frame.loc[code, "color"] == LITERAL_COLOUR[state]
        assert frame.loc[code, "display"].startswith(LITERAL_LABEL[state])  # never colour alone


def test_score_layer_is_drawn_on_the_blue_ramp_from_0_to_100(result, units, geojson):
    """Review G-3: the score layer's z, range and colour stops, checked against literals."""
    from equal_path.viz import unit_map_figure

    frame = layer_frame(result, "Visibility score", 0.5)
    for trace in (t for t in unit_map_figure(units, geojson, layer=frame, layer_name="Visibility score").data
                  if t.type == "choropleth"):
        assert (trace.zmin, trace.zmax) == (0, 100)
        assert [c for _, c in trace.colorscale] == LITERAL_RAMP
        assert list(trace.z) == [pytest.approx(result.visibility.loc[c, "score"]) for c in trace.locations]


def _geo_traces(figure, geo):
    return {t.name: t for t in figure.data if t.type == "scattergeo" and (t.geo or "geo") == geo}


@pytest.mark.parametrize("layer", LAYERS)
def test_hatching_and_symbols_are_placed_per_polygon(result, units, geojson, layer):
    """Review G-2: hatching covers exactly the low-visibility units of each map, and every unit carries
    its own state symbol, on the inset for the three tiny units (review M-5) and for every state (M-6)."""
    from equal_path.map_layers import HATCH_SPACING, INSET_HATCH_SPACING
    from equal_path.viz import unit_map_figure

    frame = layer_frame(result, layer, 0.5)
    figure = unit_map_figure(units, geojson, layer=frame, layer_name=layer)
    features = {f["properties"]["code"]: f["geometry"] for f in geojson["features"]}
    for geo, codes, spacing in (("geo", [c for c in frame.index if c not in INSET_UNITS], HATCH_SPACING),
                                ("geo2", list(INSET_UNITS), INSET_HATCH_SPACING)):
        traces = _geo_traces(figure, geo)
        hatched = [c for c in codes if frame.loc[c, "hatched"]] + ([c for c in INSET_UNITS if frame.loc[c, "hatched"]]
                                                                    if geo == "geo" else [])
        expected = sum(len(hatch_segments(features[c], spacing)) for c in hatched)
        assert (traces["hatching"].lon.count(None) if "hatching" in traces else 0) == expected, (layer, geo)
        if layer == "Visibility score":
            assert "symbols" not in traces
            continue
        symbols = dict(zip(traces["symbols"].customdata, traces["symbols"].text))
        assert symbols == {c: LITERAL_SYMBOL[result.stages.loc[c, layer.lower()]] for c in codes}, (layer, geo)


def test_hatch_note_fits_the_layer(units, geojson, result):
    """Review M-7: on the score layer, hatching means 'score below 50', not 'stage below half observable'."""
    from equal_path.viz import unit_map_figure

    for layer, wording in (("Visibility score", "visibility score below 50"), ("Detection", "less than half of this stage")):
        frame = layer_frame(result, layer, 0.5).copy()
        frame.loc["21", "hatched"] = True
        trace = unit_map_figure(units, geojson, layer=frame, layer_name=layer).data[0]
        notes = dict(zip(trace.locations, (c[2] for c in trace.customdata)))
        assert wording in notes["21"] and notes["20"] == ""


@pytest.mark.parametrize("layer", LAYERS)
def test_rendered_map_tooltips_equal_the_rendered_table(layer):
    """Review G-1, the F8 gate end to end: choose the layer in the running app, then compare every
    tooltip in the rendered Plotly spec (main map and inset) with the rendered table, 22 of 22."""
    import json

    from streamlit.testing.v1 import AppTest

    app_file = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
    at = AppTest.from_file(str(app_file), default_timeout=60).run()
    next(sb for sb in at.selectbox if sb.label == "Map layer").select(layer).run()
    assert not at.exception, [e.value for e in at.exception]
    table = next(d.value for d in at.dataframe if {"Code", "Municipalities", layer} <= set(d.value.columns))
    shown = dict(zip(table.Code, table[layer]))
    spec = json.loads(at.get("plotly_chart")[0].proto.spec)
    choropleths = [t for t in spec["data"] if t["type"] == "choropleth"]
    assert [len(t["locations"]) for t in choropleths] == [22, len(INSET_UNITS)]
    for trace in choropleths:
        assert f"{layer}: %{{customdata[3]}}" in trace["hovertemplate"]
        for code, custom in zip(trace["locations"], trace["customdata"]):
            assert custom[3] == shown[code], (layer, code)


def test_score_layer_is_a_single_hue_ramp_light_to_dark():
    low, mid, high = sequential_colour(0.0), sequential_colour(0.5), sequential_colour(1.0)
    assert (low, high) == ("#cde2fb", "#0d366b") and low != mid != high


def test_only_low_visibility_cells_are_hatched_on_real_data(result):
    """Real data: only diagnosis (every county) is below 0.5 among the mapped layers."""
    hatched = {layer: set(layer_frame(result, layer, 0.5).query("hatched").index) for layer in LAYERS}
    assert hatched["Diagnosis"] == set(result.stages.index)
    assert all(not hatched[layer] for layer in LAYERS if layer != "Diagnosis")


def test_hatch_segments_lie_inside_the_polygon():
    segments = hatch_segments(SQUARE, spacing=0.004)
    assert len(segments) >= 5
    ring = SQUARE["coordinates"][0]
    for lons, lats in segments:
        assert len(lons) >= 2
        for lon, lat in zip(lons, lats):
            assert 25 - 1e-9 <= lon <= 26 + 1e-9 and 62 - 1e-9 <= lat <= 63 + 1e-9
        assert point_in_ring((lons[0] + lons[-1]) / 2, (lats[0] + lats[-1]) / 2, ring)  # endpoints sit on the edge


def test_hatching_skips_holes():
    hole = WITH_HOLE["coordinates"][1]
    for lons, lats in hatch_segments(WITH_HOLE, spacing=0.004):
        for lon, lat in zip(lons[1:-1], lats[1:-1]):
            assert not (25.8 + 1e-6 < lon < 26.2 - 1e-6 and 62.3 + 1e-6 < lat < 62.7 - 1e-6), "segment crosses the hole"
    assert point_in_ring(26.0, 62.5, hole)


def test_every_unit_gets_visible_hatching_even_helsinki(geojson):
    """A fixed spacing could miss a small unit entirely; each feature must get at least 2 hatch lines."""
    for feature in geojson["features"]:
        assert len(hatch_segments(feature["geometry"])) >= 2, feature["properties"]["code"]


@pytest.mark.parametrize("code", ["01", "08", "21", "90", "04"])
def test_click_event_selects_the_county(code):
    event = {"selection": {"points": [{"location": code, "point_index": 3}], "point_indices": [3]}}
    assert selected_county(event, {"01", "04", "08", "21", "90"}) == code


@pytest.mark.parametrize("event", [None, {}, {"selection": {"points": []}}, {"selection": {"points": [{"point_index": 1}]}},
                                   {"selection": {"points": [{"location": "99"}]}}])
def test_empty_or_foreign_click_selects_nothing(event):
    assert selected_county(event, {"01", "90"}) is None


def test_map_has_one_clickable_trace_and_overlays_never_take_hover(result, units, geojson):
    from equal_path.viz import unit_map_figure

    figure = unit_map_figure(units, geojson, highlight_area="Sisä-Suomi", layer=layer_frame(result, "Diagnosis", 0.5),
                             layer_name="Diagnosis")
    figure.add_traces(unit_map_figure(units, geojson, layer=layer_frame(result, "Detection", 0.5),
                                      layer_name="Detection").data[2:])  # Detection has Leak/Watch symbols
    clickable = [t for t in figure.data if t.type == "choropleth"]
    assert [len(t.locations) for t in clickable] == [22, len(INSET_UNITS)]
    assert set(clickable[1].locations) == set(INSET_UNITS) and clickable[1].geo == "geo2"
    for trace in clickable:
        assert trace.unselected.marker.opacity == 1  # a click must not dim the others
    overlays = [t for t in figure.data if t.type != "choropleth"]
    for overlay in overlays:
        assert overlay.type == "scattergeo" and overlay.hoverinfo == "skip"
        if overlay.mode == "text":  # a click must not fade the Leak/Watch symbols
            assert overlay.unselected.textfont.color == overlay.textfont.color is not None
    assert any(t.mode == "text" for t in overlays)
    assert {"hatching", "highlight"} <= {t.name for t in overlays}


def test_helsinki_area_inset_makes_the_small_units_clickable(result, units, geojson):
    """At full-map scale Helsinki, Vantaa-Kerava and Keski-Uusimaa are a few pixels wide (a real click test
    landed on a neighbour), so they are repeated in a zoomed inset with the same colours and tooltips."""
    from equal_path.viz import unit_map_figure

    frame = layer_frame(result, "Detection", 0.5)
    figure = unit_map_figure(units, geojson, layer=frame, layer_name="Detection")
    main, inset = [t for t in figure.data if t.type == "choropleth"]
    main_tips = dict(zip(main.locations, (c[-1] for c in main.customdata)))
    for code, custom in zip(inset.locations, inset.customdata):
        assert custom[-1] == main_tips[code]
    assert figure.layout.geo2.domain.x[0] > 0.5  # beside the main map, not on top of it


def test_highlight_outlines_exactly_the_area_units(result, units, geojson):
    from equal_path.viz import highlight_codes

    assert highlight_codes(units, "Sisä-Suomi") == {"07", "08", "16"}


@pytest.mark.parametrize("layer", [layer for layer in LAYERS if layer != "Visibility score"])
def test_each_polygon_is_drawn_in_its_own_layer_colour(result, units, geojson, layer):
    """The per-unit stepwise colour scale must give every polygon exactly the colour in layer_frame (and the table)."""
    from equal_path.viz import unit_map_figure

    frame = layer_frame(result, layer, 0.5)
    for trace in (t for t in unit_map_figure(units, geojson, layer=frame, layer_name=layer).data if t.type == "choropleth"):
        scale = [(float(pos), colour) for pos, colour in trace.colorscale]
        for code, z in zip(trace.locations, trace.z):
            position = (z - trace.zmin) / (trace.zmax - trace.zmin)
            # the segment Plotly interpolates in: consecutive stops with lo < position < hi
            segment = next((a, b) for a, b in zip(scale, scale[1:]) if a[0] < position < b[0])
            assert segment[0][1] == segment[1][1] == frame.loc[code, "color"], (layer, code)


LABELS = {"08": "08 Pirkanmaa", "21": "21 Lappi", "90": "90 Helsinki"}


def test_every_click_opens_its_county_even_the_one_already_open():
    """Review M-1: after a click navigates, the chart is re-keyed (fresh, empty selection), so clicking the
    same polygon again is a new selection rather than a toggle-off that would do nothing."""
    from equal_path.map_layers import handle_map_event

    def click(code):
        return {"selection": {"points": [{"location": code}]}}

    state = {"county": "90 Helsinki"}
    assert handle_map_event(state, click("21"), LABELS) and state["county"] == "21 Lappi" and state["_map_nonce"] == 1
    assert not handle_map_event(state, {"selection": {"points": []}}, LABELS)   # the re-keyed chart starts empty
    state["county"] = "08 Pirkanmaa"
    assert handle_map_event(state, click("21"), LABELS) and state["county"] == "21 Lappi" and state["_map_nonce"] == 2


def test_a_map_click_opens_the_county_and_stale_selections_do_not():
    state = {"county": "90 Helsinki"}
    apply_map_pick(state, "21", LABELS)
    assert state["county"] == "21 Lappi"
    state["county"] = "08 Pirkanmaa"                 # the user then picks another county in the selector
    apply_map_pick(state, "21", LABELS)             # the same plotly selection comes back on every rerun
    assert state["county"] == "08 Pirkanmaa"
    apply_map_pick(state, None, LABELS)             # clicking the selected polygon again deselects it
    assert state["county"] == "08 Pirkanmaa"
    apply_map_pick(state, "21", LABELS)             # a fresh click on the same county opens it again
    assert state["county"] == "21 Lappi"
