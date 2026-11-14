"""Step 8 hardening: offline analyst cache, network blocking, trust / data-gap / limitations content, rehearsal.

Offline mode (spec F8): every county's briefing is cached in data/processed/briefings.json with the hash of the
facts it was written from. The app shows a cached briefing only if the hash still matches and the text passes
the number validator, so a stale or edited cache can never show an unsupported number.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import socket
import time
from datetime import date
from pathlib import Path

import pandas as pd

from equal_path.paths import DATA_DIR, ROOT

BRIEFINGS_FILE = DATA_DIR / "processed" / "briefings.json"
DEMO_COUNTIES = ("10", "14", "90")   # treatment + detection leak; detection leak; capital, no verified gap
SPEC = "S_EQUAL_PATH_SPEC"


def facts_hash(facts: dict) -> str:
    return hashlib.sha256(json.dumps(facts, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def load_cache(path: Path = BRIEFINGS_FILE) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def cached_briefing(facts: dict, cache: dict, code: str):
    """The cached Briefing, only if written from these exact facts and still passing the validator."""
    from equal_path.analyst import Briefing, validate

    entry = cache.get(code)
    if not entry or entry.get("facts_hash") != facts_hash(facts) or not validate(entry["text"], facts).ok:
        return None
    return Briefing(entry["text"], entry["source"], 0, note=f"from the offline cache, generated {entry['generated_on']}",
                    model=entry.get("model", ""))


def build_briefing_cache(run, today: str | None = None, path: Path = BRIEFINGS_FILE) -> dict:
    """One validated briefing per county (Claude when available, else the template), written to the cache."""
    from equal_path.analyst import briefing_facts, generate_briefing, validate

    cache = {}
    for code in sorted(run.plans):
        facts = briefing_facts(code, run)
        briefing = generate_briefing(facts)
        if not validate(briefing.text, facts).ok:
            raise ValueError(f"{code}: briefing failed the validator; not cached")
        cache[code] = {"facts_hash": facts_hash(facts), "text": briefing.text, "source": briefing.source,
                       "model": briefing.model, "generated_on": today or date.today().isoformat()}
    path.write_text(json.dumps(cache, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return cache


@contextlib.contextmanager
def block_network():
    """Every outbound connection and DNS lookup raises, as with the network disabled."""
    def refuse(*args, **kwargs):
        raise OSError("network blocked (offline mode)")

    saved = socket.socket.connect, socket.getaddrinfo, socket.create_connection
    socket.socket.connect, socket.getaddrinfo, socket.create_connection = refuse, refuse, refuse
    try:
        yield
    finally:
        socket.socket.connect, socket.getaddrinfo, socket.create_connection = saved


def displayed_briefing(code: str, run, cache: dict | None = None):
    """What the county page shows: cached text if current and valid, else the deterministic template."""
    from equal_path.analyst import Briefing, briefing_facts, template_briefing

    facts = briefing_facts(code, run)
    found = cached_briefing(facts, load_cache() if cache is None else cache, code)
    return facts, found or Briefing(template_briefing(facts), "template", 0, note="no current cache entry")


def trust_figures(reconciliation, run, summary) -> dict:
    """Spec F8 Trust panel, computed from the actual runs: anchors, tests, and briefings checked."""
    from equal_path.analyst import validate

    cache = load_cache()
    checks = [validate(b.text, f) for f, b in (displayed_briefing(c, run, cache) for c in sorted(run.plans))]
    return {
        "anchors_passed": sum(r.status == "pass" for r in reconciliation),
        "anchors_checked": sum(r.status in ("pass", "fail") for r in reconciliation),
        "tests_passed": getattr(summary, "passed", 0), "tests_total": getattr(summary, "total", 0),
        "briefings": len(checks), "briefings_passed": sum(c.ok for c in checks),
        "unsupported_numbers_shown": sum(1 for c in checks for p in c.problems if "number" in p),
    }


def data_gaps(catalog, store: pd.DataFrame) -> pd.DataFrame:
    """Spec Step 6 data-gap panel: every catalog indicator that is not available for all 22 units."""
    units = store[(store.geo_level == "unit") & store.value.notna()]
    rows = []
    for item in catalog:
        if item.status == "available":
            continue
        n = units.loc[units.indicator_id == item.id, "county_id"].nunique()
        rows.append({"Stage": item.stage, "Indicator": item.id, "Label": item.label, "Status": item.status,
                     "Units with a value": f"{n} of 22", "Why": item.limitation})
    order = {s: i for i, s in enumerate(("detection", "referral", "diagnosis", "treatment", "timing", "context"))}
    return pd.DataFrame(rows).sort_values(["Stage", "Indicator"], key=lambda s: s.map(order) if s.name == "Stage" else s)


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
    scope = load_scope()
    items = [
        (f"{_list(own)} {'has its' if len(own) == 1 else 'have their'} own stage-recording figure; the other "
         f"{len(facts) - len(own)} counties use the cooperation-area or national figure "
         f"({national_value(store, 'stage_recording_coverage') * 100:.1f} % nationally).",
         "S_CIF2024_REPORT"),
        (f"Diagnosis cannot be judged in {grey['diagnosis']} of {len(facts)} counties and timing (access times) in "
         f"{grey['timing']} of {len(facts)}: the data are not published by county.", SPEC),
        (f"Glidepaths are indicative: held-out-year calibration covered {calib.covered}/{calib.series} series "
         f"({calib.coverage:.0%}; target 65-95 %).", "S_CR_SCREENING_STATS"),
        (f"Twin sets are unstable (Jaccard below {bar:g}) in {unstable} of {len(result.twin_stability)} counties; "
         "twin gaps there deserve care.", "S_SOTKANET; S_STATFIN; S_WIKIDATA_UNIV_HOSPITALS"),
        ("Screening participation by mother tongue and education is "
         + ("published nationally only, so the outreach rule cannot be checked by county." if subgroup_units.empty
            else "published by county for some programmes."), "S_CR_SCREENING_STATS"),
        ("Early warning is not built: the frozen targets cannot be met with the public monthly series "
         "(evidence/step4/early_warning_feasibility.txt).", SPEC),
        ("Costs are national reference figures from the roadmap, not county budgets.", "S_ROADMAP"),
    ]
    if scope.secondary_cancer is None:
        items.append(("The second (screened) cancer is not chosen yet; lung is the anchor cancer.", SPEC))
    return items


def _list(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def rehearse(runs: int = 5, counties=DEMO_COUNTIES) -> dict:
    """Spec Step 7 rehearsal: render the demo counties with the network blocked, `runs` times in a row."""
    from streamlit.testing.v1 import AppTest

    from equal_path.analyst import validate
    from equal_path.actions import run_actions

    run = run_actions()
    app = ROOT / "app" / "streamlit_app.py"
    report = {"runs": runs, "counties": list(counties), "validator_rejections": 0, "exceptions": 0,
              "network_blocked": True, "seconds": []}
    for _ in range(runs):
        for code in counties:
            started = time.perf_counter()
            with block_network():
                at = AppTest.from_file(str(app), default_timeout=60)
                at.session_state["county"] = f"{code} {run.names[code]}"
                at.run()
            report["seconds"].append(round(time.perf_counter() - started, 2))
            report["exceptions"] += len(at.exception)
            facts, shown = displayed_briefing(code, run)
            on_page = [str(m.value) for m in at.markdown]
            report["validator_rejections"] += int(not validate(shown.text, facts).ok
                                                  or not all(line in on_page for line in shown.text.splitlines()))
    return report
