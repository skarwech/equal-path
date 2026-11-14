"""The 22-unit geography (21 wellbeing counties + Helsinki) and its 5 cooperation areas."""

import pandas as pd
import pytest

from equal_path.geography import (
    EXCLUDED_CODES,
    UNIT_CODES,
    load_unit_geojson,
    load_units,
    ring_is_clockwise,
)
from equal_path.sources import source_ids

EXPECTED_CODES = {f"{i:02d}" for i in range(1, 22)} | {"90"}


@pytest.fixture(scope="module")
def units():
    return load_units()


@pytest.fixture(scope="module")
def geojson():
    return load_unit_geojson()


def test_exactly_22_units(units):
    assert len(units) == 22
    assert units["code"].is_unique
    assert set(units["code"]) == EXPECTED_CODES == set(UNIT_CODES)


def test_aland_excluded_explicitly(units, geojson):
    assert "91" in EXCLUDED_CODES
    assert "91" not in set(units["code"])
    assert "91" not in {f["properties"]["code"] for f in geojson["features"]}


def test_five_cooperation_areas_every_unit_assigned(units):
    assert (units["coop_area_code"] != "").all()
    assert set(units["coop_area_code"]) == {"1", "2", "3", "4", "5"}  # "6" (Åland) absent
    assert units["coop_area_code"].value_counts().to_dict() == {"1": 8, "2": 4, "3": 3, "4": 3, "5": 4}


# Pinned independently of the build code: (code, short Finnish name, official English
# name, cooperation area). Source: Statistics Finland classifications 2026.
PINNED = [
    ("01", "Itä-Uusimaa", "East Uusimaa wellbeing services county", "Etelä-Suomi"),
    ("02", "Keski-Uusimaa", "Central Uusimaa wellbeing services county", "Etelä-Suomi"),
    ("03", "Länsi-Uusimaa", "West Uusimaa wellbeing services county", "Etelä-Suomi"),
    ("04", "Vantaa-Kerava", "Vantaa and Kerava wellbeing services county", "Etelä-Suomi"),
    ("05", "Varsinais-Suomi", "Southwest Finland wellbeing services county", "Länsi-Suomi"),
    ("06", "Satakunta", "Satakunta wellbeing services county", "Länsi-Suomi"),
    ("07", "Kanta-Häme", "Kanta-Häme wellbeing services county", "Sisä-Suomi"),
    ("08", "Pirkanmaa", "Pirkanmaa wellbeing services county", "Sisä-Suomi"),
    ("09", "Päijät-Häme", "Päijät-Häme wellbeing services county", "Etelä-Suomi"),
    ("10", "Kymenlaakso", "Kymenlaakso wellbeing services county", "Etelä-Suomi"),
    ("11", "Etelä-Karjala", "South Karelia wellbeing services county", "Etelä-Suomi"),
    ("12", "Etelä-Savo", "South Savo wellbeing services county", "Itä-Suomi"),
    ("13", "Pohjois-Savo", "North Savo wellbeing services county", "Itä-Suomi"),
    ("14", "Pohjois-Karjala", "North Karelia wellbeing services county", "Itä-Suomi"),
    ("15", "Keski-Suomi", "Central Finland wellbeing services county", "Itä-Suomi"),
    ("16", "Etelä-Pohjanmaa", "South Ostrobothnia wellbeing services county", "Sisä-Suomi"),
    ("17", "Pohjanmaa", "Ostrobothnia wellbeing services county", "Länsi-Suomi"),
    ("18", "Keski-Pohjanmaa", "Central Ostrobothnia wellbeing services county", "Pohjois-Suomi"),
    ("19", "Pohjois-Pohjanmaa", "North Ostrobothnia wellbeing services county", "Pohjois-Suomi"),
    ("20", "Kainuu", "Kainuu wellbeing services county", "Pohjois-Suomi"),
    ("21", "Lappi", "Lapland wellbeing services county", "Pohjois-Suomi"),
    ("90", "Helsinki", "City of Helsinki", "Etelä-Suomi"),
]


def test_pinned_table_covers_all_units():
    assert {row[0] for row in PINNED} == EXPECTED_CODES and len(PINNED) == 22


@pytest.mark.parametrize("code,short,name_en,area", PINNED)
def test_unit_row_matches_pinned(units, code, short, name_en, area):
    row = units.set_index("code").loc[code]
    assert (row["short_fi"], row["name_en"], row["coop_area_fi"]) == (short, name_en, area)
    assert row["unit_type"] == ("city" if code == "90" else "wellbeing_services_county")
    assert row["name_sv"].endswith("välfärdsområde") or row["name_sv"] == "Helsingfors stad"


