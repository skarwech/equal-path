"""Turn raw Statistics Finland downloads into the 22-unit master and display GeoJSON.

Pure functions (inputs in, new objects out); scripts/build_units.py does the I/O.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Iterable

import pandas as pd

from equal_path.geography import (
    COOP_AREA_SHORT_NAMES,
    EXCLUDED_CODES,
    UNIT_SHORT_NAMES,
    ring_is_clockwise,
)

UNIT_SOURCE_ID = "S_STATFI_HVA_CLASS_2026"
COOP_SOURCE_ID = "S_STATFI_YTA_CORR_2026"
BOUNDARY_SOURCE_ID = "S_STATFI_HVA_BOUNDARIES_2026"


def geojson_content_sha256(collection: dict) -> str:
    """Hash of the features only: WFS responses carry a fresh timeStamp on every request."""
    canonical = json.dumps(collection["features"], sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _suffix(local_id: str) -> str:
    return local_id.rsplit("/", 1)[1]


def municipality_map(correspondence: Iterable[dict]) -> dict[str, str]:
    """Correspondence-table rows -> {municipality code: target code}."""
    return {_suffix(row["sourceLocalId"]): _suffix(row["targetLocalId"]) for row in correspondence}


def unit_to_coop_area(kunta_hva: dict[str, str], kunta_yta: dict[str, str]) -> dict[str, str]:
    """Derive each unit's cooperation area; every unit must map to exactly one."""
    areas: dict[str, set[str]] = defaultdict(set)
    for municipality, unit in kunta_hva.items():
        if municipality not in kunta_yta:
            raise ValueError(f"municipality {municipality} missing from cooperation-area key")
        areas[unit].add(kunta_yta[municipality])
    ambiguous = {unit: sorted(found) for unit, found in areas.items() if len(found) != 1}
    if ambiguous:
        raise ValueError(f"units spanning several cooperation areas: {ambiguous}")
    return {unit: next(iter(found)) for unit, found in areas.items()}


def build_unit_table(
    classification: list[dict],
    coop_classification: list[dict],
    unit_coop: dict[str, str],
    boundaries: dict,
    municipality_counts: dict[str, int],
) -> pd.DataFrame:
    """Assemble the 22-row unit master; raises if any code set disagrees."""
    full_fi = {item["code"]: item["classificationItemNames"][0]["name"] for item in classification}
    coop_full = {item["code"]: item["classificationItemNames"][0]["name"] for item in coop_classification}
    _reject_duplicate_codes(boundaries)
    props = {f["properties"]["hyvinvointialue"]: f["properties"] for f in boundaries["features"]}

    expected = set(UNIT_SHORT_NAMES)
    for label, codes in (("classification", full_fi), ("boundaries", props), ("coop key", unit_coop)):
        found = set(codes) - EXCLUDED_CODES
        if found != expected:
            raise ValueError(f"{label} codes differ from expected 22: {sorted(found ^ expected)}")
    if set(COOP_AREA_SHORT_NAMES) != set(coop_full) - {"6"}:
        raise ValueError(f"cooperation areas changed: {sorted(coop_full)}")

    for code, (_, short_en) in UNIT_SHORT_NAMES.items():
        expected_en = "City of Helsinki" if code == "90" else f"{short_en} wellbeing services county"
        if props[code]["name"].strip() != expected_en:
            raise ValueError(f"English name mismatch for {code}: {props[code]['name']!r} != {expected_en!r}")

    rows = [
        {
            "code": code,
            "short_fi": short_fi,
            "short_en": short_en,
            "name_fi": full_fi[code],
            "name_sv": props[code]["namn"].strip(),
            "name_en": props[code]["name"].strip(),
            "unit_type": "city" if code == "90" else "wellbeing_services_county",
            "coop_area_code": unit_coop[code],
            "coop_area_fi": COOP_AREA_SHORT_NAMES[unit_coop[code]],
            "coop_area_full_fi": coop_full[unit_coop[code]],
            "municipality_count": str(municipality_counts.get(code, 0)),
            "source_id": UNIT_SOURCE_ID,
            "coop_area_source_id": COOP_SOURCE_ID,
        }
        for code, (short_fi, short_en) in UNIT_SHORT_NAMES.items()
    ]
    return pd.DataFrame(rows)


def _reject_duplicate_codes(boundaries: dict) -> None:
    codes = [f["properties"]["hyvinvointialue"] for f in boundaries["features"]]
    duplicates = sorted({code for code in codes if codes.count(code) > 1})
    if duplicates:
        raise ValueError(f"duplicate feature codes in boundaries: {duplicates}")


def _orient(ring: list, clockwise: bool) -> list:
    return list(ring) if ring_is_clockwise(ring) == clockwise else list(reversed(ring))


def _orient_polygon(polygon: list) -> list:
    """d3-geo convention: exterior clockwise, holes counter-clockwise."""
    return [_orient(ring, clockwise=(index == 0)) for index, ring in enumerate(polygon)]


def _round_ring(ring: list, digits: int) -> list:
    return [[round(lon, digits), round(lat, digits)] for lon, lat in ring]


def display_geometry(geometry: dict, digits: int = 4) -> dict:
    if geometry["type"] == "Polygon":
        polygons = [geometry["coordinates"]]
    elif geometry["type"] == "MultiPolygon":
        polygons = geometry["coordinates"]
    else:
        raise ValueError(f"unsupported geometry {geometry['type']}")
    oriented = [_orient_polygon([_round_ring(r, digits) for r in poly]) for poly in polygons]
    return {"type": "MultiPolygon", "coordinates": oriented}


def build_unit_geojson(boundaries: dict, units: pd.DataFrame) -> dict:
    """22 features keyed by `code`, Åland dropped, rings oriented for Plotly geo."""
    _reject_duplicate_codes(boundaries)
    lookup = units.set_index("code")
    features = [
        {
            "type": "Feature",
            "id": feature["properties"]["hyvinvointialue"],
            "properties": {
                "code": feature["properties"]["hyvinvointialue"],
                "short_fi": lookup.loc[feature["properties"]["hyvinvointialue"], "short_fi"],
                "coop_area_fi": lookup.loc[feature["properties"]["hyvinvointialue"], "coop_area_fi"],
                "source_id": BOUNDARY_SOURCE_ID,
            },
            "geometry": display_geometry(feature["geometry"]),
        }
        for feature in boundaries["features"]
        if feature["properties"]["hyvinvointialue"] not in EXCLUDED_CODES
    ]
    return {"type": "FeatureCollection", "features": features}
