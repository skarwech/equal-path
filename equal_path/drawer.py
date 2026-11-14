"""F8 sources drawer: every figure on a county page, as data, with its source and locator or derivation.

Pure data (no Streamlit) so the AI analyst's number validator (F7) and the Action Card can reuse it.
Raw values cite the store row's source and locator; computed figures name their method and the
sources of their inputs; rule constants cite the frozen threshold register (S_EQUAL_PATH_SPEC).
"""

from __future__ import annotations

import re

import pandas as pd

from equal_path.confidence import county_confidence, stage_reason
from equal_path.display import STATE_WORD, interval_text, national_row, pct, share_interval, share_pct, typical_twin_distance
from equal_path.gaps import MIN_TWIN_VALUES
from equal_path.glidepath import PROGRAMMES
from equal_path.visibility import COMPOSITE_STAGES, SEPARATE_STAGES, stage_members

DRAWER_COLUMNS = ("Section", "Figure", "Shown", "Period", "Sources", "Locator or derivation")
SPEC = "S_EQUAL_PATH_SPEC"
COVARIATE_SOURCES = "S_SOTKANET; S_STATFIN; S_WIKIDATA_UNIV_HOSPITALS"
_NUMBER = re.compile(r"(?<![\w.])[-−]?\d+(?:\.\d+)?")


def numbers_in(text: str) -> set[float]:
    """Numbers as a reader sees them: signs (incl. U+2212), decimals; '2019-2023' is two years, not a minus."""
    return {round(float(m.replace("−", "-")), 6) for m in _NUMBER.findall(str(text))}


def _fmt(value) -> str:
    return "" if value is None else f"{value}"


def _sources(catalog, ids) -> str:
    """Sources of the indicators a figure is computed from; never falls back to the rule register (review G-5)."""
    found = sorted({s for i in ids if i in catalog for s in catalog[i].source_ids})
    if not found:
        raise ValueError(f"no catalog sources for {sorted(ids)}")
    return "; ".join(found)


def _present(value) -> bool:
    return value is not None and not pd.isna(value)


def _store_row(store, indicator, code, period, subgroup, level="unit"):
    rows = store[(store.indicator_id == indicator) & (store.county_id == code) & (store.period == period)
                 & (store.subgroup == subgroup) & (store.geo_level == level)]
    return rows.iloc[0] if len(rows) else None


def _header_and_funnel(code, result, store, catalog, thresholds) -> list[tuple]:
    members = stage_members(catalog)
    observed = {s: [m for m in members[s] if m in result.observable.columns and bool(result.observable.loc[code, m])]
                for s in members}
    composite = [m for s in COMPOSITE_STAGES for m in members[s]]
    leaks = result.assessments[(result.assessments.code == code) & (result.assessments.state == "leak")]
    rows = [("Header", "Visibility score", f"{result.visibility.loc[code, 'score']:.1f}/100", "", _sources(catalog, composite),
             "F1: mean of the four stage shares (weights 0.25) of observable indicators; observable = latest "
             "period, headline series, n >= 30, registered source"),
            ("Header", "Primary finding", result.primary_leak[code], "",
             _sources(catalog, list(leaks.indicator_id) or composite),
             "F2: largest verified gap (the smaller of the national and twin gaps) among Leak stages")]
    confidence = county_confidence(result, code, thresholds)
    for stage in COMPOSITE_STAGES + SEPARATE_STAGES:
        name, vis = stage.capitalize(), float(result.visibility.loc[code, stage])
        state = result.stages.loc[code, stage]
        level = confidence[stage]
        rows += [
            ("Funnel", f"{name} · state", STATE_WORD[state], "", _sources(catalog, members[stage]),
             "F2 stage rule over this stage's indicator states (gap locator output)"),
            ("Funnel", f"{name} · visibility", f"{vis:.0%}", "", _sources(catalog, members[stage]),
             f"{len(observed[stage])} of {len(members[stage])} indicators observable"),
            ("Funnel", f"{name} · confidence", level.level + (": " + "; ".join(level.reasons) if level.reasons else ""), "",
             SPEC, f"confidence rule (frozen thresholds: min_stage_visibility {thresholds.min_stage_visibility:g}, "
                   f"twin_stability_jaccard {thresholds.twin_stability_jaccard:g})"),
        ]
        reason = stage_reason(result, store, catalog, code, stage, thresholds.min_stage_visibility)
        if reason:
            rows.append(("Funnel", f"{name} · why grey", reason, "", _sources(catalog, members[stage]),
                         "catalog status and unit-level coverage of each indicator"))
    coverage = national_row(store, "stage_recording_coverage")
    if coverage is not None:
        rows.append(("Funnel", "National stage-recording coverage", f"{pct(coverage.value)} %", coverage.period,
                     coverage.source_id, coverage.locator))
    return rows


