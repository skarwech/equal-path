"""Distance to the nearest university hospital (F3 structural covariate), DERIVED.

Per municipality: straight-line (great-circle) km from its area centroid to the nearest of the
five university hospitals; per unit: the population-weighted mean over its municipalities.
A proxy for access, not travel time. Inputs: Wikidata hospital locations, Statistics Finland
municipality boundaries, municipality populations (StatFin 11ra 2025) and the
municipality -> wellbeing services county key.
"""

from __future__ import annotations

import itertools
import json
import math

import pandas as pd

from equal_path.geography import EXCLUDED_CODES
from equal_path.geography_build import municipality_map
from equal_path.loaders._util import obs, raw
from equal_path.paths import RAW_GEO_DIR
from equal_path.spine import make_observations

SOURCE = "S_WIKIDATA_UNIV_HOSPITALS"
HOSPITAL_FILES = {
    "HUS Helsinki": "hus_helsinki_Q246315.json", "TYKS Turku": "tyks_turku_Q3736764.json",
    "TAYS Tampere": "tays_tampere_Q11896324.json", "KYS Kuopio": "kys_kuopio_Q11873596.json",
    "OYS Oulu": "oys_oulu_Q3737020.json",
}
EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def hospitals() -> dict[str, tuple[float, float]]:
    out = {}
    for name, file in HOSPITAL_FILES.items():
        entity = next(iter(json.loads(raw("hospitals", file).read_text(encoding="utf-8"))["entities"].values()))
        coord = entity["claims"]["P625"][0]["mainsnak"]["datavalue"]["value"]
        out[name] = (float(coord["latitude"]), float(coord["longitude"]))
    return out


def centroid(geometry: dict) -> tuple[float, float]:
    """Area-weighted planar centroid of the exterior rings, in lon/lat degrees.

    No cos(latitude) factor is applied: scaling longitude uniformly does not move a planar
    centroid, so it would have no effect (review D-1). The Step 4 review recomputed all 22 county
    distances from sinusoidal equal-area centroids (holes subtracted) and found every one within
    0.3 km of these, so the planar approximation is adequate at municipality scale.
    """
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    rings = [poly[0] for poly in polygons]  # exteriors (one enclave hole in Espoo; negligible)
    total_area = cx = cy = 0.0
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
            cross = x1 * y2 - x2 * y1
            total_area += cross
            cx += (x1 + x2) * cross
            cy += (y1 + y2) * cross
    total_area /= 2
    return cy / (6 * total_area), cx / (6 * total_area)


def _populations() -> dict[str, float]:
    data = json.loads(raw("municipalities", "11ra_municipality_population_2025.json").read_text(encoding="utf-8"))
    dims = data["id"]
    codes = [sorted(data["dimension"][d]["category"]["index"].items(), key=lambda kv: kv[1]) for d in dims]
    out = {}
    for position, combo in enumerate(itertools.product(*[[c for c, _ in dim] for dim in codes])):
        area = combo[dims.index("alue_23_20260101")]
        out[area.removeprefix("KU")] = data["value"][position]
    return out


def municipalities() -> pd.DataFrame:
    """One row per mainland municipality: code, unit, population, centroid, nearest hospital, km."""
    key = municipality_map(json.loads((RAW_GEO_DIR / "kunta_hva_2026.json").read_text(encoding="utf-8")))
    population = _populations()
    sites = hospitals()
    boundaries = json.loads(raw("municipalities", "kunta_boundaries_4500k_2026.geojson").read_text(encoding="utf-8"))
    rows = []
    for feature in boundaries["features"]:
        code = feature["properties"]["kunta"]
        unit = key.get(code)
        if unit is None:
            raise ValueError(f"municipality {code} missing from the county key")
        if unit in EXCLUDED_CODES:
            continue
        lat, lon = centroid(feature["geometry"])
        nearest, km = min(((name, haversine_km(lat, lon, *site)) for name, site in sites.items()), key=lambda x: x[1])
        rows.append({"municipality": code, "unit": unit, "population": population[code], "lat": lat, "lon": lon,
                     "nearest": nearest, "km": km})
    frame = pd.DataFrame(rows)
    if frame.municipality.duplicated().any():
        raise ValueError("duplicate municipality features")
    return frame


def load():
    frame = municipalities()
    rows = []
    for unit, part in frame.groupby("unit"):
        weighted = (part.km * part.population).sum() / part.population.sum()
        rows.append(obs("unit", unit, "cov_distance_university_hospital_km", "2025", round(float(weighted), 1), SOURCE,
                        "population-weighted mean of municipality-centroid distances to the nearest university hospital",
                        quality_flag="derived"))
    return make_observations(rows)
