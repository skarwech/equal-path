"""Action Card (spec F8, P1): one printable page per county.

The card is plain data (CardLine: text + sources + locator). The app shows those lines on screen and
render_pdf() writes the same lines to a one-page PDF, so the two cannot drift apart. The PDF writer is
self-contained (built-in Helvetica, WinAnsi encoding, uncompressed text), so it needs no extra package,
works offline, and tests can read its text back. Content that does not fit raises CardOverflow; it is
never silently cut.
"""

from __future__ import annotations

from dataclasses import dataclass

from equal_path.actions import STAGES

SPEC = "S_EQUAL_PATH_SPEC"
PAGE_W, PAGE_H, MARGIN = 595.0, 842.0, 48.0          # A4 in points
BODY, LEADING = 9.5, 12.4
SECTION_SIZE, TITLE_SIZE, SUBTITLE_SIZE = 11.5, 16.0, 9.0
FOOTER = "Equal Path, Junction 2026. Product-neutral: no sponsor, brand or drug names. Public data only."


class CardOverflow(ValueError):
    """The card does not fit on one page."""


@dataclass(frozen=True)
class CardLine:
    text: str
    sources: str        # registered source ids, '; '-separated
    locator: str        # where in the source, or how the line was derived

    def __post_init__(self):
        object.__setattr__(self, "text", " ".join(self.text.split()))


@dataclass(frozen=True)
class Card:
    code: str
    county: str
    date: str
    title: str
    subtitle: str
    sections: tuple[tuple[str, tuple[CardLine, ...]], ...]
    footer: str = FOOTER


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", ")")) else text + "."


def _why(rule, facts: dict) -> str:
    if rule.id == "R-DAT-01":
        return (f"stage-recording coverage {facts['stage_coverage'] * 100:.1f} % ({facts['stage_coverage_level']} "
                "figure), below the 70 % target")
    if rule.id == "R-DET-02":
        return "screening statistics are published annually"
    why = f"verified gap in {rule.stage}: {facts[f'gap_{rule.stage}'] * 100:.1f} pp"
    return why + (" and above-median distance to a university hospital" if rule.id == "R-TRT-01" else "")


def _stage_list(stages: list[str]) -> str:
    return stages[0] if len(stages) == 1 else ", ".join(stages[:-1]) + " and " + stages[-1]


def build_card(code: str, run, date: str) -> Card:
    from equal_path.config import load_rules
    from equal_path.sources import load_sources

    rules = {r.id: r for r in load_rules()}
    titles = dict(zip(load_sources().source_id, load_sources().title))
    plan, facts = run.plans[code], run.facts[code]
    county, area = run.names[code], run.coop_area[code]

    from equal_path.config import load_indicator_catalog

    primary = run.primary[code]
    for indicator in load_indicator_catalog():   # readable label instead of the internal id
        primary = primary.replace(f"{indicator.id} (all)", indicator.label).replace(indicator.id, indicator.label)
    finding = [CardLine(f"Primary finding: {primary}.", SPEC, "F2 gap locator (sources drawer, Header)"),
               CardLine(_sentence(plan.message), SPEC, "F5 ranking rule")]
    for o in plan.outcomes:
        rule = rules[o.rule_id]
        if o.status == "needs data" and facts.get(f"stage_{rule.stage}") == "leak":
            reasons = "; ".join(m.split(" (", 1)[1].rstrip(")") for m in o.missing)
            finding.append(CardLine(f"Verified gap in {rule.stage}, but {rule.id} cannot be checked yet: {reasons}.",
                                    "; ".join(dict.fromkeys(c.id for c in rule.sources)), "F5: needs data"))

    actions = []
    for i, o in enumerate(plan.top, start=1):
        rule = rules[o.rule_id]
        sources = "; ".join(dict.fromkeys(c.id for c in rule.sources))
        cited = "; ".join(f"{titles[c.id]}, {c.locator}" for c in rule.sources)
        actions += [
            CardLine(f"{i}. {o.verb}: {_sentence(rule.action)}", sources, rule.id),
            CardLine(f"Owner: {o.owner_label}", sources, f"{rule.id} owner_level {rule.owner_level}"),
            CardLine(f"KPI: {rule.kpi}", sources, rule.id),
            CardLine(f"Cost reference: {rule.cost_ref}", sources, rule.id),
            CardLine(f"Why: {_why(rule, facts)}; evidence: {rule.evidence_grade}. Source: {cited}.", sources, rule.id),
        ]
    if not actions:
        actions = [CardLine("No action fires for this county today.", SPEC, "F5")]

    unknown = [s for s in STAGES if facts.get(f"stage_{s}") == "unknown"]
    pilot = [
        CardLine(f"Capture the Pathway Clock time points in {county} for lung cancer and one other cancer, as "
                 "county-level aggregates: the THL access dates (Ohjaus 21/2016) plus the first primary-care contact "
                 "and the tumour-board date.", "S_THL_OHJAUS_21_2016; S_STRATEGY", "spec 7.5 and 13; strategy 2.5"),
        CardLine(f"Run a monthly equity review with FICAN's regional cancer centre for the {area} cooperation area, "
                 "attached to the national pilots planned for 2026-2028 (referral criteria, roadmap 2.5.2; digital "
                 "pathways, 3.5.3; structured recording, 4.1.1).", "S_ROADMAP", "2.5.2, 3.5.3, 4.1.1"),
    ]
    if unknown:
        pilot.append(CardLine(f"Day 90: a first monthly figure for {_stage_list(unknown)}, which public data cannot "
                              "show today.", SPEC, "F1 visibility"))

    judged = sum(facts.get(f"stage_{s}") != "unknown" for s in STAGES if s != "timing")
    limitations = [
        CardLine(f"Visibility {facts['visibility_score']:.1f}/100: {judged} of the 4 pathway stages can be judged from "
                 "public data; access times (timing) are not published by county.", SPEC, "F1 visibility score"),
        CardLine(f"Stage-recording coverage is {facts['stage_coverage'] * 100:.1f} % ({facts['stage_coverage_level']} "
                 "figure); stage-level findings stay provisional below 70 %.", "S_CIF2024_REPORT", "Table 5.1 and area text"),
        CardLine("Costs are national reference figures from the roadmap, not county budgets; hypothesis-graded actions "
                 "are marked Test, never Implement.", "S_ROADMAP", "cost annex"),
        CardLine("Every figure is traceable in the app's sources drawer; nothing on this card is synthetic.", SPEC,
                 "sources drawer"),
    ]
    return Card(code, county, date, f"Equal Path Action Card: {county} ({code})",
                f"Generated {date} from public data only. Cooperation area: {area}.",
                (("Finding", tuple(finding)), ("Actions", tuple(actions)), ("90-day pilot", tuple(pilot)),
                 ("Limitations", tuple(limitations))))


