"""Resolve published area names (Finnish, Swedish or English, full or short) to our codes."""

from __future__ import annotations

import re
from functools import lru_cache

from equal_path.geography import load_units

NATIONAL_NAMES = ("koko maa", "whole finland", "total", "finland", "total (finland)", "suomi", "yhteensä", "hela landet")
ALAND_NAMES = ("åland", "ahvenanmaa")
# English cooperation-area names used by the Cancer Registry reports (code = Statistics Finland yhteistyöalue)
COOP_AREA_EN = {"Southern Finland": "1", "Eastern Finland": "2", "Inland Finland": "3",
                "Western Finland": "4", "Northern Finland": "5"}


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", str(name).replace("–", "-").replace(" ", " ")).strip().casefold()


def _add(aliases: dict, name: str, target: tuple[str, str]) -> None:
    key = _norm(name)
    if aliases.get(key, target) != target:
        raise ValueError(f"area name {name!r} is ambiguous: {aliases[key]} vs {target}")
    aliases[key] = target


@lru_cache(maxsize=1)
def _aliases() -> dict[str, tuple[str, str]]:
    aliases: dict[str, tuple[str, str]] = {}
    for row in load_units().itertuples(index=False):
        for name in (row.name_fi, row.name_sv, row.name_en, row.short_fi, row.short_en,
                     row.name_en.replace(" wellbeing services county", "")):
            _add(aliases, name, ("unit", row.code))
        for name in (row.coop_area_full_fi, row.coop_area_fi):
            _add(aliases, name, ("cooperation_area", f"YTA{row.coop_area_code}"))
    for name, code in COOP_AREA_EN.items():
        _add(aliases, name, ("cooperation_area", f"YTA{code}"))
    for name in NATIONAL_NAMES:
        _add(aliases, name, ("national", "FI"))
    for name in ALAND_NAMES:
        _add(aliases, name, ("excluded_unit", "91"))
    return aliases


def resolve_area(name: str) -> tuple[str, str]:
    """(geo_level, code) for a published area name; unknown names raise, never guess."""
    try:
        return _aliases()[_norm(name)]
    except KeyError:
        raise ValueError(f"unknown area name {name!r}") from None