@pytest.mark.parametrize("code,name_sv", [("08", "Birkalands välfärdsområde"), ("21", "Lapplands välfärdsområde"), ("90", "Helsingfors stad")])
def test_swedish_names_spot_check(units, code, name_sv):
    assert units.set_index("code").loc[code, "name_sv"] == name_sv


def test_unit_master_contract(tmp_path, units):
    from equal_path.geography import UNIT_COLUMNS

    assert tuple(units.columns) == UNIT_COLUMNS
    broken = tmp_path / "units.csv"
    units.drop(columns=["coop_area_fi"]).to_csv(broken, index=False)
    with pytest.raises(ValueError, match="coop_area_fi"):
        load_units(broken)
    units.iloc[:21].to_csv(broken, index=False)
    with pytest.raises(ValueError, match="22"):
        load_units(broken)
    units.assign(municipality_count="many").to_csv(broken, index=False)
    with pytest.raises(ValueError, match="municipality_count"):
        load_units(broken)
    pd.concat([units, units.iloc[[0]]]).to_csv(broken, index=False)  # 23 rows, same code set
    with pytest.raises(ValueError, match="22"):
        load_units(broken)
    units.assign(code=units["code"].replace({"01": "91"})).to_csv(broken, index=False)  # 22 rows, wrong set
    with pytest.raises(ValueError, match="22"):
        load_units(broken)
    units.assign(municipality_count=units["municipality_count"].str.cat(["abc"] * 22)).to_csv(broken, index=False)
    with pytest.raises(ValueError, match="municipality_count"):
        load_units(broken)
    broken.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="units.csv"):
        load_units(broken)


def test_unit_geojson_contract(tmp_path, geojson):
    import copy
    import json

    broken = tmp_path / "units.geojson"
    cases = {
        "FeatureCollection": {"type": "Feature"},
        "22": {**geojson, "features": geojson["features"][:21]},
        "duplicate": {**geojson, "features": geojson["features"][:21] + geojson["features"][:1]},
    }
    empty = copy.deepcopy(geojson)
    empty["features"][3]["geometry"]["coordinates"] = []
    cases["empty geometry"] = empty
    for message, payload in cases.items():
        broken.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            load_unit_geojson(broken)
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="units.geojson"):
        load_unit_geojson(broken)


def test_geojson_matches_unit_master(units, geojson):
    feature_codes = [f["properties"]["code"] for f in geojson["features"]]
    assert len(feature_codes) == 22
    assert set(feature_codes) == set(units["code"])


def _rings(geometry):
    if geometry["type"] == "Polygon":
        yield from enumerate(geometry["coordinates"])
    elif geometry["type"] == "MultiPolygon":
        for polygon in geometry["coordinates"]:
            yield from enumerate(polygon)
    else:
        raise AssertionError(f"unexpected geometry {geometry['type']}")


def test_coordinates_inside_finland(geojson):
    for feature in geojson["features"]:
        for _, ring in _rings(feature["geometry"]):
            for lon, lat in ring:
                assert 19.0 <= lon <= 32.0, (feature["properties"]["code"], lon)
                assert 59.0 <= lat <= 70.5, (feature["properties"]["code"], lat)


def test_exterior_rings_clockwise_for_d3(geojson):
    """d3-geo (Plotly geo) needs clockwise exteriors or it fills the globe."""
    for feature in geojson["features"]:
        for index, ring in _rings(feature["geometry"]):
            assert ring_is_clockwise(ring) == (index == 0), feature["properties"]["code"]


def test_ring_orientation_helper():
    square_ccw = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
    assert not ring_is_clockwise(square_ccw)
    assert ring_is_clockwise(list(reversed(square_ccw)))


def test_every_unit_row_cites_a_registered_source(units, geojson):
    known = source_ids()
    assert (units["source_id"] != "").all() and set(units["source_id"]) <= known
    assert (units["coop_area_source_id"] != "").all() and set(units["coop_area_source_id"]) <= known
    assert {f["properties"]["source_id"] for f in geojson["features"]} <= known


def test_rings_are_closed(geojson):
    for feature in geojson["features"]:
        for _, ring in _rings(feature["geometry"]):
            assert len(ring) >= 4 and ring[0] == ring[-1], feature["properties"]["code"]
