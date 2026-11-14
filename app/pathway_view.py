"""County pathway page (F1 visibility + F2 gap locator) and the all-counties overview."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from equal_path.display import BADGE, interval_text, pct, share_interval, share_pct
from equal_path.visibility import COMPOSITE_STAGES, SEPARATE_STAGES

STAGES = COMPOSITE_STAGES + SEPARATE_STAGES
PERCENT_UNITS = ("share", "ratio")
_pct, _share_pct, _share_interval, _interval = pct, share_pct, share_interval, interval_text


def _better_label(better, state: str, names: dict) -> str:
    if state == "unknown":
        return ""
    if better is None:
        return "no twin data"
    return ", ".join(names.get(t, t) for t in better) if better else "leader among peers"


def _county_options(units: pd.DataFrame) -> list[str]:
    return [f"{code} {name}" for code, name in zip(units["code"], units["short_fi"])]


def _funnel(result, code: str, confidence: dict, reasons: dict) -> None:
    """The pathway as a funnel, left to right: state, how much is observable, how far to trust it."""
    cols = st.columns(len(STAGES))
    for col, stage in zip(cols, STAGES):
        state, visibility = result.stages.loc[code, stage], result.visibility.loc[code, stage]
        arrow = " →" if stage in COMPOSITE_STAGES[:-1] else ""
        note = "separate row (not in score)" if stage in SEPARATE_STAGES else "in the visibility score"
        col.markdown(f"**{stage.capitalize()}**{arrow}  \n{BADGE[state]}  \nvisibility {visibility:.0%} · {note}  \n"
                     f"confidence **{confidence[stage].level}**")
    for stage in STAGES:
        if confidence[stage].reasons and not reasons[stage]:
            st.caption(f"{stage.capitalize()} confidence {confidence[stage].level}: " + "; ".join(confidence[stage].reasons) + ".")
        if reasons[stage]:
            st.caption(f"○ {stage.capitalize()}: {reasons[stage]}")


def _indicator_table(result, code: str, names: dict) -> pd.DataFrame:
    rows = result.assessments[result.assessments.code == code]
    table = pd.DataFrame({
        "Stage": rows.stage,
        "Indicator": rows.indicator_id,
        "Series": rows.subgroup,
        "Period": rows.period,
        "Value (%)": [_pct(v) for v in rows.value],
        "Test interval at stage level (%)": [_interval(i) for i in rows.interval],
        "National (%)": [_pct(v) for v in rows.national],
        "Twin median (%)": [_pct(v) for v in rows.twin_median],
        "Gap vs national (pp)": [_pct(v) for v in rows.gap_national],
        "Gap vs twins (pp)": [_pct(v) for v in rows.gap_twin],
        "State": rows.state,
        "Better twins": [_better_label(b, s, names) for b, s in zip(rows.better_twins, rows.state)],
        "Why": rows.reason,
    })
    order = {stage: i for i, stage in enumerate(STAGES)}
    return table.sort_values(["Stage", "Indicator", "Series"], key=lambda s: s.map(order) if s.name == "Stage" else s)


def _twin_table(result, code: str, names: dict) -> pd.DataFrame:
    twins = result.twins[code]
    labels = {"cov_share_aged_75_plus": "aged 75+", "cov_education": "education", "cov_income": "income",
              "cov_population_density": "density", "cov_foreign_language_share": "foreign-language share",
              "cov_distance_university_hospital_km": "distance to university hospital"}
    return pd.DataFrame({
        "Twin": [f"{t} {names[t]}" for t in twins.twins],
        "Distance": [round(d, 2) for d in twins.distances],
        "Most similar on": [", ".join(labels[c] for c in drivers[:2]) for drivers in twins.drivers],
    })


def _overview(result, names: dict) -> pd.DataFrame:
    frame = pd.DataFrame({
        "Code": result.stages.index,
        "Unit": [names[c] for c in result.stages.index],
        "Visibility score": result.visibility.score.round(1).values,
    })
    for stage in STAGES:
        frame[stage.capitalize()] = result.stages[stage].values
    frame["Twin stability"] = [round(result.twin_stability[c], 2) for c in result.stages.index]
    frame["Primary finding"] = [result.primary_leak[c] for c in result.stages.index]
    frame["Twins"] = [", ".join(names[t] for t in result.twins[c].twins) + ("" if result.twins[c].good else " (no good twin)")
                      for c in result.stages.index]
    return frame


def _glidepath(data: dict, code: str) -> None:
    paths = data["glidepaths"]
    calib = data["calibration"]
    rows = paths[paths.code == code]
    table = pd.DataFrame({
        "Programme": rows.programme,
        "Years": rows.years,
        "Latest (%)": [_pct(v) for v in rows.latest],
        "Trend (pp/yr)": [_pct(v) for v in rows.slope],
        "Needed (pp/yr)": [_pct(v) for v in rows.required_slope],
        "Trend line 2035 (%)": [_share_pct(v) for v in rows.point_projection],
        "Bootstrap median 2035 (%)": [_share_pct(v) for v in rows.projection],
        "80 % interval (%)": [_share_interval(lo, hi) for lo, hi in zip(rows.low, rows.high)],
        "State": rows.state,
    })
    st.markdown("**Glidepath to 80 % screening participation by 2035**")
    st.dataframe(table, hide_index=True, width="stretch")
    st.caption(f"Theil–Sen trend over the published years with a bootstrap 80 % interval. Labelled **{calib.label}**: "
               f"held-out-year calibration covered {calib.covered}/{calib.series} series ({calib.coverage:.0%}; target 65–95 %). "
               "Five annual points (2020 is a pandemic year); colorectal has three, so no glidepath yet. "
               "'On track' needs both the trend line and the bootstrap median to reach 80 % by 2035; "
               "projections are shown capped at 100 %.")


@st.cache_data(max_entries=64, show_spinner="Writing the briefing...")
def _cached_claude_briefing(facts_json: str):
    """Claude briefings only: a template caused by a transient error is never cached (review G-3)."""
    import json

    from equal_path.analyst import generate_briefing

    briefing = generate_briefing(json.loads(facts_json))
    if briefing.source != "claude":
        raise RuntimeError(briefing.note)   # st.cache_data does not cache a raised call
    return briefing


def _briefing(data: dict, code: str) -> None:
    """F7: a validated briefing of at most 120 words; every number carries its source tag. Same selection as
    the trust panel: a current cache entry first (offline mode), else live Claude, else the template."""
    import json

    from equal_path.analyst import Briefing, answer_access_time, briefing_facts, make_client, template_briefing, validate
    from equal_path.hardening import CACHE_NOTE, select_briefing

    facts, briefing = select_briefing(code, data["actions"])
    if CACHE_NOTE not in briefing.note and make_client() is not None:   # no current cache entry: try live Claude
        try:
            briefing = _cached_claude_briefing(json.dumps(facts, sort_keys=True))
        except RuntimeError as exc:
            briefing = Briefing(template_briefing(briefing_facts(code, data["actions"])), "template", 0, note=str(exc))
    st.markdown("#### Analyst briefing")
    for line in briefing.text.splitlines():
        st.markdown(line)
    checked = validate(briefing.text, facts)
    origin = (f"Claude ({briefing.model or 'unknown model'})" if briefing.source == "claude" else "the deterministic template")
    origin += f" ({briefing.note})" if briefing.note else ""
    status = ("passed the number validator: every number matches a computed figure and carries its source id"
              if checked.ok else "FAILED the number validator: " + "; ".join(checked.problems))
    st.caption(f"Written by {origin}; {status}.")
    st.caption(answer_access_time(facts))


RULE_STATUS = {"fires": "fires", "not triggered": "not triggered", "needs data": "needs data", "blocked": "blocked (visibility)"}


def _action_card(data: dict, code: str):
    """F5 top actions as the printable Action Card: the screen shows exactly the PDF's lines."""
    from equal_path.card import build_card, render_pdf

    run = data["actions"]
    from datetime import date

    card = build_card(code, run, date.today().isoformat())   # per view, not cached at app start (review W-1)
    with st.container(border=True):   # the same lines, in the same order, as the PDF
        st.markdown(f"#### {card.title}")
        st.caption(card.subtitle)
        for title, lines in card.sections:
            st.markdown(f"**{title}**")
            for line in lines:
                st.markdown(line.text)
        st.caption(card.footer)
    st.download_button("Download Action Card (PDF, one page)", data=render_pdf(card), mime="application/pdf",
                       file_name=f"equal-path-action-card-{code}.pdf")
    with st.expander("All rules for this county (F5)", expanded=False):
        rules = {r.id: r for r in data["rules"]}
        st.dataframe(pd.DataFrame({
            "Rule": [o.rule_id for o in run.plans[code].outcomes],
            "Stage": [rules[o.rule_id].stage for o in run.plans[code].outcomes],
            "Status": [RULE_STATUS[o.status] for o in run.plans[code].outcomes],
            "Needs data": ["; ".join(o.missing) for o in run.plans[code].outcomes],
        }), hide_index=True, width="stretch")
    return card


