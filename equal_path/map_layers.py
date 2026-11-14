"""F8 map layers: what each county shows per layer, low-visibility hatching, and click handling.

Colours follow the reference data-viz palette: the visibility score is a single-hue blue ramp
(light = low, dark = high); stage layers use the fixed status palette, always paired with a
symbol and a word (never colour alone). Hatching marks a stage that is too little observable to
judge (gaps.low_visibility, the same test as F2's Leak gate). It carries meaning, so it is drawn
by default, sparse and at 45 degrees only.
"""

from __future__ import annotations

import math
from typing import Iterable

import pandas as pd

from equal_path.gaps import low_visibility

LAYERS = ("Visibility score", "Detection", "Referral", "Diagnosis", "Treatment")
INSET_UNITS = ("02", "04", "90")   # a few pixels wide at full-map scale, so repeated in a zoomed inset
STATUS_COLOURS = {"leak": "#d03b3b", "watch": "#fab219", "ok": "#0ca30c", "unknown": "#c9c8c2"}
STATUS_LABEL = {"leak": "▲ Leak", "watch": "◆ Watch", "ok": "✓ OK", "unknown": "○ Unknown"}
BLUE_RAMP = ("#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
             "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b")   # steps 100..700
HATCH_SPACING = 0.007   # radians between hatch lines in the Mercator plane (~8 px at the app's map size)
INSET_HATCH_SPACING = 0.0025   # the inset is zoomed, so lines sit closer in map units
DENSIFY_STEP = 0.002    # radians between points along a hatch line (Scattergeo draws great-circle arcs)


def sequential_colour(fraction: float) -> str:
    fraction = min(max(fraction, 0.0), 1.0)
    return BLUE_RAMP[round(fraction * (len(BLUE_RAMP) - 1))]


def layer_frame(result, layer: str, min_stage_visibility: float) -> pd.DataFrame:
    """Index = unit code; columns value, display (exactly as in tooltip and table), color, hatched."""
    if layer not in LAYERS:
        raise ValueError(f"unknown map layer {layer!r}")
    rows = []
    for code in result.stages.index:
        if layer == "Visibility score":
            score = float(result.visibility.loc[code, "score"])
            rows.append((code, score, f"{score:.1f} / 100", sequential_colour(score / 100),
                         low_visibility(score / 100, min_stage_visibility)))
        else:
            stage = layer.lower()
            state, vis = result.stages.loc[code, stage], float(result.visibility.loc[code, stage])
            rows.append((code, state, f"{STATUS_LABEL[state]} · visibility {vis:.0%}", STATUS_COLOURS[state],
                         low_visibility(vis, min_stage_visibility)))
    return pd.DataFrame(rows, columns=["code", "value", "display", "color", "hatched"]).set_index("code")


def layer_table(units: pd.DataFrame, frame: pd.DataFrame, layer: str) -> pd.DataFrame:
    """The table beside the map: same display strings as the tooltips."""
    table = pd.DataFrame({"Code": units["code"].values, "Unit": units["short_fi"].values,
                          "Cooperation area": units["coop_area_fi"].values})
    table[layer] = [frame.loc[code, "display"] for code in units["code"]]
    for source, label in (("municipality_count", "Municipalities"), ("indicators_loaded", "Indicators loaded")):
        if source in units:
            table[label] = units[source].values
    return table


def selected_county(event, valid_codes: Iterable[str]) -> str | None:
    """Unit code clicked on the map (Streamlit plotly selection event), or None."""
    try:
        points = event["selection"]["points"]
    except (KeyError, TypeError):
        return None
    location = points[0].get("location") if points else None
    return location if location in set(valid_codes) else None


def apply_map_pick(state, pick: str | None, labels: dict) -> bool:
    """Open the clicked county; True if it navigated. A Plotly selection persists across reruns, so act
    only when it changes: otherwise the County selector could never move away from the last clicked county."""
    if pick == state.get("_map_pick"):
        return False
    state["_map_pick"] = pick
    if pick is None:
        return False
    state["county"] = labels[pick]
    return True


def handle_map_event(state, event, labels: dict) -> bool:
    """Apply a map click. After a navigating click the chart gets a new key (an empty selection), so the
    next click is always a fresh selection, even on the county already open (review M-1)."""
    navigated = apply_map_pick(state, selected_county(event, set(labels)), labels)
    if navigated:
        state["_map_nonce"] = state.get("_map_nonce", 0) + 1
        state["_map_pick"] = None   # the re-keyed chart starts with nothing selected
    return navigated


# --- hatching geometry -------------------------------------------------------------------------

def _project(lon: float, lat: float) -> tuple[float, float]:
    return math.radians(lon), math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def _unproject(x: float, y: float) -> tuple[float, float]:
    return math.degrees(x), math.degrees(2 * math.atan(math.exp(y)) - math.pi / 2)


def point_in_ring(lon: float, lat: float, ring) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def _polygon_segments(rings, spacing: float) -> list[tuple[list[float], list[float]]]:
    """45-degree lines y - x = c (Mercator plane) clipped to one polygon (exterior + holes, even-odd)."""
    projected = [[_project(lon, lat) for lon, lat in ring] for ring in rings]
    offsets = [y - x for ring in projected for x, y in ring]
    segments = []
    c = math.floor(min(offsets) / spacing) * spacing + spacing / 2
    while c < max(offsets):
        crossings = []
        for ring in projected:
            for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
                f1, f2 = y1 - x1 - c, y2 - x2 - c
                if (f1 > 0) != (f2 > 0):
                    crossings.append(x1 + f1 / (f1 - f2) * (x2 - x1))
        crossings.sort()
        for xa, xb in zip(crossings[0::2], crossings[1::2]):
            steps = max(1, math.ceil((xb - xa) / DENSIFY_STEP))
            points = [_unproject(xa + (xb - xa) * k / steps, xa + (xb - xa) * k / steps + c) for k in range(steps + 1)]
            segments.append(([p[0] for p in points], [p[1] for p in points]))
        c += spacing
    return segments


def hatch_segments(geometry: dict, spacing: float = HATCH_SPACING) -> list[tuple[list[float], list[float]]]:
    """Hatch lines inside a GeoJSON Polygon/MultiPolygon; spacing halves until a small unit gets >= 2 lines."""
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    for _ in range(6):
        segments = [s for rings in polygons for s in _polygon_segments(rings, spacing)]
        if len(segments) >= 2:
            return segments
        spacing /= 2
    return segments
