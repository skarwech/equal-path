"""Cancer statistics app exports (session snapshots): incidence and deaths by area, 2024."""

from __future__ import annotations

import pandas as pd

from equal_path.loaders._util import obs, raw
from equal_path.names import resolve_area
from equal_path.spine import make_observations, parse_fi_number

SOURCE = "S_CR_APP_2024"
SITES = {
    "Kaikki syövät yhdessä": "all", "Keuhkot, henkitorvi": "site:lung",
    "Rinta": "site:breast", "Paksu- ja peräsuoli": "site:colorectal",
}
# file -> (indicator, required count column)
FILES = {"app_inc_2024_by_area.csv": ("cancer_incidence", "Todettuja syöpiä"),
         "app_mort_2024_by_area.csv": ("cancer_deaths", "Syöpäkuolemia")}


def load():
    rows = []
    for file, (indicator, count_column) in FILES.items():
        frame = pd.read_csv(raw("cr_app", file), sep=";", dtype=str, encoding="utf-8")
        if count_column not in frame.columns:
            raise ValueError(f"{file}: expected column {count_column!r}, found {list(frame.columns)}")
        for _, row in frame.iterrows():
            if row["Syöpätauti"] not in SITES:
                raise ValueError(f"{file}: unexpected site {row['Syöpätauti']!r}")
            geo, code = resolve_area(row["Alue"])
            locator = f"{file} > {row['Alue']} > {row['Syöpätauti']} > {count_column}"
            rows.append(obs(geo, code, indicator, "2024", parse_fi_number(row[count_column]), SOURCE, locator,
                            SITES[row["Syöpätauti"]]))
    return make_observations(rows)