def pathway_section(data: dict) -> None:
    from equal_path.confidence import county_confidence, stage_reason
    from equal_path.display import national_value, typical_twin_distance
    from equal_path.drawer import county_figures

    result, units, thresholds = data["pathway"], data["units"], data["threshold_model"]
    names = dict(zip(units["code"], units["short_fi"]))
    catalog = {i.id: i for i in data["catalog"]}
    st.subheader("Pathway: where does it leak?")
    tabs = st.tabs(["County pathway", "All counties"])
    with tabs[0]:
        options = _county_options(units)
        st.session_state.setdefault("county", "90 Helsinki")  # a map click sets this key (see map_and_units)
        choice = st.selectbox("County", options, key="county")
        code = choice.split(" ", 1)[0]
        twins = result.twins[code]
        st.markdown(f"### {names[code]}")
        st.markdown(f"Visibility **{result.visibility.loc[code, 'score']:.1f}/100** · primary finding: "
                    f"**{result.primary_leak[code]}**")
        confidence = county_confidence(result, code, thresholds)
        reasons = {stage: stage_reason(result, data["store"], catalog, code, stage, thresholds.min_stage_visibility)
                   for stage in STAGES}
        _funnel(result, code, confidence, reasons)
        tier = result.coverage_tiers[code]
        national = national_value(data["store"], "stage_recording_coverage")
        st.caption(f"Stage-recording coverage tier: **{tier}**"
                   + ("" if tier != "not published" or national is None else
                      f" by county (national {pct(national)} %; only Pirkanmaa is stated in the report text)"))
        st.dataframe(_indicator_table(result, code, names), hide_index=True, width="stretch")
        st.caption("Leak = significant (Wilson interval or published CI) and ≥ 3 pp worse than the national value and the twin "
                   "median (national only when the county has no good twin; capped at Watch when fewer than 2 twins have data). "
                   "Significance is Bonferroni-adjusted within each stage so a stage's false-alarm rate stays ≤ 5 % "
                   f"(z: detection {result.z_by_stage['detection']:.2f}, treatment {result.z_by_stage['treatment']:.2f}); "
                   "the interval column is the test interval at that level, wider than the published 95 % CI. A stage "
                   f"with visibility below {thresholds.min_stage_visibility:g} can never leak; without a published n or CI "
                   "a gap can only be Watch.")
        typical = typical_twin_distance(result.twins)
        stable, bar = result.twin_stability[code], thresholds.twin_stability_jaccard
        st.markdown("**Structural twins** · nearest twin distance "
                    f"{twins.distances[0]:.2f} (typical nearest-twin distance {typical:.2f}) · stability (Jaccard under "
                    f"±5 % covariate noise) {stable:.2f} "
                    + (":green[✓ stable]" if stable >= bar else f":orange[◆ unstable: below {bar:g}, treat twin gaps with care]")
                    + ("" if twins.good else " · :orange[no good twin: national reference only]"))
        st.dataframe(_twin_table(result, code, names), hide_index=True, width="stretch")
        st.caption("Twins: 3 nearest on 6 structural covariates (aged 75+, education, income, log density, foreign-language "
                   "share, log distance to a university hospital); outcomes never enter the distance. Twin plausibility "
                   "still needs a human review (spec F3: 18/22 by the team, 3 pairs by a mentor).")
        _glidepath(data, code)
        st.caption("Tipping point (§7.4) not computable: the stage I–II distribution is published nationally only, "
                   "not by county or cooperation area.")
        st.caption("Early warning (F4) not built: the frozen targets (≥ 90 % detection of a 1 SD step within 6 months at "
                   "≤ 5 % false alarms a year) cannot both be met; the best one-sided CUSUM reaches 51 % detection at 5 % false "
                   "alarms, and no test can exceed 79 %. See evidence/step4/early_warning_feasibility.txt.")
        _briefing(data, code)
        card = _action_card(data, code)
        with st.expander("Sources drawer: every figure on this page, with its source and locator", expanded=False):
            st.dataframe(county_figures(code, result, data["store"], catalog, data["glidepaths"], data["calibration"],
                                        thresholds, card=card), hide_index=True, width="stretch")
    with tabs[1]:
        st.dataframe(_overview(result, names), hide_index=True, width="stretch", height=35 * 23 + 3)
