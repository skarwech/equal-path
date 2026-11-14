"""THL Sotkanet REST indicators (CC BY 4.0). value is a percentage unless noted."""

from __future__ import annotations

import json

from equal_path.loaders._util import obs, raw
from equal_path.spine import make_observations

SOURCE = "S_SOTKANET"
# file -> (indicator_id, scale, absValue is the numerator)
FILES = {
    "i3869_hpv_girls.json": ("hpv_vaccination_coverage", 0.01, False),
    "i171_aged_75_plus.json": ("cov_share_aged_75_plus", 0.01, False),  # absValue has no published denominator
    "i3195_tertiary_15_plus.json": ("cov_education", 0.01, False),
    "i6411_pc_wait_over_7d.json": ("primary_care_access", 0.01, False),
}


def _regions() -> dict[int, tuple[str, str]]:
    regions = json.loads(raw("sotkanet", "regions.json").read_text(encoding="utf-8"))
    mapping = {}
    for region in regions:
        category, code = region.get("category"), str(region.get("code"))
        if category == "HYVINVOINTIALUE":
            mapping[region["id"]] = ("excluded_unit", "91") if code == "91" else ("unit", code.zfill(2))
        elif category == "YTA" and code in {"1", "2", "3", "4", "5"}:
            mapping[region["id"]] = ("cooperation_area", f"YTA{code}")
        elif category == "MAA":
            mapping[region["id"]] = ("national", "FI")
    return mapping


def load():
    regions = _regions()
    rows = []
    for file, (indicator, scale, abs_is_numerator) in FILES.items():
        for item in json.loads(raw("sotkanet", file).read_text(encoding="utf-8")):
            if item["region"] not in regions or item.get("gender") != "total":
                continue
            geo, code = regions[item["region"]]
            value = item.get("value")
            rows.append(obs(geo, code, indicator, item["year"], None if value is None else round(value * scale, 6),
                            SOURCE, f"sotkanet indicator {item['indicator']} region {item['region']} {item['year']}",
                            numerator=item.get("absValue") if abs_is_numerator else None,
                            quality_flag="" if value is not None else "suppressed"))
    return make_observations(rows)
