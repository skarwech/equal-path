"""Statistics Finland StatFin PxWeb (JSON-stat2, CC BY 4.0): population, foreign-language
speakers, density (11ra, 2025) and median equivalent disposable income (14ww, 2024)."""

from __future__ import annotations

import itertools
import json

from equal_path.loaders._util import obs, raw
from equal_path.spine import make_observations

SOURCE = "S_STATFIN"


def _cells(file: str) -> dict[tuple[str, str, str], float | None]:
    data = json.loads(raw("statfin", file).read_text(encoding="utf-8"))
    dims = data["id"]
    labels = [sorted(data["dimension"][d]["category"]["index"].items(), key=lambda kv: kv[1]) for d in dims]
    values = data["value"]
    cells = {}
    for position, combo in enumerate(itertools.product(*[[code for code, _ in dim] for dim in labels])):
        cells[combo] = values[position]
    return cells


def _area(code: str) -> tuple[str, str]:
    if code == "SSS":
        return "national", "FI"
    if code.startswith("YTA"):
        return "cooperation_area", code
    if code.startswith("HVA"):
        return "unit", code[3:]
    raise ValueError(f"unexpected StatFin area code {code!r}")


def load():
    rows = []
    file = "11ra_population_language_density_2025.json"
    cells = _cells(file)
    for area in sorted({key[0] for key in cells}):
        geo, code = _area(area)
        population = cells[(area, "vaerak-vaesto", "2025")]
        foreign = cells[(area, "vaesto_kieli_ulk", "2025")]
        foreign_pct = cells[(area, "vaesto_kieli_ulk_p", "2025")]
        locator = f"StatFin 11ra {area} 2025"
        rows.append(obs(geo, code, "cov_population", "2025", population, SOURCE, f"{locator} vaerak-vaesto"))
        rows.append(obs(geo, code, "cov_foreign_language_share", "2025", None if foreign_pct is None else foreign_pct / 100,
                        SOURCE, f"{locator} vaesto_kieli_ulk_p", numerator=foreign, denominator=population))
        rows.append(obs(geo, code, "cov_population_density", "2025", cells[(area, "vaerak-vaesto_maa_pa", "2025")],
                        SOURCE, f"{locator} vaerak-vaesto_maa_pa"))
    file = "14ww_median_income_2024.json"
    for (area, _, year), value in _cells(file).items():
        geo, code = _area(area)
        rows.append(obs(geo, code, "cov_income", year, value, SOURCE, f"StatFin 14ww {area} {year} tjt-ekvikturaha_med"))
    return make_observations(rows)
