"""Step 8 hardening: offline analyst cache, network blocking, trust / data-gap / limitations content, rehearsal.

Offline mode (spec F8): every county's briefing is cached in data/processed/briefings.json with the hash of the
facts it was written from and the hash of the text. The page shows a cached briefing only if both hashes match,
a template entry is exactly what the template gives for these facts, and the text passes the number validator.
A missing, corrupt, stale or edited entry is never shown; the deterministic template is shown instead.
The page and the trust panel use the same selection function (select_briefing).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import socket
import time
from datetime import date
from pathlib import Path

import pandas as pd

from equal_path.paths import DATA_DIR, ROOT

BRIEFINGS_FILE = DATA_DIR / "processed" / "briefings.json"
DEMO_COUNTIES = ("10", "14", "90")   # treatment + detection leak; detection leak; capital, no verified gap
REHEARSAL_RUNS = 5                   # spec Step 7: five consecutive offline rehearsals
SPEC = "S_EQUAL_PATH_SPEC"
CACHE_NOTE = "from the offline cache"
_NUMBER_PROBLEMS = ("number", "matches no figure", "Roman numeral", "non-ASCII number", "signed")
log = logging.getLogger(__name__)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def facts_hash(facts: dict) -> str:
    return _sha(json.dumps(facts, sort_keys=True, ensure_ascii=False))


def load_cache(path: Path = BRIEFINGS_FILE) -> dict:
    """The cache, or {} if it is missing or unreadable (the page then shows the template; review O-5)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError) as exc:
        log.warning("briefing cache unreadable, ignored: %s", exc)
        return {}
    return data if isinstance(data, dict) else {}


def cached_briefing(facts: dict, cache: dict, code: str):
    """The cached Briefing, only if written from these exact facts, unedited, and passing the validator."""
    from equal_path.analyst import Briefing, template_briefing, validate

    entry = cache.get(code)
    if not isinstance(entry, dict):
        return None
    text, source = entry.get("text"), entry.get("source")
    if not isinstance(text, str) or source not in ("claude", "template"):
        return None
    if entry.get("facts_hash") != facts_hash(facts) or entry.get("text_hash") != _sha(text):
        return None
    if source == "template" and text != template_briefing(facts):   # words edited, not only numbers (review O-2)
        return None
    if source == "claude" and not entry.get("model"):
        return None
    if not validate(text, facts).ok:
        return None
    return Briefing(text, source, 0, note=f"{CACHE_NOTE}, generated {entry.get('generated_on', '?')}",
                    model=entry.get("model", ""))


def select_briefing(code: str, run, cache: dict | None = None, live: bool = False):
    """What the county page shows: a current cache entry, else (live=True) a Claude briefing, else the template."""
    from equal_path.analyst import Briefing, briefing_facts, generate_briefing, make_client, template_briefing

    facts = briefing_facts(code, run)
    found = cached_briefing(facts, load_cache() if cache is None else cache, code)
    if found is not None:
        return facts, found
    if live and make_client() is not None:
        return facts, generate_briefing(facts)
    return facts, Briefing(template_briefing(facts), "template", 0, note="no current cache entry and no Claude client")


