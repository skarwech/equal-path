"""Figures. Offline by construction: Plotly geo with our own GeoJSON, no map tiles."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

NEUTRAL = "#c9c8c2"     # unit with nothing highlighted / no data
HIGHLIGHT = "#2a78d6"   # categorical slot 1 (reference palette)
BORDER = "#fcfcfb"      # surface-coloured 2px gap between fills
TEXT_PRIMARY = "#0b0b0b"

# Plotly geo always loads a world topojson, by default from cdn.plot.ly. Point it at
# the copy in app/static/topojson/ (served by Streamlit static serving) so maps work offline.
MAP_CONFIG: dict = {"displayModeBar": False, "scrollZoom": False, "topojsonURL": "/app/static/topojson/"}


HATCH_INK = "#2c2c2a"
OUTLINE = "#0b0b0b"
SYMBOL_STATES = {"leak": "▲", "watch": "◆", "ok": "✓", "unknown": "○"}   # on the map itself: never hue alone


def highlight_codes(units: pd.DataFrame, highlight_area: str | None) -> set[str]:
    if highlight_area is None:
        return set()
    if highlight_area not in set(units["coop_area_fi"]):
        raise ValueError(f"unknown cooperation area {highlight_area!r}")
    return set(units.loc[units["coop_area_fi"] == highlight_area, "code"])


def _lines_trace(segments, name: str, color: str, width: float, geo: str = "geo") -> go.Scattergeo:
    lons, lats = [], []
    for seg_lons, seg_lats in segments:
        lons += [*seg_lons, None]
        lats += [*seg_lats, None]
    return go.Scattergeo(lon=lons, lat=lats, mode="lines", line={"color": color, "width": width}, name=name,
                         hoverinfo="skip", showlegend=False, geo=geo)


def _choropleth(codes, units, geojson, frame, layer_name, hatched, geo: str) -> go.Choropleth:
    from equal_path.map_layers import BLUE_RAMP

    info = units.set_index("code")
    meaning = ("visibility score below 50" if layer_name == "Visibility score"
               else "less than half of this stage is observable")
    note = {c: f"<br>hatched: {meaning}" if c in hatched else "" for c in codes}
    custom = [[info.loc[c, "short_fi"], info.loc[c, "coop_area_fi"], note[c], frame.loc[c, "display"]] for c in codes]
    common = dict(geojson=geojson, featureidkey="properties.code", locations=list(codes), customdata=custom, geo=geo,
                  marker_line_color=BORDER, marker_line_width=1.2,
                  selected={"marker": {"opacity": 1}}, unselected={"marker": {"opacity": 1}},
                  hovertemplate=("<b>%{customdata[0]}</b> · code %{location}<br>" + layer_name
                                 + ": %{customdata[3]}%{customdata[2]}<br>Cooperation area: %{customdata[1]}"
                                 "<extra></extra>"))
    if layer_name == "Visibility score":
        return go.Choropleth(z=[float(frame.loc[c, "value"]) for c in codes], zmin=0, zmax=100,
                             colorscale=[[i / (len(BLUE_RAMP) - 1), c] for i, c in enumerate(BLUE_RAMP)],
                             showscale=geo == "geo", colorbar={"title": {"text": "Visibility"}, "thickness": 12, "len": 0.5,
                                                              "x": 0.02, "y": 0.75}, **common)
    n = len(codes)  # one flat colour per unit, from the status palette
    scale = [step for k, c in enumerate(codes)
             for step in ([k / n, frame.loc[c, "color"]], [(k + 1) / n, frame.loc[c, "color"]])]
    return go.Choropleth(z=[k + 0.5 for k in range(n)], zmin=0, zmax=n, colorscale=scale, showscale=False, **common)


def _overlays(codes, features, frame, hatched, outline, geo: str) -> list[go.Scattergeo]:
    from equal_path.loaders.distance import centroid
    from equal_path.map_layers import HATCH_SPACING, INSET_HATCH_SPACING, INSET_UNITS, hatch_segments

    traces = []
    to_hatch = [c for c in codes if c in hatched]
    if to_hatch:
        spacing = HATCH_SPACING if geo == "geo" else INSET_HATCH_SPACING
        traces.append(_lines_trace([s for c in to_hatch for s in hatch_segments(features[c], spacing)], "hatching",
                                   HATCH_INK, 0.8, geo))
    # the three tiny units are marked in the inset only: on the main map their symbol would sit on a neighbour
    marked = [c for c in codes if frame.loc[c, "value"] in SYMBOL_STATES and (geo == "geo2" or c not in INSET_UNITS)]
    if marked:
        points = [centroid(features[c]) for c in marked]
        traces.append(go.Scattergeo(lat=[p[0] for p in points], lon=[p[1] for p in points], mode="text", geo=geo,
                                    text=[SYMBOL_STATES[frame.loc[c, "value"]] for c in marked], name="symbols",
                                    customdata=marked,
                                    textfont={"color": OUTLINE, "size": 14}, hoverinfo="skip", showlegend=False,
                                    selected={"textfont": {"color": OUTLINE}}, unselected={"textfont": {"color": OUTLINE}}))
    ringed = [c for c in codes if c in outline]
    if ringed:
        rings = [poly[0] for c in sorted(ringed) for poly in
                 ([features[c]["coordinates"]] if features[c]["type"] == "Polygon" else features[c]["coordinates"])]
        traces.append(_lines_trace([([p[0] for p in r], [p[1] for p in r]) for r in rings], "highlight", OUTLINE, 2.5, geo))
    return traces


def _layer_figure(units: pd.DataFrame, geojson: dict, frame: pd.DataFrame, layer_name: str,
                  highlight_area: str | None) -> go.Figure:
    from equal_path.map_layers import INSET_UNITS

    codes = list(units["code"])
    features = {f["properties"]["code"]: f["geometry"] for f in geojson["features"]}
    hatched = {c for c in codes if frame.loc[c, "hatched"]}
    outline = highlight_codes(units, highlight_area)
    inset = [c for c in codes if c in INSET_UNITS]
    figure = go.Figure(_choropleth(codes, units, geojson, frame, layer_name, hatched, "geo"))
    figure.add_trace(_choropleth(inset, units, geojson, frame, layer_name, hatched, "geo2"))
    for trace in _overlays(codes, features, frame, hatched, outline, "geo") + _overlays(inset, features, frame, hatched,
                                                                                      outline, "geo2"):
        figure.add_trace(trace)
    figure.update_layout(  # the inset sits in the sea south-east of the coast, clear of every polygon
        geo={"domain": {"x": [0.0, 1.0], "y": [0.0, 1.0]}},
        geo2={"domain": {"x": [0.70, 1.0], "y": [0.0, 0.24]}},
        annotations=[{"text": "Helsinki area (zoom)", "x": 0.85, "y": 0.25, "xref": "paper", "yref": "paper",
                      "showarrow": False, "font": {"size": 11, "color": TEXT_PRIMARY}}],
        shapes=[{"type": "rect", "xref": "paper", "yref": "paper", "x0": 0.70, "x1": 1.0, "y0": 0.0, "y1": 0.24,
                 "line": {"color": "#c9c8c2", "width": 1}}],
    )
    return figure


def unit_map_figure(units: pd.DataFrame, geojson: dict, highlight_area: str | None = None,
                    layer: pd.DataFrame | None = None, layer_name: str = "") -> go.Figure:
    """Map of the 22 units. Without a layer: optionally highlight one cooperation area (Stage 1 view).
    With a layer (map_layers.layer_frame): fill by layer, hatch low-visibility units, mark Leak/Watch
    with a symbol, and outline the highlighted cooperation area (so the fill stays the layer's).
    """
    if layer is not None:
        figure = _layer_figure(units, geojson, layer, layer_name, highlight_area)
        return _layout(figure)
    areas = set(units["coop_area_fi"])
    if highlight_area is not None and highlight_area not in areas:
        raise ValueError(f"unknown cooperation area {highlight_area!r}")
    z = [1 if area == highlight_area else 0 for area in units["coop_area_fi"]]
    loaded = units["indicators_loaded"] if "indicators_loaded" in units else pd.Series(0, index=units.index)
    hover = units[["short_fi", "coop_area_fi", "name_en"]].assign(indicators_loaded=loaded)
    trace = go.Choropleth(
        geojson=geojson,
        featureidkey="properties.code",
        locations=list(units["code"]),
        z=z,
        zmin=0,
        zmax=1,
        colorscale=[[0.0, NEUTRAL], [0.5, NEUTRAL], [0.5, HIGHLIGHT], [1.0, HIGHLIGHT]],
        showscale=False,
        marker_line_color=BORDER,
        marker_line_width=1.2,
        customdata=hover.to_numpy(),
        hovertemplate=(
            "<b>%{customdata[0]}</b> · code %{location}<br>"
            "%{customdata[2]}<br>"
            "Cooperation area: %{customdata[1]}<br>"
            "Indicators loaded: %{customdata[3]}<extra></extra>"
        ),
    )
    return _layout(go.Figure(trace))


def _layout(figure: go.Figure) -> go.Figure:
    figure.update_geos(fitbounds="locations", visible=False, projection_type="mercator")  # every geo, inset included
    figure.update_layout(
        height=700,
        dragmode=False,  # no pan/zoom; note: Streamlit switches to pan when map clicks are on (see Reset map view)
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        geo_bgcolor="rgba(0,0,0,0)",
        hoverlabel={"bgcolor": "white", "font_color": TEXT_PRIMARY},
    )
    return figure
