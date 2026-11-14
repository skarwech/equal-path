"""Coverage matrix for the data-spine view: what is observable, per indicator and unit."""

from __future__ import annotations

from typing import Mapping, Sequence

import pandas as pd

VALUE = "●"        # a value at unit level (any period or subgroup)
AREA_ONLY = "◐"    # only a cooperation-area or national value exists
SUPPRESSED = "○"   # unit row exists but the value is suppressed or missing
NONE = "·"         # nothing public loaded: a gap
LEGEND = {
    VALUE: "value for this unit",
    AREA_ONLY: "area or national level only",
    SUPPRESSED: "suppressed or missing",
    NONE: "no public data loaded",
}


def coverage_matrix(store: pd.DataFrame, indicator_ids: Sequence[str], units: Mapping[str, str]) -> pd.DataFrame:
    """Rows = catalog indicators (in catalog order), columns = unit names, cells = symbols."""
    unit_rows = store[store.geo_level == "unit"]
    with_value = set(zip(unit_rows.loc[unit_rows.value.notna(), "indicator_id"], unit_rows.loc[unit_rows.value.notna(), "county_id"]))
    without_value = set(zip(unit_rows.loc[unit_rows.value.isna(), "indicator_id"], unit_rows.loc[unit_rows.value.isna(), "county_id"]))
    area_only = set(store.loc[store.geo_level.isin(["cooperation_area", "national"]) & store.value.notna(), "indicator_id"])

    def cell(indicator_id: str, code: str) -> str:
        if (indicator_id, code) in with_value:
            return VALUE
        if (indicator_id, code) in without_value:
            return SUPPRESSED
        if indicator_id in area_only:
            return AREA_ONLY
        return NONE

    data = {name: [cell(i, code) for i in indicator_ids] for code, name in units.items()}
    return pd.DataFrame(data, index=list(indicator_ids))