def _national_published(store, catalog, indicator, period, subgroup):
    """The national row F2 used, selected exactly as pathway.eligible_series does (review P-7)."""
    rows = store[(store.indicator_id == indicator) & (store.geo_level == "national") & (store.period == period)
                 & (store.subgroup == subgroup) & store.value.notna() & store.source_id.isin(catalog[indicator].source_ids)]
    return rows.iloc[0] if len(rows) == 1 else None


def _twins_used(code, result, store, indicator, period, subgroup, min_denominator):
    """The twins whose values entered the twin median, as gaps.assess_series selects them (review P-4)."""
    rows = store[(store.indicator_id == indicator) & (store.period == period) & (store.subgroup == subgroup)
                 & (store.geo_level == "unit") & store.value.notna()].set_index("county_id")
    used = [t for t in result.twins[code].twins
            if t in rows.index and bool(result.observable.loc[t, indicator])
            and (pd.isna(rows.denominator[t]) or rows.denominator[t] >= min_denominator)]
    return used, any(pd.notna(rows.denominator[t]) for t in used)


def _indicators(code, result, store, catalog, min_denominator) -> list[tuple]:
    rows = []
    part = result.assessments[result.assessments.code == code]
    for a in part.itertuples(index=False):
        key, src = f"{a.indicator_id} ({a.subgroup})", _sources(catalog, [a.indicator_id])
        row = _store_row(store, a.indicator_id, code, a.period, a.subgroup)
        if _present(a.value) and row is not None:
            rows.append(("Indicators", f"{key} · value", f"{pct(a.value)}", a.period, row.source_id, row.locator))
            if pd.notna(row.denominator):
                rows.append(("Indicators", f"{key} · n", f"{row.denominator:.0f}", a.period, row.source_id, row.locator))
        if isinstance(a.interval, tuple):
            how = ("published 95 % CI widened to the stage z" if row is not None and pd.notna(row.ci_low)
                   else "Wilson interval from n at the stage z")
            rows.append(("Indicators", f"{key} · test interval", interval_text(a.interval), a.period, src, how))
        if _present(a.national):
            nat = _national_published(store, catalog, a.indicator_id, a.period, a.subgroup)
            rows.append(("Indicators", f"{key} · national", f"{pct(a.national)}", a.period,
                         nat.source_id if nat is not None else src,
                         nat.locator if nat is not None else "pooled over all unit rows, weighted by n"))
        if _present(a.twin_median):
            used, with_n = _twins_used(code, result, store, a.indicator_id, a.period, a.subgroup, min_denominator)
            rows.append(("Indicators", f"{key} · twin median", f"{pct(a.twin_median)}", a.period, src,
                         f"median of the twins' values (units {', '.join(used)})"
                         + (f" with n >= {min_denominator:g}" if with_n else "")))
        for label, gap in (("gap vs national", a.gap_national), ("gap vs twins", a.gap_twin)):
            if _present(gap):
                rows.append(("Indicators", f"{key} · {label}", f"{pct(gap)}", a.period, src,
                             "difference in percentage points, signed so positive = worse"))
        if any(ch.isdigit() for ch in str(a.reason)):
            rows.append(("Indicators", f"{key} · why", str(a.reason), a.period, src, "F2 rule"))
    return rows


def _twins(code, result) -> list[tuple]:
    twins = result.twins[code]
    how = "z-scored Euclidean distance on 6 structural covariates (log density, log1p distance)"
    rows = [("Twins", "Nearest twin distance", f"{twins.distances[0]:.2f}", "", COVARIATE_SOURCES, how),
            ("Twins", "Typical nearest-twin distance", f"{typical_twin_distance(result.twins):.2f}", "", COVARIATE_SOURCES,
             "median over the 22 units of each unit's nearest-twin distance"),
            ("Twins", "Twin stability", f"{result.twin_stability[code]:.2f}", "", COVARIATE_SOURCES,
             "mean Jaccard overlap of twin sets under ±5 % covariate noise (200 draws, fixed seed)")]
    rows += [("Twins", f"Twin {t} · distance", f"{round(d, 2)}", "", COVARIATE_SOURCES, how)
             for t, d in zip(twins.twins, twins.distances)]
    return rows


