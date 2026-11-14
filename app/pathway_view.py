"""County pathway page (F1 visibility + F2 gap locator) and the all-counties overview."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from equal_path.visibility import COMPOSITE_STAGES, SEPARATE_STAGES

STAGES = COMPOSITE_STAGES + SEPARATE_STAGES
BADGE = {  # status colours always paired with a symbol and a word (never colour alone)
    "leak": ":red[▲ Leak]",
    "watch": ":orange[◆ Watch]",
    "ok": ":green[✓ OK]",
    "unknown": ":gray[○ Unknown]",
}
PERCENT_UNITS = ("share", "ratio")


def _pct(value) -> float | None:
    return None if value is None or pd.isna(value) else round(float(value) * 100, 1)


def _share_pct(value) -> float | None:
    """A projected share for display: capped to 0-100 % (a linear trend can extrapolate past 100 %)."""
    return None if value is None or pd.isna(value) else _pct(min(max(float(value), 0.0), 1.0))


def _share_interval(low, high) -> str:
    return "" if pd.isna(low) or pd.isna(high) else f"{_share_pct(low):.1f}–{_share_pct(high):.1f}"


def _better_label(better, state: str, names: dict) -> str:
    if state == "unknown":
        return ""
    if better is None:
        return "no twin data"
    return ", ".join(names.get(t, t) for t in better) if better else "leader among peers"


def _interval(interval) -> str:
    if interval is None or (isinstance(interval, float) and pd.isna(interval)):
        return "not published"
    low, high = interval
    return f"{low * 100:.1f}–{high * 100:.1f}"


def _county_options(units: pd.DataFrame) -> list[str]:
    return [f"{code} {name}" for code, name in zip(units["code"], units["short_fi"])]


def _scorecard(result, code: str) -> None:
    cols = st.columns(len(STAGES))
    for col, stage in zip(cols, STAGES):
        state = result.stages.loc[code, stage]
        visibility = result.visibility.loc[code, stage]
        note = "separate row (not in score)" if stage in SEPARATE_STAGES else f"visibility {visibility:.0%}"
        col.markdown(f"**{stage.capitalize()}**  \n{BADGE[state]}  \n{note}")


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


def pathway_section(data: dict) -> None:
    result, units = data["pathway"], data["units"]
    names = dict(zip(units["code"], units["short_fi"]))
    st.subheader("Pathway: where does it leak?")
    tabs = st.tabs(["County pathway", "All counties"])
    with tabs[0]:
        options = _county_options(units)
        choice = st.selectbox("County", options, index=options.index("90 Helsinki"))
        code = choice.split(" ", 1)[0]
        twins = result.twins[code]
        st.markdown(f"### {names[code]}")
        st.markdown(f"Visibility **{result.visibility.loc[code, 'score']:.1f}/100** · primary finding: "
                    f"**{result.primary_leak[code]}**")
        _scorecard(result, code)
        tier = result.coverage_tiers[code]
        st.caption(f"Stage-recording coverage tier: **{tier}**"
                   + ("" if tier != "not published" else " by county (national 41.9 %; only Pirkanmaa is stated in the report text)"))
        st.dataframe(_indicator_table(result, code, names), hide_index=True, width="stretch")
        st.caption("Leak = significant (Wilson interval or published CI) and ≥ 3 pp worse than the national value and the twin "
                   "median (national only when the county has no good twin; capped at Watch when fewer than 2 twins have data). "
                   "Significance is Bonferroni-adjusted within each stage so a stage's false-alarm rate stays ≤ 5 % "
                   f"(z: detection {result.z_by_stage['detection']:.2f}, treatment {result.z_by_stage['treatment']:.2f}); "
                   "the interval column is the test interval at that level, wider than the published 95 % CI. A stage "
                   "with visibility below 0.5 can never leak; without a published n or CI a gap can only be Watch.")
        typical = sorted(t.distances[0] for t in result.twins.values())[len(result.twins) // 2]
        stable = result.twin_stability[code]
        st.markdown("**Structural twins** · nearest twin distance "
                    f"{twins.distances[0]:.2f} (typical nearest-twin distance {typical:.2f}) · stability (Jaccard under "
                    f"±5 % covariate noise) {stable:.2f} "
                    + (":green[✓ stable]" if stable >= 0.6 else ":orange[◆ unstable: below 0.6, treat twin gaps with care]")
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
    with tabs[1]:
        st.dataframe(_overview(result, names), hide_index=True, width="stretch", height=35 * 23 + 3)
