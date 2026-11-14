# Equal Path

**Where does the cancer pathway leak in each Finnish wellbeing county, how sure can we be, and what should
happen next?** Equal Path answers this for all 22 units (21 wellbeing services counties and Helsinki) from
public data only. It was built for the Junction 2026 AstraZeneca challenge on equitable and effective cancer
care. The design and acceptance spec is `equal_path_junction_astrazeneca.md` (rev 2).

Three principles run through everything:

- **Gaps are shown, never filled.** Nothing on screen is synthetic; missing data is a finding in itself.
- **Every number has a source.** Each figure on a county page appears in its sources drawer with a source id and
  a locator or derivation.
- **Claims match the evidence.** A leak needs statistical significance, a practical gap and enough visibility;
  hypothesis-graded actions are only ever offered as a test.

## Quick start

Requires Python 3.13 (tested on macOS).

```bash
pip install -r requirements.txt
bash scripts/run_app.sh            # opens on http://localhost:8501 (localhost only, no telemetry, works offline)
```

Check that everything is green (about 4 minutes; this also updates the test badge shown in the app):

```bash
python3 -m pytest
```

Demo checks before a presentation:

```bash
python3 scripts/rehearse.py        # 5 offline runs of the demo counties; exits non-zero on any problem
python3 scripts/cold_start.py      # cold start with the network blocked; must stay under 10 seconds
```

## Tour of the app

The page reads top to bottom:

1. **Header.** Data spine summary and six badges: units on the map, cooperation areas, frozen thresholds (with the
   lock's SHA-256), action rules, tests passing (from the last full test run; marked stale if code or data changed
   since) and **Trust** (anchors reconciled, tests, briefings validated, unsupported numbers shown, all computed
   live).
2. **Map.** Choose a layer: visibility score or the state of one pathway stage (detection, referral, diagnosis,
   treatment). Each county shows a colour, a symbol (▲ Leak, ◆ Watch, ✓ OK, ○ Unknown) and a word in the tooltip;
   hatching means less than half of that stage is observable. Keski-Uusimaa, Vantaa-Kerava and Helsinki are also
   drawn in a zoomed inset. **Click a county to open its page.** The table beside the map shows the same values as
   the tooltips.
3. **County pathway** (or pick a county in the selector):
   - **Funnel:** each stage's state, visibility and confidence (high, medium or low), and why every grey stage
     cannot be judged.
   - **Indicator table:** value, test interval, national value, twin median, gaps and the reason for each state.
   - **Structural twins:** the three most similar counties on structural covariates, with stability.
   - **Glidepath:** screening participation trend towards the 80 % goal by 2035.
   - **Analyst briefing:** at most 120 words, every number tagged with its source and checked by the number
     validator; the caption says who wrote it and that it passed.
   - **Action Card:** finding, top 3 actions (owner, KPI, cost reference, evidence), a 90-day pilot and
     limitations; **Download Action Card** gives the same text as a one-page PDF.
   - **All rules for this county:** the status of each of the 12 rules (fires, not triggered, needs data, blocked).
   - **Sources drawer:** every figure on the page with its source and locator.
4. **All counties:** one row per county with visibility, stage states, twin stability and primary finding.
5. **Data gaps and limitations:** every indicator that is not published for all 22 units (and why), and the
   main limitations, each computed from the data.
6. **Data spine:** coverage matrix, reconciliation against published national figures, indicator catalog.
7. **Configuration:** scope and Goal 3 measures, threshold register, action library (with each rule's machine
   condition), sources, anchors, reference times.

Good demo counties: **Kymenlaakso** (verified leaks in treatment and detection; the Action Card adds remote
oncology and lung peer review), **Pohjois-Karjala** (detection leak) and **Helsinki** (no verified gap).

## What the public data can and cannot show

- Stage at diagnosis is recorded for 41.9 % of cancers nationally; only Pirkanmaa publishes its own figure (71.9 %),
  so the **diagnosis** stage cannot be judged anywhere and stage recording is the first action for 21 counties.
- **Access times** (timing) are not published by county; the app says so instead of showing a number.
- Screening participation by mother tongue and education is published nationally only, so the outreach rule
  (R-DET-01) is shown as "needs data" where detection leaks.
- Glidepaths are **indicative**: held-out-year calibration covered 25 of 44 series (57 %, target 65-95 %).
- Twin sets are unstable in 10 of 22 counties (Jaccard below 0.6, mostly driven by income).
- Early warning (spec F4) is not built: the frozen targets cannot be met with the public monthly series
  (`evidence/step4/early_warning_feasibility.txt`).
- The second (screened) cancer has not been chosen; lung cancer is the anchor.

## The AI analyst (optional Claude)

Without setup, each county's briefing comes from a deterministic template, cached for offline use in
`data/processed/briefings.json`. To have Claude (`claude-opus-5-5`) write the briefings:

```bash
pip install anthropic
export ANTHROPIC_API_KEY=...       # your own key
python3 scripts/cache_briefings.py # writes validated Claude briefings to the offline cache
```

Claude receives only a JSON of computed figures with source ids. The number validator accepts a reply only if
every number equals a computed figure exactly (with its unit and its own source tag), the five sections are
present in at most 120 words, the stages that cannot be judged are named, causal wording appears only for
study-supported actions and no access time is stated. A rejected reply is regenerated up to twice and then
replaced by the template. Rerun `scripts/cache_briefings.py` after any data change; the tests fail while the
cache is stale.

