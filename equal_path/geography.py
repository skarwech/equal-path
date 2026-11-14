"""The 22 reporting units: 21 wellbeing services counties plus the City of Helsinki.

Åland (code 91) has its own health system and is excluded by design.
Short names are an explicit lookup: Finnish genitives (Lapin, Satakunnan,
Kanta-Hämeen ...) cannot be derived reliably by stripping suffixes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import pandas as pd

from equal_path.paths import UNITS_FILE, UNITS_GEOJSON

EXCLUDED_CODES: frozenset[str] = frozenset({"91"})  # Åland

# code -> (short Finnish name, short English name)
UNIT_SHORT_NAMES: dict[str, tuple[str, str]] = {
    "01": ("Itä-Uusimaa", "East Uusimaa"),
    "02": ("Keski-Uusimaa", "Central Uusimaa"),
    "03": ("Länsi-Uusimaa", "West Uusimaa"),
    "04": ("Vantaa-Kerava", "Vantaa and Kerava"),
    "05": ("Varsinais-Suomi", "Southwest Finland"),
    "06": ("Satakunta", "Satakunta"),
    "07": ("Kanta-Häme", "Kanta-Häme"),
    "08": ("Pirkanmaa", "Pirkanmaa"),
    "09": ("Päijät-Häme", "Päijät-Häme"),
    "10": ("Kymenlaakso", "Kymenlaakso"),
    "11": ("Etelä-Karjala", "South Karelia"),
    "12": ("Etelä-Savo", "South Savo"),
    "13": ("Pohjois-Savo", "North Savo"),
    "14": ("Pohjois-Karjala", "North Karelia"),
    "15": ("Keski-Suomi", "Central Finland"),
    "16": ("Etelä-Pohjanmaa", "South Ostrobothnia"),
    "17": ("Pohjanmaa", "Ostrobothnia"),
    "18": ("Keski-Pohjanmaa", "Central Ostrobothnia"),
    "19": ("Pohjois-Pohjanmaa", "North Ostrobothnia"),
    "20": ("Kainuu", "Kainuu"),
    "21": ("Lappi", "Lapland"),
    "90": ("Helsinki", "Helsinki"),
}
UNIT_CODES: tuple[str, ...] = tuple(UNIT_SHORT_NAMES)

# cooperation-area code -> short Finnish name (yhteistyöalue, 2026 classification)
COOP_AREA_SHORT_NAMES: dict[str, str] = {
    "1": "Etelä-Suomi",
    "2": "Itä-Suomi",
    "3": "Sisä-Suomi",
    "4": "Länsi-Suomi",
    "5": "Pohjois-Suomi",
}


UNIT_COLUMNS: tuple[str, ...] = (
    "code", "short_fi", "short_en", "name_fi", "name_sv", "name_en", "unit_type",
    "coop_area_code", "coop_area_fi", "coop_area_full_fi", "municipality_count",
    "source_id", "coop_area_source_id",
)


def load_units(path: Path = UNITS_FILE) -> pd.DataFrame:
    """Load the unit master built by scripts/build_units.py; fail fast on contract breaks."""
    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read {path.name}: {exc}") from exc
    missing = [column for column in UNIT_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"{path.name}: missing columns {missing}")
    if len(frame) != len(UNIT_CODES) or set(frame["code"]) != set(UNIT_CODES):
        raise ValueError(f"{path.name}: expected the 22 unit codes, found {len(frame)} rows")
    if not frame["municipality_count"].str.fullmatch(r"\d+").all():
        raise ValueError(f"{path.name}: municipality_count must be a whole number in every row")
    return frame[list(UNIT_COLUMNS)]


def load_unit_geojson(path: Path = UNITS_GEOJSON) -> dict:
    """Load the display boundaries; exactly the 22 unit codes, once each, all non-empty."""
    try:
        with path.open(encoding="utf-8") as handle:
            collection = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read {path.name}: {exc}") from exc
    if not isinstance(collection, dict) or collection.get("type") != "FeatureCollection":
        raise ValueError(f"{path.name}: expected a FeatureCollection")
    features = collection.get("features") or []
    codes = [feature.get("properties", {}).get("code") for feature in features]
    if len(codes) != len(set(codes)):
        raise ValueError(f"{path.name}: duplicate feature codes")
    if set(codes) != set(UNIT_CODES):
        raise ValueError(f"{path.name}: expected the 22 unit codes, found {len(set(codes))}")
    empty = [code for code, feature in zip(codes, features) if not (feature.get("geometry") or {}).get("coordinates")]
    if empty:
        raise ValueError(f"{path.name}: empty geometry for {empty}")
    return collection


def signed_area(ring: Sequence[Sequence[float]]) -> float:
    """Shoelace area in lon/lat space; positive means counter-clockwise."""
    total = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        total += x1 * y2 - x2 * y1
    return total / 2.0


def ring_is_clockwise(ring: Sequence[Sequence[float]]) -> bool:
    return signed_area(ring) < 0
