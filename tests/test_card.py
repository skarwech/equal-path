"""Action Card (F8, P1): one printable page per county; the PDF says exactly what the screen says."""

import re
import time

import pytest

from equal_path.card import CardOverflow, build_card, card_text_lines, pdf_text_lines, render_pdf

CODES = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11",
         "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "90"]
DATE = "2026-11-14"


@pytest.fixture(scope="module")
def cards():
    from equal_path.actions import run_actions

    run = run_actions()
    return {code: build_card(code, run, DATE) for code in CODES}


def _xref_ok(pdf: bytes) -> bool:
    start = int(re.search(rb"startxref\s+(\d+)", pdf).group(1))
    table = pdf[start:].split(b"trailer")[0].split(b"\n")
    offsets = [int(line[:10]) for line in table[3:] if len(line) >= 18 and line[17:18] == b"n"]
    return all(pdf[o:].startswith(f"{k} 0 obj".encode()) for k, o in enumerate(offsets, start=1))


@pytest.mark.parametrize("code", CODES)
def test_pdf_is_one_valid_page_in_under_3_seconds(cards, code):
    started = time.perf_counter()
    pdf = render_pdf(cards[code])
    elapsed = time.perf_counter() - started
    assert elapsed < 3.0
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    assert b"/Count 1" in pdf and pdf.count(b"/Type /Page ") == 1
    assert _xref_ok(pdf)


@pytest.mark.parametrize("code", CODES)
def test_pdf_text_equals_the_card_text(cards, code):
    """Spec F8: sampled text equals the on-screen content. Here all of it: same lines, same order."""
    assert pdf_text_lines(render_pdf(cards[code])) == card_text_lines(cards[code])


@pytest.mark.parametrize("code", CODES)
def test_card_has_the_spec_sections(cards, code):
    card = cards[code]
    titles = [title for title, _ in card.sections]
    assert titles == ["Finding", "Actions", "90-day pilot", "Limitations"]
    actions = dict(card.sections)["Actions"]
    assert 1 <= sum(line.text[:3] in {"1. ", "2. ", "3. "} for line in actions) <= 3
    for label in ("Owner:", "KPI:", "Cost reference:"):
        assert any(line.text.startswith(label) for line in actions), label
    assert DATE in " ".join(card_text_lines(card))


def test_card_text_is_product_neutral_and_printable(cards):
    from equal_path.lint import neutrality_violations

    for card in cards.values():
        text = "\n".join(card_text_lines(card))
        assert neutrality_violations(text) == []
        text.encode("cp1252")  # the PDF's built-in font encoding


def test_every_card_line_cites_a_registered_source(cards):
    from equal_path.sources import load_sources

    registered = set(load_sources().source_id)
    for card in cards.values():
        for _, lines in card.sections:
            for line in lines:
                ids = {s.strip() for s in line.sources.split(";") if s.strip()}
                assert ids and ids <= registered, line


def test_no_verified_gap_card_says_so(cards):
    finding = " ".join(line.text for line in dict(cards["01"].sections)["Finding"])
    assert "no verified gap; maintain and improve data" in finding.lower()


def test_test_mode_and_national_lead_are_printed():
    """Fixture card: a hypothesis rule prints as 'Test', a national-lead rule names the national lead."""
    from equal_path.actions import ActionRun, county_plan
    from equal_path.config import load_thresholds
    from test_actions import QUIET, TRUTH

    facts = {**QUIET, **TRUTH["R-AUD-01"][0], "gap_timing": 0.05, **TRUTH["R-REF-02"][0], "gap_referral": 0.04,
             "visibility_score": 58.9, "stage_coverage_level": "national"}
    plan = county_plan(facts, load_thresholds())
    run = ActionRun(plans={"90": plan}, facts={"90": facts}, primary={"90": "fixture"}, names={"90": "Helsinki"},
                    coop_area={"90": "Etelä-Suomi"})
    text = card_text_lines(build_card("90", run, DATE))
    assert any(line.startswith("1. Test:") or line.startswith("2. Test:") for line in text)
    assert any("National lead" in line for line in text)


def test_overflow_raises_instead_of_truncating(cards):
    from dataclasses import replace

    from equal_path.card import CardLine

    long = tuple(CardLine(f"filler line {i} " * 8, "S_EQUAL_PATH_SPEC", "test") for i in range(200))
    with pytest.raises(CardOverflow):
        render_pdf(replace(cards["01"], sections=(*cards["01"].sections, ("Extra", long))))


def test_special_characters_round_trip(cards):
    from dataclasses import replace

    from equal_path.card import CardLine

    tricky = (CardLine(r"Parentheses (a) and back\slash, Pohjois-Pohjanmaa ä ö – EUR", "S_EQUAL_PATH_SPEC", "test"),)
    card = replace(cards["01"], sections=(*cards["01"].sections[:-1], ("Limitations", tricky)))
    assert pdf_text_lines(render_pdf(card)) == card_text_lines(card)
