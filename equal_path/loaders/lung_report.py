"""Lung cancer quality report 2019-2023, Taulukko 11: curative-intent share by county
(numerator, denominator, published share). Shares are crude, by home county, pooled."""

from __future__ import annotations

import io

import pandas as pd

from equal_path.loaders._util import obs, raw
from equal_path.names import resolve_area
from equal_path.spine import make_observations, parse_fi_number

SOURCE = "S_LUNG_REPORT_2019_2023"
FILE = "keuhkosyoparaportti_2019_2023.html"
GROUPS = {"Parantava": "lung_curative_route_share"}


def _table() -> pd.DataFrame:
    text = raw("reports", FILE).read_text(encoding="utf-8")
    start = text.find('id="tbl-osuudet-hva"')
    if start < 0:
        raise ValueError(f"{FILE}: Taulukko 11 (tbl-osuudet-hva) not found")
    begin = text.find("<table", start)
    end = text.find("</table>", begin) + len("</table>")
    return pd.read_html(io.StringIO(text[begin:end]))[0].astype(str)


AREA_TOTAL = "Yhteistyöalue yhteensä"


def _header(text: str) -> tuple[str, str] | None:
    """A full-width header row is either a cooperation area or a treatment group."""
    try:
        return resolve_area(text)
    except ValueError:
        return None


def load():
    frame = _table()
    rows, group, area = [], None, None
    for _, row in frame.iterrows():
        cells = [c for c in row.tolist() if c != "nan"]
        if len(set(cells)) == 1:
            resolved = _header(cells[0])
            if resolved is None:
                group, area = cells[0], None  # new treatment group
            else:
                area = resolved
            continue
        if group not in GROUPS:
            continue
        name = row["Hyvinvointialue"]
        if name == AREA_TOTAL:
            if area is None:
                raise ValueError(f"{FILE}: area total row without an area header")
            geo, code = area
        else:
            geo, code = resolve_area(name)
        num, den, pct = (parse_fi_number(row[c]) for c in ("Lukumäärä", "Yhteensä", "Osuus (%)"))
        rows.append(obs(geo, code, GROUPS[group], "2019-2023", None if pct is None else pct / 100, SOURCE,
                        f"{FILE} > Taulukko 11 > {group} > {name}", numerator=num, denominator=den))
    return make_observations(rows)
