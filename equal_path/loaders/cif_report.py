"""Cancer in Finland 2024 report: county survival (Tables 15.10-15.13) and national stage
coverage (Table 5.1). Survival is a relative-survival ratio with a 95% CI (can exceed 1)."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from equal_path.geography import load_units
from equal_path.loaders._util import obs, raw
from equal_path.names import resolve_area
from equal_path.spine import make_observations, parse_fi_number

SOURCE = "S_CIF2024_REPORT"
FILE = "cancer_in_finland_2024.html"
CI = re.compile(r"^\s*([\d.,]+)\s*\(\s*([\d.,]+)\s*,\s*([\d.,]+)\s*\)\s*$")
COUNT_SHARE = re.compile(r"^\s*([\d\s ]+)\s*\(([\d.,]+)%\)\s*$")
STAGE_SITES = {"C00-69,C73-80,D09.0-1,D41": "all", "C33-34": "site:lung", "C50": "site:breast"}


def _soup() -> BeautifulSoup:
    with raw("reports", FILE).open(encoding="utf-8") as handle:
        return BeautifulSoup(handle.read(), "lxml")


def _caption_table(soup, prefix: str):
    for caption in soup.find_all("caption"):
        if caption.get_text(" ", strip=True).startswith(prefix):
            return caption.get_text(" ", strip=True), caption.find_parent("table")
    raise ValueError(f"{FILE}: table {prefix!r} not found")


# table number -> (subgroup, keyword that must appear in the caption)
SERIES = {
    "15.10": ("site:breast|sex:female", "breast cancer in women"),
    "15.11": ("site:colorectal|sex:all", "colorectal cancer"),
    "15.12": ("site:lung|sex:female", "lung cancer in women"),
    "15.13": ("site:lung|sex:male", "lung cancer in men"),
}


def _survival(soup) -> list[dict]:
    coop_of = dict(zip(load_units()["code"], load_units()["coop_area_code"]))
    rows = []
    for number, (subgroup, keyword) in SERIES.items():
        caption, table = _caption_table(soup, f"TAULUKKO {number}")
        if keyword not in caption.lower():
            raise ValueError(f"{FILE} TAULUKKO {number}: caption no longer mentions {keyword!r}")
        area = None
        for tr in table.find("tbody").find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            name = cells[0]
            geo, code = resolve_area(name)
            if geo == "cooperation_area":
                area = code
            elif geo == "unit" and f"YTA{coop_of[code]}" != area:
                raise ValueError(f"{FILE} TAULUKKO {number}: {name} listed under {area}, expected YTA{coop_of[code]}")
            match = CI.match(cells[3])
            if not match:
                raise ValueError(f"{FILE} TAULUKKO {number}: cannot parse survival {cells[3]!r} for {name}")
            value, low, high = (parse_fi_number(v) / 100 for v in match.groups())
            rows.append(obs(geo, code, "survival_5y_relative", "2020-2024", value, SOURCE,
                            f"{FILE} > TAULUKKO {number} > {name} > 5-year", subgroup, ci_low=low, ci_high=high))
    return rows


def _stage_coverage(soup) -> list[dict]:
    _, table = _caption_table(soup, "TAULUKKO 5.1")
    rows = []
    for tr in table.find("tbody").find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if cells[1] not in STAGE_SITES:
            continue
        match = COUNT_SHARE.match(cells[2])
        if not match:
            raise ValueError(f"{FILE} Table 5.1: cannot parse {cells[2]!r}")
        rows.append(obs("national", "FI", "stage_recording_coverage", "2024", parse_fi_number(match.group(2)) / 100,
                        SOURCE, f"{FILE} > TAULUKKO 5.1 > {cells[0]}", STAGE_SITES[cells[1]],
                        numerator=parse_fi_number(match.group(1)), denominator=parse_fi_number(cells[4])))
    return rows


PROSE = re.compile(
    r"Inland Finland collaborative area \((\d+(?:\.\d+)?)\s*%\), where the coverage of data was particularly "
    r"high in the wellbeing services county of Pirkanmaa \((\d+(?:\.\d+)?)\s*%(?:, FIGURE 5\.2\s*)?\)"
)


def _prose_stage_coverage(soup) -> list[dict]:
    """Section 5 states two regional values in text; county values exist only in a figure."""
    text = re.sub(r"\s+", " ", soup.get_text(" "))
    match = PROSE.search(text)
    if not match:
        raise ValueError(f"{FILE}: section 5 sentence with the Inland Finland / Pirkanmaa stage coverage not found")
    locator = f"{FILE} > 5 Stage at diagnosis > text"
    area, pirkanmaa = (parse_fi_number(v) / 100 for v in match.groups())
    return [
        obs("cooperation_area", "YTA3", "stage_recording_coverage", "2024", area, SOURCE, locator, quality_flag="transcribed"),
        obs("unit", "08", "stage_recording_coverage", "2024", pirkanmaa, SOURCE, locator, quality_flag="transcribed"),
    ]


def load():
    soup = _soup()
    return make_observations(_survival(soup) + _stage_coverage(soup) + _prose_stage_coverage(soup))
