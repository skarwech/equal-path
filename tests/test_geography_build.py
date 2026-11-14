"""The unit master is reproducible from the raw Statistics Finland files and fails loudly."""

import json
from collections import Counter

import pandas as pd
import pytest

from equal_path.geography import load_unit_geojson, load_units
from equal_path.geography_build import (
    build_unit_geojson,
    build_unit_table,
    display_geometry,
    municipality_map,
    unit_to_coop_area,
)
from equal_path.paths import RAW_GEO_DIR


def _raw(name):
    return json.loads((RAW_GEO_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def raw():
    kunta_hva = municipality_map(_raw("kunta_hva_2026.json"))
    kunta_yta = municipality_map(_raw("kunta_yta_2026.json"))
    return {
        "kunta_hva": kunta_hva,
        "kunta_yta": kunta_yta,
        "classification": _raw("hva_classification_2026.json"),
        "coop_classification": _raw("yta_classification_2026.json"),
        "boundaries": _raw("hva_boundaries_4500k_2026.geojson"),
    }


def _build(raw, **overrides):
    args = {
        "classification": raw["classification"],
        "coop_classification": raw["coop_classification"],
        "unit_coop": unit_to_coop_area(raw["kunta_hva"], raw["kunta_yta"]),
        "boundaries": raw["boundaries"],
        "municipality_counts": dict(Counter(raw["kunta_hva"].values())),
    }
    return build_unit_table(**{**args, **overrides})


def test_rebuild_matches_saved_units(raw):
    pd.testing.assert_frame_equal(_build(raw), load_units())


def test_rebuild_matches_saved_geojson(raw):
    assert build_unit_geojson(raw["boundaries"], _build(raw)) == load_unit_geojson()


def test_municipalities_sum_to_mainland_total(raw):
    units = _build(raw)
    aland = sum(1 for unit in raw["kunta_hva"].values() if unit == "91")
    assert units["municipality_count"].astype(int).sum() == len(raw["kunta_hva"]) - aland


def test_unit_spanning_two_areas_is_rejected():
    with pytest.raises(ValueError, match="several cooperation areas"):
        unit_to_coop_area({"001": "08", "002": "08"}, {"001": "3", "002": "4"})


def test_municipality_missing_from_area_key_is_rejected():
    with pytest.raises(ValueError, match="missing"):
        unit_to_coop_area({"001": "08"}, {})


def test_missing_unit_in_boundaries_is_rejected(raw):
    trimmed = {**raw["boundaries"], "features": raw["boundaries"]["features"][1:]}
    with pytest.raises(ValueError, match="boundaries"):
        _build(raw, boundaries=trimmed)


def test_changed_cooperation_areas_are_rejected(raw):
    with pytest.raises(ValueError, match="cooperation areas changed"):
        _build(raw, coop_classification=raw["coop_classification"][:3])


def test_unsupported_geometry_is_rejected():
    with pytest.raises(ValueError, match="unsupported"):
        display_geometry({"type": "Point", "coordinates": [25.0, 62.0]})


def test_polygon_with_hole_is_oriented_for_d3():
    """Real data has no holes, so exercise the hole branch with a synthetic ring pair."""
    from equal_path.geography import ring_is_clockwise

    exterior_ccw = [[20.0, 60.0], [22.0, 60.0], [22.0, 62.0], [20.0, 62.0], [20.0, 60.0]]
    hole_cw = [[20.5, 60.5], [20.5, 61.5], [21.5, 61.5], [21.5, 60.5], [20.5, 60.5]]
    out = display_geometry({"type": "Polygon", "coordinates": [exterior_ccw, hole_cw]})
    exterior, hole = out["coordinates"][0]
    assert ring_is_clockwise(exterior) and not ring_is_clockwise(hole)
    assert exterior[0] == exterior[-1] and hole[0] == hole[-1]


def test_display_geometry_does_not_mutate_input():
    ring = [[20.0, 60.0], [22.0, 60.0], [22.0, 62.0], [20.0, 62.0], [20.0, 60.0]]
    geometry = {"type": "Polygon", "coordinates": [list(map(list, ring))]}
    display_geometry(geometry)
    assert geometry["coordinates"][0] == ring


def test_duplicate_feature_codes_rejected(raw):
    doubled = {**raw["boundaries"], "features": raw["boundaries"]["features"] + raw["boundaries"]["features"][:1]}
    with pytest.raises(ValueError, match="duplicate"):
        build_unit_geojson(doubled, _build(raw))


def test_english_name_inconsistent_with_lookup_rejected(raw):
    features = [
        {**f, "properties": {**f["properties"], "name": "Somewhere else"}} if f["properties"]["hyvinvointialue"] == "08" else f
        for f in raw["boundaries"]["features"]
    ]
    with pytest.raises(ValueError, match="English name"):
        _build(raw, boundaries={**raw["boundaries"], "features": features})


def test_raw_files_match_manifest():
    import hashlib

    manifest = json.loads((RAW_GEO_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert {entry["file"] for entry in manifest} == {p.name for p in RAW_GEO_DIR.iterdir() if p.name != "manifest.json"}
    for entry in manifest:
        payload = (RAW_GEO_DIR / entry["file"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"], entry["file"]
        assert len(payload) == entry["bytes"]


def test_manifest_records_volatile_free_content_hash_for_boundaries():
    """GeoServer stamps every response with a fresh timeStamp; the content hash ignores it."""
    from equal_path.geography_build import geojson_content_sha256

    manifest = {e["file"]: e for e in json.loads((RAW_GEO_DIR / "manifest.json").read_text(encoding="utf-8"))}
    entry = manifest["hva_boundaries_4500k_2026.geojson"]
    boundaries = _raw("hva_boundaries_4500k_2026.geojson")
    assert entry["content_sha256"] == geojson_content_sha256(boundaries)
    assert geojson_content_sha256({**boundaries, "timeStamp": "2099-01-01T00:00:00Z"}) == entry["content_sha256"]
