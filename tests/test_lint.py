"""Neutrality lint: no sponsor, brand or drug names in any action or config text."""

from pathlib import Path

import pytest
import yaml

from equal_path.lint import BLOCKED_TERMS, INN_STEMS, neutrality_violations
from equal_path.paths import CONFIG_DIR


@pytest.mark.parametrize(
    "text",
    [
        # sponsor, incl. spaced, hyphenated and Finnish-inflected forms
        "Partner with AstraZeneca on outreach",
        "Astra Zeneca funds the pilot",
        "Astra-Zeneca pilot",
        "Partner with Astra Zeneca on outreach",
        "yhteistyö Astra-Zenecan kanssa",
        "AstraZenecan tuki",
        "AstraZenecalle raportoidaan",
        "AstraZeneca's programme",
        "AZ:n rahoitus",
        # brands, incl. Finnish case endings and casing
        "Prefer Keytruda",
        "KEYTRUDA access",
        "keytruda® access",
        "Tagrisso access programme",
        "Tagrissoa käytetään",
        "Keytrudaa annetaan",
        "Imfinzin saatavuus",
        "Iressa", "Zoladex", "Faslodex", "Datroway",
        # INN stems, incl. Finnish spellings and endings
        "Start osimertinib earlier",
        "osimertinibi", "osimertinibin käyttö",
        "Use pembrolizumab in first line",
        "pembrolitsumabi ensilinjassa", "nivolumabi",
        "sotorasib", "adagrasib", "capivasertib", "camizestrant", "abiraterone", "abirateroni",
        # Finnish compounds and spellings (stem inside a longer word)
        "osimertinibihoito ensilinjassa", "olaparibihoitoa", "durvalumabihoidon",
        "trastutsumabiderukstekaani", "palbosiklibi", "bortetsomibi", "osimertinibilla",
        "Tagrisso-hoito", "Keytrudahoito",
        # all caps
        "OSIMERTINIB", "OLAPARIB",
    ],
)
def test_catches_planted_terms(text):
    assert neutrality_violations(text), text


@pytest.mark.parametrize(
    "text",
    [
        "Standardised referral criteria built on Kræftpakkeforløb, SVF and Pakkeforløp",
        "Kanta-Häme, Päijät-Häme and Etelä-Pohjanmaa",
        "Multidisciplinary tumour-board links with the university hospital",
        "G8 frailty screening and geriatric-oncology assessment at referral",
        "Community-based multilingual screening outreach with local NGOs",
        "Structured cancer recording template and automated reporting",
        "Hub-and-spoke remote oncology; digital care pathways; symptom awareness",
        "Mammography and colorectal screening; immunotherapy access is out of scope",
        "Lung cancer curative-route share and first-line treatment mix",
        "Seulontaan osallistuminen äidinkielen mukaan; hoitoonpääsy; kasvainkokous",
        "Monoclonal antibodies are named by class only",
    ],
)
def test_allows_neutral_pathway_language(text):
    assert neutrality_violations(text) == [], text


# Pinned independently of the lint module, so deleting a term from the lint fails here.
EXPECTED_BRANDS = {
    "astrazeneca",
    "tagrisso", "imfinzi", "imjudo", "lynparza", "enhertu", "calquence", "truqap",
    "iressa", "zoladex", "faslodex", "datroway",
    "keytruda", "opdivo", "yervoy", "tecentriq", "libtayo", "herceptin", "perjeta",
    "kadcyla", "ibrance", "kisqali", "verzenio", "xtandi", "zytiga", "erleada",
    "nubeqa", "alecensa", "lorbrena", "retevmo", "lumakras", "trodelvy",
}


def test_blocked_terms_pinned():
    assert BLOCKED_TERMS >= EXPECTED_BRANDS


@pytest.mark.parametrize("term", sorted(EXPECTED_BRANDS))
@pytest.mark.parametrize("form", ["{t}", "{T}", "{t}a", "{t}n käyttö"])
def test_every_blocked_term_is_caught(term, form):
    assert neutrality_violations(form.format(t=term, T=term.upper())), (term, form)


# One real INN example per stem; removing a stem from the lint must fail this test.
STEM_EXAMPLES = {
    "mab": "durvalumab", "tinib": "gefitinib", "rafenib": "sorafenib", "ciclib": "palbociclib",
    "siklib": "palbosiklibi", "parib": "olaparib", "lisib": "idelalisib", "degib": "vismodegib",
    "zomib": "bortezomib", "tsomib": "bortetsomibi", "lutamid": "enzalutamide", "rasib": "sotorasib",
    "sertib": "capivasertib", "strant": "fulvestrant", "ateron": "abiraterone",
}


def test_stem_examples_cover_every_stem():
    assert set(STEM_EXAMPLES) == set(INN_STEMS)


@pytest.mark.parametrize("stem,example", sorted(STEM_EXAMPLES.items()))
def test_every_inn_stem_is_caught(stem, example):
    assert neutrality_violations(f"Start {example} early"), stem


def test_reports_every_hit_once():
    hits = neutrality_violations("Keytruda and keytruda plus osimertinib and Tagrisso")
    assert len(hits) == len({h.casefold() for h in hits}) == 3


def _strings(node, path=""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _strings(value, f"{path}[{index}]")
    elif isinstance(node, str):
        yield path, node


@pytest.mark.parametrize("config_file", sorted(p.name for p in Path(CONFIG_DIR).glob("*.yaml")))
def test_every_config_string_is_neutral(config_file):
    data = yaml.safe_load((CONFIG_DIR / config_file).read_text(encoding="utf-8"))
    offenders = {path: neutrality_violations(text) for path, text in _strings(data)}
    assert {path: hits for path, hits in offenders.items() if hits} == {}
