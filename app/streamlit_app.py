"""Equal Path app: data spine, county pathway (F1 visibility, F2 gaps, F3 twins, F4 glidepath) and config."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from equal_path.config import (  # noqa: E402
    load_anchors,
    load_indicator_catalog,
    load_reference_times,
    load_rules,
    load_scope,
    load_thresholds,
    threshold_provenance,
    thresholds_are_frozen,
    thresholds_digest,
)
from equal_path.geography import load_unit_geojson, load_units  # noqa: E402
from equal_path.map_layers import LAYERS, handle_map_event, layer_frame, layer_table  # noqa: E402
from app.pathway_view import pathway_section  # noqa: E402
from equal_path.coverage import LEGEND, coverage_matrix  # noqa: E402
from equal_path.glidepath import calibration, run_glidepaths  # noqa: E402
from equal_path.pathway import run_pathway  # noqa: E402
from equal_path.observations import indicator_counts, load_observations, reconcile_anchors  # noqa: E402
from equal_path.paths import APP_INPUTS, ROOT, STALENESS_WATCHED, TEST_FINGERPRINT, TEST_REPORT  # noqa: E402
from equal_path.sources import load_sources  # noqa: E402
from equal_path.trust import fingerprint_is_current, input_stamp, read_test_summary  # noqa: E402
from equal_path.viz import MAP_CONFIG, unit_map_figure  # noqa: E402

NO_AREA = "None (all units neutral)"

st.set_page_config(page_title="Equal Path", page_icon="🧭", layout="wide")


@st.cache_data(max_entries=4)
def load_everything(stamp: tuple) -> dict:
    """Validated config and reference data. `stamp` (file name, mtime, size) keys the cache,
    so an edit to any input reloads it instead of serving a stale copy."""
    del stamp  # only used as the cache key
    counts = indicator_counts()
    units = load_units()
    units = units.assign(
        municipality_count=units["municipality_count"].astype(int),
        indicators_loaded=[counts.get(code, 0) for code in units["code"]],
    )
    store = load_observations()
    thresholds = load_thresholds()
    anchors = load_anchors()
    return {
        "pathway": run_pathway(store),
        "glidepaths": run_glidepaths(store),
        "calibration": calibration(store),
        "store": store,
        "catalog": load_indicator_catalog(),
        "reconciliation": reconcile_anchors(store, anchors, thresholds),
        "counts": counts,
        "units": units,
        "geojson": load_unit_geojson(),
        "sources": load_sources(),
        "thresholds": thresholds.model_dump(),
        "threshold_model": thresholds,
        "scope": load_scope(),
        "rules": load_rules(),
        "anchors": anchors,
        "times": load_reference_times(),
    }


def header(data: dict) -> None:
    st.title("Equal Path")
    st.caption("Equitable and effective cancer care in Finland · Step 5: interface (map layers, funnel, sources drawer)")
    counts = data["counts"]
    if not counts:
        st.info(
            "**No indicator data loaded yet.** This view shows the 22-unit geography, the frozen "
            "thresholds and the scope (second cancer pending). Nothing on this page is synthetic.",
            icon="ℹ️",
        )
        return
    loaded = data["store"].loc[data["store"].value.notna(), "indicator_id"].nunique()
    st.info(
        f"**Data spine: {loaded} of {len(data['catalog'])} catalogued indicators have public values; "
        f"{len(counts)} of 22 units have at least one.** Gaps are shown, never filled. "
        "Scope: lung anchor, second cancer pending. Nothing on this page is synthetic.",
        icon="ℹ️",
    )


def metrics_row(data: dict) -> None:
    # Computed on every run (not cached) so an edit to thresholds or lock shows at once.
    frozen = thresholds_are_frozen()
    summary = read_test_summary(TEST_REPORT)
    cols = st.columns(5)
    drawn = {f["properties"]["code"] for f in data["geojson"]["features"]} & set(data["units"]["code"])
    cols[0].metric("Units on map", f"{len(drawn)} / {data['scope'].unit_count}")
    cols[1].metric("Cooperation areas", data["units"]["coop_area_fi"].nunique())
    cols[2].metric("Thresholds", "Frozen" if frozen else "NOT FROZEN")
    cols[2].caption(f"sha256 `{thresholds_digest()[:12]}`" if frozen else ":red[edited after freeze, draft, or lock missing]")
    cols[3].metric("Action rules", len(data["rules"]))
    if summary is None:
        cols[4].metric("Tests", "not run")
        cols[4].caption("Run pytest with --junitxml=evidence/test_report.xml")
    else:
        cols[4].metric("Tests passing", f"{summary.passed} / {summary.total}")
        if summary.total == 0:
            status = ":orange[no tests ran]"
        elif summary.all_green:
            status = ":green[all green]"
        else:
            status = f":red[{summary.failed} failing]"
        current = fingerprint_is_current(TEST_FINGERPRINT, STALENESS_WATCHED, root=ROOT, report=TEST_REPORT)
        stale = "" if current else " · :orange[stale: not a full run, or code/data changed since]"
        cols[4].caption(f"{status} · run {summary.timestamp[:16].replace('T', ' ')}{stale}")


def map_and_units(data: dict) -> None:
    units = data["units"]
    left, right = st.columns([3, 2], gap="large")
    with right:
        areas = [NO_AREA, *sorted(units["coop_area_fi"].unique())]
        choice = st.selectbox("Highlight a cooperation area", areas, index=0)
        highlight = None if choice == NO_AREA else choice
        layer = st.selectbox("Map layer", LAYERS, index=LAYERS.index("Detection"))
        frame = layer_frame(data["pathway"], layer, data["threshold_model"].min_stage_visibility)
        table = layer_table(units, frame, layer)
        if highlight:
            table = table[table["Cooperation area"] == highlight]
        row_height = 35
        st.dataframe(table, hide_index=True, width="stretch", height=row_height * (len(table) + 1) + 3)
        st.caption(LAYER_LEGEND[layer == "Visibility score"])
        st.caption("Source: Statistics Finland classifications and boundaries 2026 (see Sources tab).")
    with left:
        nonce = st.session_state.setdefault("_map_nonce", 0)
        event = st.plotly_chart(
            unit_map_figure(units, data["geojson"], highlight_area=highlight, layer=frame, layer_name=layer),
            width="stretch", config=MAP_CONFIG, on_select="rerun", selection_mode="points", key=f"map_{nonce}",
        )
        labels = {code: f"{code} {name}" for code, name in zip(units["code"], units["short_fi"])}
        if handle_map_event(st.session_state, event, labels):
            st.rerun()  # re-draw with a fresh chart, so the next click is a new selection
        st.caption("Click a county to open its pathway below. Dragging pans the map; the view resets when a county "
                   "opens, or with the button.")
        if st.button("Reset map view"):
            st.session_state["_map_nonce"] = nonce + 1
            st.rerun()


LAYER_LEGEND = {
    False: "Colours and map symbols: ▲ Leak (red) · ◆ Watch (amber) · ✓ OK (green) · ○ Unknown (grey); Keski-Uusimaa, "
           "Vantaa-Kerava and Helsinki are marked in the inset. Hatched: less than half of the stage is observable, so it "
           "cannot be judged.",
    True: "Colour: visibility score, light (low) to dark blue (high). Hatched: score below 50.",
}


STATUS_ICON = {"pass": "✅ pass", "fail": "❌ fail", "incomplete": "⚠️ incomplete",
               "not_reconcilable": "➖ not reconcilable", "no_data": "➖ no data", "not_checked": "▫️ not checked"}


def data_spine(data: dict) -> None:
    st.subheader("Data spine")
    catalog = data["catalog"]
    names = dict(zip(data["units"]["code"], data["units"]["short_fi"]))
    tabs = st.tabs(["Coverage", "Reconciliation", "Indicator catalog"])
    with tabs[0]:
        st.caption("  ·  ".join(f"{symbol} {meaning}" for symbol, meaning in LEGEND.items()))
        matrix = coverage_matrix(data["store"], [i.id for i in catalog], names)
        labels = pd.DataFrame(
            {"Stage": [i.stage for i in catalog], "Indicator": [i.label for i in catalog], "Status": [i.status for i in catalog]},
            index=matrix.index,
        )
        st.dataframe(pd.concat([labels, matrix], axis=1), hide_index=True, width="stretch", height=35 * (len(matrix) + 1) + 3)
    with tabs[1]:
        st.caption("Each published figure recomputed from the store. A pass is never forced; gaps stay visible.")
        labels = {a.id: a.label for a in data["anchors"]}
        rows = [
            {
                "Anchor": labels.get(r.anchor_id, r.anchor_id),
                "Indicator": r.indicator_id,
                "Period": r.period,
                "Method": r.method,
                "Published": r.published,
                "Computed": r.computed,
                "Diff": r.diff,
                "Tolerance": r.tolerance,
                "Status": STATUS_ICON[r.status],
                "Detail": r.detail,
            }
            for r in data["reconciliation"]
        ]
        columns = ["Anchor", "Indicator", "Period", "Method", "Published", "Computed", "Diff", "Tolerance", "Status", "Detail"]
        st.dataframe(pd.DataFrame(rows, columns=columns), hide_index=True, width="stretch", height=35 * (len(rows) + 1) + 3)
    with tabs[2]:
        st.dataframe(pd.DataFrame([i.model_dump() for i in catalog]), hide_index=True, width="stretch")


def scope_tab(data: dict) -> None:
    scope = data["scope"]
    st.markdown(f"**Anchor cancer:** {scope.anchor_cancer}")
    secondary = scope.secondary_cancer or "⚠️ decision pending (" + " or ".join(scope.secondary_cancer_candidates) + ")"
    st.markdown(f"**Second (screened) cancer:** {secondary}")
    st.markdown(f"**Pathway stages:** {' → '.join(scope.pathway_stages)}, plus cross-stage *{scope.cross_stage}*")
    st.markdown(f"**Data rule:** {scope.data_rule}")
    st.markdown("**Goal 3 measures tracked**")
    st.dataframe(pd.DataFrame([g.model_dump() for g in scope.goal3_indicators]), hide_index=True, width="stretch")
    st.markdown("**Related pathway targets**")
    st.dataframe(pd.DataFrame([g.model_dump() for g in scope.related_targets]), hide_index=True, width="stretch")


def rules_tab(data: dict) -> None:
    rows = [
        {
            "ID": r.id,
            "Stage": r.stage,
            "Trigger": r.trigger,
            "Action": r.action,
            "Owner": r.owner,
            "Owner level": r.owner_level,
            "KPI": r.kpi,
            "Cost reference": r.cost_ref,
            "Evidence": r.evidence_grade,
            "Mode": r.mode,
            "Sources": "; ".join(f"{c.id} {c.locator}" for c in r.sources),
            "Do not fire if": "; ".join(r.do_not_fire_if) or "(data-capture rule: always eligible)",
            "Note": r.note,
        }
        for r in data["rules"]
    ]
    st.caption("Rule triggers become machine-evaluable with the action engine (F5). Hypothesis-graded actions are shown only as 'test'.")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def config_tabs(data: dict) -> None:
    tabs = st.tabs(["Scope & Goal 3", "Threshold register", "Action library", "Sources", "Anchors", "Reference times"])
    with tabs[0]:
        scope_tab(data)
    with tabs[1]:
        if thresholds_are_frozen():
            st.caption(f"Frozen before any county result was loaded · sha256 `{thresholds_digest()}`")
        else:
            st.error("Thresholds are NOT frozen: edited after the freeze, marked draft, or the lock is missing.")
        provenance = threshold_provenance()
        frame = pd.DataFrame(
            {
                "Parameter": list(data["thresholds"]),
                "Value": [str(v) for v in data["thresholds"].values()],
                "Provenance": [provenance[name] for name in data["thresholds"]],
            }
        )
        st.dataframe(frame, hide_index=True, width="stretch")
    with tabs[2]:
        rules_tab(data)
    with tabs[3]:
        st.dataframe(data["sources"], hide_index=True, width="stretch")
    with tabs[4]:
        st.caption(
            "Published figures that Step 2 data must reconcile to: counts sum back to national totals; "
            "shares are compared like for like at the stated level. Ranges and bounds use low / high."
        )
        st.dataframe(pd.DataFrame([a.model_dump() for a in data["anchors"]]), hide_index=True, width="stretch")
    with tabs[5]:
        times = data["times"]
        st.warning(f"Indicative only, not binding targets. {times.note}")
        st.dataframe(pd.DataFrame([i.model_dump() for i in times.intervals]), hide_index=True, width="stretch")


def main() -> None:
    # Only data loading is guarded: a rendering bug must surface as an exception
    # (and fail the smoke tests), never be mislabelled as a configuration problem.
    try:
        data = load_everything(input_stamp(APP_INPUTS))
    except (OSError, ValueError) as exc:
        st.error(f"Configuration or reference data failed validation: {exc}")
        st.stop()
    header(data)
    metrics_row(data)
    st.divider()
    map_and_units(data)
    st.divider()
    pathway_section(data)
    st.divider()
    data_spine(data)
    st.divider()
    config_tabs(data)


main()
