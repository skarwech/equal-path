"""Neutrality lint: actions must be product-neutral (no sponsor, brand or drug names).

Matching is deliberately broad: brand and sponsor terms match as word *prefixes*
(so Finnish case endings such as "Tagrissoa" or "AstraZenecan" hit) and across two
adjacent words (so "Astra Zeneca" and "Astra-Zeneca" hit). Drug names are caught
by INN stems anywhere inside a word, so Finnish spellings, endings and compounds
("pembrolitsumabi", "osimertinibihoito") hit too.
"""

from __future__ import annotations

import re

# Sponsor and marketed oncology brands, lowercase; matched as word prefixes.
BLOCKED_TERMS: frozenset[str] = frozenset(
    {
        "astrazeneca",
        "tagrisso", "imfinzi", "imjudo", "lynparza", "enhertu", "calquence", "truqap",
        "iressa", "zoladex", "faslodex", "datroway",
        "keytruda", "opdivo", "yervoy", "tecentriq", "libtayo", "herceptin", "perjeta",
        "kadcyla", "ibrance", "kisqali", "verzenio", "xtandi", "zytiga", "erleada",
        "nubeqa", "alecensa", "lorbrena", "retevmo", "lumakras", "trodelvy",
    }
)

# Sponsor abbreviation: uppercase only, as a standalone token ("AZ", "AZ:n").
SPONSOR_ABBREVIATION = re.compile(r"\bAZ\b")

# INN stems of targeted and hormonal oncology drugs, incl. Finnish spellings
# (siklib, tsomib). Matched anywhere inside a word after >= 2 letters, so Finnish
# compounds such as "osimertinibihoito" or "trastutsumabiderukstekaani" are caught.
INN_STEMS: tuple[str, ...] = (
    "mab", "tinib", "rafenib", "ciclib", "siklib", "parib", "lisib", "degib",
    "zomib", "tsomib", "lutamid", "rasib", "sertib", "strant", "ateron",
)
_LETTER = r"[^\W\d_]"
INN_STEM = re.compile(rf"{_LETTER}{{2}}(?:{'|'.join(INN_STEMS)})", re.IGNORECASE)
WORD = re.compile(rf"{_LETTER}+")


def _brand_hit(token: str) -> str | None:
    lowered = token.casefold()
    return next((term for term in BLOCKED_TERMS if lowered.startswith(term)), None)


def neutrality_violations(text: str) -> list[str]:
    """Return one snippet per distinct offending term (empty list means neutral)."""
    hits: dict[str, str] = {}
    words = WORD.findall(text)
    for index, word in enumerate(words):
        term = _brand_hit(word)
        if term:
            hits.setdefault(term, word)
            continue
        if index + 1 < len(words):
            joined_term = _brand_hit(word + words[index + 1])
            if joined_term:
                hits.setdefault(joined_term, f"{word} {words[index + 1]}")
    if SPONSOR_ABBREVIATION.search(text):
        hits.setdefault("az", "AZ")
    for word in words:
        if INN_STEM.search(word):
            hits.setdefault(word.casefold(), word)
    return sorted(hits.values(), key=str.casefold)
