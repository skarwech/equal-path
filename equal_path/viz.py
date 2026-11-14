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


def unit_map_figure(units: pd.DataFrame, geojson: dict, highlight_area: str | None = None) -> go.Figure:
    """Map of the 22 units; optionally highlight one cooperation area.

    Five areas exceed the safe categorical count for a choropleth, so identity is
    shown one area at a time (highlight vs neutral) and in the table beside it.
    """
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
    figure = go.Figure(trace)
    figure.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
    figure.update_layout(
        height=700,
        dragmode=False,  # no accidental pan/zoom during a live demo
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        geo_bgcolor="rgba(0,0,0,0)",
        hoverlabel={"bgcolor": "white", "font_color": TEXT_PRIMARY},
    )
    return figure