def card_text_lines(card: Card) -> list[str]:
    lines = [card.title, card.subtitle]
    for title, section in card.sections:
        lines += [title, *(line.text for line in section)]
    return [*lines, card.footer]


# --- PDF ---------------------------------------------------------------------------------------

# Helvetica advance widths (Adobe AFM, 1/1000 em) for ASCII; other characters use a wide default.
_W = dict(zip(" !\"#$%&'()*+,-./0123456789:;<=>?@", [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584,
                                                       278, 333, 278, 278] + [556] * 10 + [278, 278, 584, 584, 584, 556, 1015]))
_W.update(dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", [667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722,
                                                   778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611])))
_W.update(dict(zip("abcdefghijklmnopqrstuvwxyz", [556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556,
                                                   556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500])))
_W.update({"[": 278, "]": 278, "_": 556, "|": 260, "–": 556, "ä": 556, "ö": 556, "å": 556, "Ä": 667, "Ö": 778, "Å": 667})


def _width(text: str, size: float, bold: bool = False) -> float:
    return sum(_W.get(ch, 667) for ch in text) * size / 1000 * (1.08 if bold else 1.0)


def _wrap(text: str, size: float, bold: bool, width: float) -> list[str]:
    lines, current = [], ""
    for word in text.split(" "):
        trial = f"{current} {word}" if current else word
        if _width(trial, size, bold) <= width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    return [*lines, current]


def _pdf_string(text: str) -> bytes:
    raw = text.encode("cp1252")   # raises on characters the built-in font cannot show
    return b"(" + raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def render_pdf(card: Card) -> bytes:
    width = PAGE_W - 2 * MARGIN
    blocks: list[tuple[str, float, bool, float]] = [(card.title, TITLE_SIZE, True, 6), (card.subtitle, SUBTITLE_SIZE, False, 10)]
    for title, section in card.sections:
        blocks.append((title, SECTION_SIZE, True, 3))
        for line in section:
            numbered = line.text[:3] in ("1. ", "2. ", "3. ")
            if numbered and line is not section[0]:
                blocks[-1] = (*blocks[-1][:3], blocks[-1][3] + 4)   # air before each numbered action
            blocks.append((line.text, BODY, numbered, 2.5))
        blocks[-1] = (*blocks[-1][:3], 9)
    blocks.append((card.footer, 8.0, False, 0))

    ops, y = [], PAGE_H - MARGIN
    for text, size, bold, gap_after in blocks:
        wrapped = _wrap(text, size, bold, width)
        leading = size * 1.3
        y -= size
        if y - leading * (len(wrapped) - 1) < MARGIN:
            raise CardOverflow(f"card for {card.code} does not fit on one page")
        font = b"/F2" if bold else b"/F1"
        ops.append(b"BT %s %.1f Tf %.1f TL %.2f %.2f Td " % (font, size, leading, MARGIN, y)
                   + b" T* ".join(_pdf_string(part) + b" Tj" for part in wrapped) + b" ET")
        y -= leading * (len(wrapped) - 1) + gap_after
    ops.append(b"0.75 g %.2f %.2f %.2f 0.6 re f" % (MARGIN, PAGE_H - MARGIN - TITLE_SIZE - 3, width))
    content = b"\n".join(ops)

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> "
        b"/Contents 6 0 R >>" % (PAGE_W, PAGE_H),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def pdf_text_lines(pdf: bytes) -> list[str]:
    """Text of each BT..ET block (one per card line), wrapped parts re-joined with a space."""
    import re

    stream = pdf.split(b"stream\n", 1)[1].split(b"\nendstream", 1)[0]
    lines = []
    for block in re.findall(rb"BT (.*?) ET", stream, flags=re.S):
        parts = re.findall(rb"\(((?:\\.|[^\\)])*)\) Tj", block)
        decoded = [re.sub(rb"\\(.)", rb"\1", p).decode("cp1252") for p in parts]
        lines.append(" ".join(decoded))
    return lines