def build_briefing_cache(run, today: str | None = None, path: Path = BRIEFINGS_FILE) -> dict:
    """One validated briefing per county (Claude when available, else the template), written to the cache."""
    from equal_path.analyst import briefing_facts, generate_briefing, validate

    cache = {}
    for code in sorted(run.plans):
        facts = briefing_facts(code, run)
        briefing = generate_briefing(facts)
        if not validate(briefing.text, facts).ok:
            raise ValueError(f"{code}: briefing failed the validator; not cached")
        cache[code] = {"facts_hash": facts_hash(facts), "text_hash": _sha(briefing.text), "text": briefing.text,
                       "source": briefing.source, "model": briefing.model,
                       "generated_on": today or date.today().isoformat()}
    path.write_text(json.dumps(cache, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return cache


class NetworkBlock:
    """Counts the outbound attempts it refused while active."""

    def __init__(self):
        self.refused = 0


@contextlib.contextmanager
def block_network():
    """Every outbound connection, datagram and DNS lookup raises, as with the network disabled (in this process)."""
    block = NetworkBlock()

    def refuse(*args, **kwargs):
        block.refused += 1
        raise OSError("network blocked (offline mode)")

    targets = [(socket.socket, n) for n in ("connect", "connect_ex", "sendto", "sendmsg")]
    targets += [(socket, n) for n in ("getaddrinfo", "create_connection", "gethostbyname", "gethostbyname_ex",
                                      "gethostbyaddr")]
    saved = [(owner, name, getattr(owner, name)) for owner, name in targets]
    for owner, name in targets:
        setattr(owner, name, refuse)
    try:
        yield block
    finally:
        for owner, name, original in saved:
            setattr(owner, name, original)


def trust_figures(reconciliation, run, summary) -> dict:
    """Spec F8 Trust panel, computed from the actual runs: anchors, tests, and the briefings the page shows."""
    from equal_path.analyst import validate

    cache = load_cache()
    shown = [select_briefing(c, run, cache) for c in sorted(run.plans)]
    checks = [validate(b.text, f) for f, b in shown]
    statuses = [r.status for r in reconciliation]
    return {
        "anchors_passed": statuses.count("pass"), "anchors_failed": statuses.count("fail"),
        "anchors_not_checked": len(statuses) - statuses.count("pass") - statuses.count("fail"),
        "anchors_total": len(statuses),
        "tests_passed": getattr(summary, "passed", 0), "tests_total": getattr(summary, "total", 0),
        "briefings": len(checks), "briefings_passed": sum(c.ok for c in checks),
        "briefings_from_cache": sum(CACHE_NOTE in b.note for _, b in shown),
        "unsupported_numbers_shown": sum(1 for c in checks for p in c.problems if any(k in p for k in _NUMBER_PROBLEMS)),
    }


def data_gaps(catalog, store: pd.DataFrame) -> pd.DataFrame:
    """Spec Step 6 data-gap panel: every catalog indicator without a value for all 22 units (by the store)."""
    units = store[(store.geo_level == "unit") & store.value.notna()]
    rows = []
    for item in catalog:
        n = units.loc[units.indicator_id == item.id, "county_id"].nunique()
        if n == 22:
            continue
        rows.append({"Stage": item.stage, "Indicator": item.id, "Label": item.label, "Status": item.status,
                     "Units with a value": f"{n} of 22", "Why": item.limitation})
    order = {s: i for i, s in enumerate(("detection", "referral", "diagnosis", "treatment", "timing", "context"))}
    return pd.DataFrame(rows).sort_values(["Stage", "Indicator"], key=lambda s: s.map(order) if s.name == "Stage" else s)


def _list(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def limitations(run, result=None) -> list[tuple[str, str]]:
    """Spec Step 6 limitations panel: each statement computed from the data, with its source."""
    from equal_path.config import load_scope, load_thresholds
    from equal_path.display import national_value
    from equal_path.glidepath import calibration
    from equal_path.observations import load_observations
    from equal_path.pathway import run_pathway

    facts, names = run.facts, run.names
    store = load_observations()
    result = result if result is not None else run_pathway(store)
    bar = load_thresholds().twin_stability_jaccard
    own = [names[c] for c, f in facts.items() if f.get("stage_coverage_level") == "county"]
    grey = {s: sum(f[f"stage_{s}"] == "unknown" for f in facts.values()) for s in ("diagnosis", "timing")}
    calib = calibration(store)
    unstable = sum(v < bar for v in result.twin_stability.values())
    subgroup_units = store[(store.geo_level == "unit") & (store.subgroup.str.startswith(("lang:", "edu:")))]
    national = national_value(store, "stage_recording_coverage")
    if own:
        coverage = (f"{_list(own)} {'has its' if len(own) == 1 else 'have their'} own stage-recording figure; the other "
                    f"{len(facts) - len(own)} counties use the cooperation-area or national figure")
    else:
        coverage = "No county has its own stage-recording figure; all use the cooperation-area or national figure"
    coverage += f" ({national * 100:.1f} % nationally)." if national is not None else "."
    glide = (f"Glidepaths are {calib.label}: held-out-year calibration covered {calib.covered}/{calib.series} series "
             f"({calib.coverage:.0%}; target 65-95 %).")
    items = [
        (coverage, "S_CIF2024_REPORT"),
        (f"Diagnosis cannot be judged in {grey['diagnosis']} of {len(facts)} counties and timing (access times) in "
         f"{grey['timing']} of {len(facts)}: the data are not published by county.", SPEC),
        (glide, "S_CR_SCREENING_STATS"),
        (f"Twin sets are unstable (Jaccard below {bar:g}) in {unstable} of {len(result.twin_stability)} counties; "
         "twin gaps there deserve care.", "S_SOTKANET; S_STATFIN; S_WIKIDATA_UNIV_HOSPITALS"),
        ("Screening participation by mother tongue and education is "
         + ("published nationally only, so the outreach rule cannot be checked by county." if subgroup_units.empty
            else "published by county for some programmes."), "S_CR_SCREENING_STATS"),
        ("Early warning is not built: the frozen targets cannot be met with the public monthly series "
         "(evidence/step4/early_warning_feasibility.txt).", SPEC),
        ("Costs are national reference figures from the roadmap, not county budgets.", "S_ROADMAP"),
    ]
    if load_scope().secondary_cancer is None:
        items.append(("The second (screened) cancer is not chosen yet; lung is the anchor cancer.", SPEC))
    return items


def rehearse(runs: int = REHEARSAL_RUNS, counties=DEMO_COUNTIES) -> dict:
    """Spec Step 7: render the demo counties with the network blocked, `runs` times in a row, each run with
    fresh Streamlit caches, and check what the page itself says about its briefing."""
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    from equal_path.actions import run_actions
    from equal_path.analyst import validate

    run = run_actions()
    app = ROOT / "app" / "streamlit_app.py"
    cache = load_cache()
    report = {"runs": runs, "counties": list(counties), "validator_rejections": 0, "exceptions": 0,
              "not_from_cache": 0, "cache_entries_missing": sum(c not in cache for c in counties),
              "network_refusals": 0, "seconds": []}
    for _ in range(runs):
        st.cache_data.clear()
        for code in counties:
            started = time.perf_counter()
            with block_network() as block:
                at = AppTest.from_file(str(app), default_timeout=60)
                at.session_state["county"] = f"{code} {run.names[code]}"
                at.run()
            report["network_refusals"] += block.refused
            report["seconds"].append(round(time.perf_counter() - started, 2))
            report["exceptions"] += len(at.exception)
            facts, shown = select_briefing(code, run, cache)
            captions = " ".join(str(c.value) for c in at.caption if str(c.value).startswith("Written by"))  # the briefing's own
            on_page = [str(m.value) for m in at.markdown]
            rejected = (not validate(shown.text, facts).ok or "FAILED the number validator" in captions
                        or "passed the number validator" not in captions
                        or not all(line in on_page for line in shown.text.splitlines()))
            report["validator_rejections"] += int(rejected)
            report["not_from_cache"] += int(CACHE_NOTE not in captions)
    report["gate_met"] = (runs >= REHEARSAL_RUNS and report["exceptions"] == 0 and report["validator_rejections"] == 0
                          and report["not_from_cache"] == 0 and report["cache_entries_missing"] == 0)
    return report