def _glidepaths(code, store, glidepaths) -> list[tuple]:
    rows = []
    for g in glidepaths[glidepaths.code == code].itertuples(index=False):
        series = store[(store.indicator_id == PROGRAMMES[g.programme]) & (store.county_id == code)
                       & (store.geo_level == "unit") & (store.subgroup == "all") & store.value.notna()]
        ordered, src = series.sort_values("period"), "S_CR_SCREENING_STATS"
        fit = "Theil-Sen over the published years; bootstrap 2,000 draws, fixed seed, 80 % interval"
        goal = f"{src}; S_STRATEGY"
        shown = [("latest", _fmt(pct(g.latest)), ordered.locator.iloc[-1], src),
                 ("trend (pp/yr)", _fmt(pct(g.slope)), " | ".join(ordered.locator), src),
                 ("needed (pp/yr)", _fmt(pct(g.required_slope)), "(80 % goal - latest) / (2035 - latest year)", goal),
                 ("trend line 2035", _fmt(share_pct(g.point_projection)), fit, src),
                 ("bootstrap median 2035", _fmt(share_pct(g.projection)), fit, src),
                 ("80 % interval", share_interval(g.low, g.high), fit, src)]
        rows += [("Glidepath", f"{g.programme} · {label}", value, g.years, cite, how)
                 for label, value, how, cite in shown if value not in ("", "None", "nan")]
    return rows


def _method(result, calib, thresholds) -> list[tuple]:
    z = result.z_by_stage
    return [
        ("Method", "Leak rule", f"significant at the stage's Bonferroni z (Wilson interval from n, or the published "
         f"95 % CI widened) and ≥ {thresholds.min_practical_gap_pp:g} pp worse; false-alarm rate ≤ "
         f"{thresholds.false_leak_rate_max:.0%} per stage", "", SPEC, "F2 thresholds (frozen) and equal_path/gaps.py"),
        ("Method", "Stage z (Bonferroni)", f"detection {z['detection']:.2f}, treatment {z['treatment']:.2f}", "", SPEC,
         "within-stage Bonferroni on the 1.96 base"),
        ("Method", "Visibility gate", f"{thresholds.min_stage_visibility:g} ({thresholds.min_stage_visibility:.0%})", "",
         SPEC, "below this a stage can never leak"),
        ("Method", "References", f"twin median needs ≥ {MIN_TWIN_VALUES} twins with values; "
         f"n ≥ {thresholds.min_denominator:g}", "", SPEC,
         "min_denominator: frozen register; minimum twins: method constant MIN_TWIN_VALUES in equal_path/gaps.py"),
        ("Method", "Twins", f"{thresholds.twin_k} nearest on 6 structural covariates (aged 75+, education, income, "
         "density, foreign-language share, distance to a university hospital)", "", COVARIATE_SOURCES, "F3"),
        ("Method", "Twin stability bar", f"±{thresholds.twin_noise_fraction:.0%} noise; stable at ≥ "
         f"{thresholds.twin_stability_jaccard:g}", "", SPEC, "F3 (frozen)"),
        ("Method", "Twin review still open", "18/22 by the team, 3 pairs by a mentor", "", SPEC, "spec F3 acceptance"),
        ("Method", "Glidepath target", "80 % participation by 2035; projections capped at 100 %; 2020 is a pandemic year",
         "", f"S_STRATEGY; {SPEC}", "national goal of at least 80 % participation in every county (config/scope.yaml)"),
        ("Method", "Glidepath calibration", f"{calib.covered}/{calib.series} series ({calib.coverage:.0%}); "
         "target 65–95 %", "2020-2024", "S_CR_SCREENING_STATS", "held-out last year, 80 % interval"),
        ("Method", "Tipping point", "spec §7.4; stage I–II not published by county", "", SPEC, "not computable"),
        ("Method", "Early warning", "target ≥ 90 % detection of a 1 SD step within 6 months at ≤ 5 % false alarms a year; "
         "best CUSUM 51 % at 5 %; no test above 79 %", "", SPEC, "evidence/step4/early_warning_feasibility.txt"),
    ]


def _card_rows(card) -> list[tuple]:
    rows = [("Action Card", "Card title", card.title, "", SPEC, "equal_path/card.py"),
            ("Action Card", "Card date", card.subtitle, "", SPEC, "generation date")]
    for title, lines in card.sections:
        rows += [("Action Card", f"{title} · line {i}", line.text, "", line.sources, line.locator)
                 for i, line in enumerate(lines, start=1)]
    return rows


def county_figures(code: str, result, store: pd.DataFrame, catalog: dict, glidepaths: pd.DataFrame, calib,
                   thresholds, card=None) -> pd.DataFrame:
    rows = (_header_and_funnel(code, result, store, catalog, thresholds)
            + _indicators(code, result, store, catalog, thresholds.min_denominator)
            + _twins(code, result) + _glidepaths(code, store, glidepaths) + _method(result, calib, thresholds)
            + (_card_rows(card) if card is not None else []))
    return pd.DataFrame(rows, columns=list(DRAWER_COLUMNS))