## How correctness is checked

All of these are enforced by the test suite (`tests/`, about 1,250 tests, 97 % coverage):

- **Data:** exactly 22 units (Åland excluded); every stored value comes from a saved raw download parsed by code,
  cites a source and locator, and passes validation; published national figures are recomputed from county rows
  and never forced to pass; catalog status stays in sync with the data.
- **Thresholds:** frozen before any county result was loaded and locked by SHA-256 (`config/thresholds.lock`).
- **Visibility (F1):** only real, current, unit-level data counts.
- **Gap locator (F2):** a Leak must be significant (Wilson interval or published CI, Bonferroni within the
  stage), at least 3 pp worse than both the national value and the twin median, in a stage with visibility of
  at least 0.5. Pure-noise false-Leak rate at most 5 % per stage.
- **Twins (F3):** six structural covariates only (no outcomes); stability reported per county.
- **Glidepath (F4):** Theil-Sen trend with a seeded bootstrap 80 % interval; one outlier year never reverses a
  verdict on the test series.
- **Interface (F8):** 22 of 22 counties clickable (verified in the running app); tooltips equal the table; every
  number on a county page is in its sources drawer, for all 22 counties.
- **Action engine (F5):** truth tables for all 12 rules; no gap action without a verified gap; missing data means
  "needs data", never "fires"; product-neutral text (no sponsor, brand or drug names); national-lead rules name
  the national lead.
- **Action Card:** the PDF and the screen show the same lines for all 22 counties; one page; built in well under
  3 seconds; overflow raises instead of truncating.
- **Analyst (F7):** the validator above; 22 counties x 3 runs with no unsupported number.
- **Offline (Step 8):** all 22 counties load with the network blocked; cold start under 10 seconds; the cached
  briefing is shown only if it matches the current data, is unedited and passes the validator.

Each step also had an independent review (findings re-checked by a second reviewer) and a mutation check
(the code was broken on purpose to confirm the tests catch it); see `evidence/step*/`.

## Status

| Step | Content | Status |
|---|---|---|
| 1 | Foundation: frozen thresholds, scope, 22-unit geography, source registry, action library as data | approved |
| 2 | Data spine (F0): 18 public indicators, catalog of 27 incl. gaps, reconciliation, spot check | approved |
| 3 | Visibility score (F1), gap locator (F2), twin core, tipping point (not computable: no regional stage data) | approved |
| 4 | Twins final (F3), screening glidepath (F4); early warning shown infeasible | approved |
| 5 | Interface (F8): map layers, click-through, funnel, confidence, sources drawer | approved |
| 6 | Action engine (F5) and the one-page Action Card | approved |
| 7 | AI analyst and number validator (F7) | approved |
| 8 | Hardening: offline mode, trust panel, data gaps and limitations, rehearsal | approved |

Development is complete. Open items need people, not code:

- Clinical review of the 12 action rules (`evidence/step6/clinical_review_sheet.csv`).
- Plausibility check of the twin lists (`evidence/step4/twin_review_sheet.csv`).
- Choosing the second (screened) cancer.
- Analyst faithfulness review of 5 counties and the clarity test (2 of 3 outside readers name the leak and the
  action within 2 minutes).
- Backup demo video and up to three slides.

## Rebuilding the data

Only needed to refresh the sources (online once; everything runs offline afterwards):

```bash
python3 scripts/fetch_geography.py        # Statistics Finland boundaries -> data/raw/geo/
python3 scripts/build_units.py            # -> data/reference/units.csv, units.geojson
python3 scripts/fetch_sources.py          # config/downloads.yaml -> data/raw/<family>/ + manifest.json
python3 scripts/build_observations.py     # parse + validate -> data/processed/observations.parquet
python3 scripts/spot_check_sample.py      # seeded 10-cell sample for the F0 spot check
python3 scripts/cache_briefings.py        # refresh the offline analyst cache
```

Two Cancer Registry app exports are session-bound and cannot be scripted; they are registered as snapshots with
`scripts/register_snapshots.py` (`config/snapshots.yaml` records origin and capture). Change a threshold only
deliberately: edit `config/thresholds.yaml`, then run `python3 scripts/freeze_thresholds.py`; the lock diff makes
the change visible.

## Layout

```
app/               Streamlit app (streamlit_app.py, pathway_view.py); app/static/ serves the map topojson locally
config/            scope, frozen thresholds (+ lock), indicator catalog, action rules, anchors, downloads, reference times
data/raw/          every raw download + manifest.json (URL, time, sha256): the offline source of truth
data/processed/    observations.parquet (long format) and briefings.json (offline analyst cache)
data/reference/    sources.csv (source registry), units.csv, units.geojson
equal_path/        library: data spine, visibility (F1), gaps (F2), twins (F3), glidepath (F4), pathway, map layers,
                   confidence, sources drawer, actions (F5), Action Card + PDF, analyst (F7), hardening
equal_path/loaders one parser per source family
scripts/           run, fetch, build, freeze, cache, rehearse, cold start
tests/             pytest suite (unit, real data, app smoke and page gates)
evidence/          test report, per-step screenshots, reviews, mutation checks, rehearsal and cold-start results
```
