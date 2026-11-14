"""Cancer Registry screening statistics pages (breast, cervical, colorectal), 2020-2024.

County tables give invited/picked and attended counts (numerator, denominator) and the
published share; screen-detected cancers and precursor lesions per county; national
population-group breakdowns (mother tongue, education). Cervical headline = age-group
screening; its population-group tables mix age and risk groups, so they are not loaded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from equal_path.loaders._util import html_table, obs, raw
from equal_path.names import resolve_area
from equal_path.spine import make_observations, parse_fi_number

SOURCE = "S_CR_SCREENING_STATS"
PAGES = {"breast": "breast.html", "cervical": "cervix.html", "colorectal": "colorectal.html"}
GROUPS = {
    "Domestic": "lang:domestic", "Other/missing": "lang:other_or_missing",
    "Primary education/unknown": "edu:primary_or_unknown", "Intermediate/secondary": "edu:secondary",
    "Tertiary/higher education": "edu:tertiary",
}
LABEL = re.compile(r"(Age group|Risk group) screening")


@dataclass(frozen=True)
class Table:
    section: str
    kind: str
    year: str
    label: str
    frame: object
    locator: str


def _heading(tag, name: str) -> str:
    found = tag.find_previous(name)
    return found.get_text(" ", strip=True) if found else ""


def _tables(programme: str) -> list[Table]:
    page = PAGES[programme]
    with raw("screening", page).open(encoding="utf-8") as handle:
        soup = BeautifulSoup(handle.read(), "lxml")
    tables = []
    for element in soup.find_all("table"):
        section, kind, year = _heading(element, "h2"), _heading(element, "h3"), _heading(element, "h4")
        if not re.fullmatch(r"20\d\d", year):
            continue
        label = ""
        if programme == "cervical" and section == "Wellbeing services counties":
            previous = element.find_previous_sibling()
            found = LABEL.search(previous.get_text(" ", strip=True)) if previous else None
            if not found:
                raise ValueError(f"{page}: county table under {kind} {year} lacks its age/risk group label")
            label = found.group(1)
        locator = f"{page} > {section} > {kind} > {year}" + (f" [{label}]" if label else "")
        tables.append(Table(section, kind, year, label, html_table(str(element)), locator))
    return tables


def _n(text) -> float | None:
    return parse_fi_number(text)


def _participation_columns(frame) -> tuple[str, str, str] | None:
    cols = list(frame.columns)
    den = next((c for c in cols if c in ("Invited | N", "Picked | N")), None)
    num = next((c for c in cols if c in ("Attended (of invited) | N", "Attended | N")), None)
    pct = next((c for c in cols if c in ("Attended (of invited) | %", "Attended | %")), None)
    if pct and not den:  # a participation rate with an unknown denominator = the source changed
        raise ValueError(f"participation table has an attendance rate but no recognised denominator: {cols[:4]}")
    return (num, den, pct) if num and den and pct else None


def _participation(programme: str, table: Table) -> list[dict]:
    columns = _participation_columns(table.frame)
    if columns is None:
        return []
    num_col, den_col, pct_col = columns
    first = table.frame.columns[0]
    rows = []
    for _, row in table.frame.iterrows():
        if table.section == "Wellbeing services counties":
            geo, code = resolve_area(row[first])
            subgroup = "all"
        elif table.section == "Population groups" and programme != "cervical" and row[first] in GROUPS:
            if "Sex" in table.frame.columns and row["Sex"] != "Total":
                continue
            geo, code, subgroup = "national", "FI", GROUPS[row[first]]
        else:
            continue
        pct = _n(row[pct_col])
        rows.append(obs(geo, code, f"screening_participation_{programme}", table.year,
                        None if pct is None else round(pct / 100, 6), SOURCE, table.locator, subgroup,
                        numerator=_n(row[num_col]), denominator=_n(row[den_col])))
    return rows


# (programme, table kind, label) -> [(column, indicator, subgroup)]
DETECTED = {
    ("breast", "Screening results", ""): [("Malignant (of referred) | N", "screening_cancers_detected", "prog:breast")],
    ("cervical", "Histological findings", "Age group"): [
        ("Cervical cancer | N", "screening_cancers_detected", "prog:cervical_age"),
        ("HSIL | N", "screening_precursors_detected", "prog:cervical_age|lesion:hsil"),
        ("AIS | N", "screening_precursors_detected", "prog:cervical_age|lesion:ais"),
    ],
    ("cervical", "Histological findings", "Risk group"): [
        ("Cervical cancer | N", "screening_cancers_detected", "prog:cervical_risk"),
        ("HSIL | N", "screening_precursors_detected", "prog:cervical_risk|lesion:hsil"),
        ("AIS | N", "screening_precursors_detected", "prog:cervical_risk|lesion:ais"),
    ],
    ("colorectal", "Diagnoses", ""): [
        ("Cancer | N", "screening_cancers_detected", "prog:colorectal"),
        ("Adenoma/polyp, advanced | N", "screening_precursors_detected", "prog:colorectal|lesion:advanced_adenoma"),
    ],
}


def _detected(programme: str, table: Table) -> list[dict]:
    if table.section != "Wellbeing services counties":
        return []
    specs = DETECTED.get((programme, table.kind, table.label), [])
    first = table.frame.columns[0]
    rows = []
    for _, row in table.frame.iterrows():
        geo, code = resolve_area(row[first])
        for column, indicator, subgroup in specs:
            rows.append(obs(geo, code, indicator, table.year, _n(row[column]), SOURCE, table.locator, subgroup))
    return rows


def load():
    rows = []
    for programme in PAGES:
        for table in _tables(programme):
            if programme == "cervical" and table.section == "Wellbeing services counties" and table.label == "Risk group" \
                    and table.kind == "Screening process":
                continue  # headline participation = age-group screening only
            rows += _participation(programme, table) + _detected(programme, table)
    return make_observations(rows)
