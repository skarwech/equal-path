"""Build data/reference/units.csv and units.geojson from the raw downloads (offline)."""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from equal_path.geography_build import (  # noqa: E402
    build_unit_geojson,
    build_unit_table,
    municipality_map,
    unit_to_coop_area,
)
from equal_path.paths import RAW_GEO_DIR, UNITS_FILE, UNITS_GEOJSON  # noqa: E402

log = logging.getLogger("build_units")


def _read(name: str):
    with (RAW_GEO_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    try:
        kunta_hva = municipality_map(_read("kunta_hva_2026.json"))
        kunta_yta = municipality_map(_read("kunta_yta_2026.json"))
        boundaries = _read("hva_boundaries_4500k_2026.geojson")
        units = build_unit_table(
            classification=_read("hva_classification_2026.json"),
            coop_classification=_read("yta_classification_2026.json"),
            unit_coop=unit_to_coop_area(kunta_hva, kunta_yta),
            boundaries=boundaries,
            municipality_counts=dict(Counter(kunta_hva.values())),
        )
        geojson = build_unit_geojson(boundaries, units)
    except (OSError, KeyError, ValueError) as exc:
        log.error("build failed: %s", exc)
        return 1
    UNITS_FILE.parent.mkdir(parents=True, exist_ok=True)
    units.to_csv(UNITS_FILE, index=False)
    UNITS_GEOJSON.write_text(json.dumps(geojson, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log.info("wrote %d units and %d features", len(units), len(geojson["features"]))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(main())
