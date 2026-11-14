# Equal Path

Equitable and effective cancer care in Finland. Junction 2026, AstraZeneca challenge.
Design and acceptance spec: `equal_path_junction_astrazeneca.md` (rev 2).

## Status

| Stage | Plan step | Status |
|---|---|---|
| 1. Foundation: frozen thresholds, scope (second cancer pending), 22-unit geography, source registry, action library as data, skeleton app | Step 1 + the "22 units visible" half of Step 2 | approved (second cancer still to be chosen) |
| 2. Data spine (F0): 18 public indicators for 22 units, catalog of all 27 incl. gaps, 9 of 11 anchors reconciled (2 shown as not checked), 10/10 spot-check | Step 2 | approved |
| 3. Visibility score (F1) + gap locator (F2) + twin core + tipping point (synthetic only: no regional stage data) | Step 3 | approved |
| 4. Twins final (F3: + distance to university hospital, stability, better twins) + glidepath (F4); early warning shown infeasible | Step 3 | approved |
| 5. Interface (F8): map layers with low-visibility hatching, 22/22 clickable map (Helsinki-area inset), funnel with confidence badges and grey-stage reasons, sources drawer | Step 4 | approved |
| 6. Action engine (F5) + Action Card: 12 rules with machine conditions, top 3 per county, one-page PDF card | Step 5 | approved |
| 7. AI analyst + number validator (F7) | Step 6 | in progress on branch `step-7-analyst` |
| 8. Hardening: offline cold start, trust panel, rehearsal | Steps 6-7 | |

## Run

```bash
python3 -m pytest --cov            # full run; writes evidence/test_report.xml + fingerprint for the app badge
bash scripts/run_app.sh            # offline-safe launcher: localhost only, no telemetry, local map assets
```

Rebuild the data (online once, offline after):

```bash
python3 scripts/fetch_geography.py        # Statistics Finland boundaries -> data/raw/geo/
python3 scripts/build_units.py            # -> data/reference/units.csv, units.geojson
python3 scripts/fetch_sources.py          # config/downloads.yaml -> data/raw/<family>/ + manifest.json
python3 scripts/build_observations.py     # parse + validate -> data/processed/observations.parquet
python3 scripts/spot_check_sample.py      # seeded 10-cell sample for the F0 spot check
```

Two Cancer Registry app exports are session-bound and cannot be scripted; they are registered as
snapshots with `scripts/register_snapshots.py` (config/snapshots.yaml records origin and capture).

Change a threshold only deliberately: edit `config/thresholds.yaml`, then run
`python3 scripts/freeze_thresholds.py`. It stamps `frozen_at` with the real time and rewrites the
lock; the lock diff makes the change visible. Files marked `status: draft` are never locked.

## Layout

```
config/            scope (second cancer pending), frozen thresholds (+ lock), rules, anchors, reference times
data/raw/<family>/ every raw download + manifest.json (URL, time, sha256): the offline source of truth
data/processed/    observations.parquet (long format, section 7.2 + geo_level, subgroup, locator, CI)
data/reference/    sources.csv (registry), units.csv, units.geojson (22 units, Åland excluded)
equal_path/        library: config, geography, sources, lint, trust, viz, spine, coverage, names,
                   visibility (F1), gaps (F2), twins (F3), glidepath (F4), tipping, pathway (runs F1-F3),
                   confidence + grey-stage reasons, map_layers (layers, hatching, clicks), drawer (sources
                   for every figure), display (shared formatting), actions (F5 rule engine), card (Action Card
                   and its one-page PDF writer)
equal_path/loaders one parser per source family (screening, cr_app, cif_report, lung_report, sotkanet, statfin,
                   distance: population-weighted km to the nearest university hospital)
scripts/           fetch / build / freeze
app/               Streamlit app; app/static/ serves the Plotly topojson locally (no CDN)
tests/             pytest suite (unit, build reproducibility, app smoke test)
evidence/          test reports, screenshots
```

## Ground rules enforced by tests

- Exactly 22 units (codes 01-21 and 90); Åland (91) excluded explicitly.
- Every unit, anchor, rule citation and Goal 3 indicator resolves to `sources.csv`.
- Thresholds: Appendix B values verbatim, plus the section-8 method constants and two labelled team-set
  parameters (early-warning baseline window, visibility stage weights); all match the frozen SHA-256 lock.
- The test badge is "current" only for a full default run that wrote `evidence/test_report.xml`, with no
  watched file changed since; partial runs, `-o addopts=""` runs and edits all show "stale".
- Actions are product-neutral (no sponsor, brand or drug names); hypothesis-graded actions are "test" only.
- No synthetic indicator values anywhere in the real view; gaps stay gaps (catalog status kept in sync with the store).
- Every stored value comes from a saved raw file parsed by code, cites a source and a locator, and passes
  validation (numerator <= denominator, shares 0-1, value inside its CI, no duplicate keys).
- Published national figures are recomputed from county rows and never forced to pass.
- F1 counts only real, current, unit-level data (injected or area-only values stay dark); timing is a separate row.
- F2: a Leak must be significant (Wilson or published CI, Bonferroni within the stage), >= 3 pp worse than the
  national value AND the twin median, and in a stage with visibility >= 0.5. Pure-noise false-Leak rate <= 5 %
  per county and stage, tested on the real denominators, CI widths and twins.
- F3: twins use six structural covariates only (no outcomes), density as log10 and hospital distance as
  log10(1 + km), z-scored; ties broken by code. Stability under +/-5 % noise is reported per county (10 of 22
  fall below the 0.6 gate and unit 01 sits exactly at 0.60; driven by income: disclosed, not hidden). "No twin data" is never shown as
  "leader among peers".
- F4: Theil-Sen trend with a seeded bootstrap 80 % interval. "On track" needs both the Theil-Sen line and
  the bootstrap median to reach 80 % by 2035; on the test series no single outlier year of up to +/-10 pp
  reverses a verdict (it can soften "off track" to "uncertain").
  Projections are displayed capped at 100 %. Held-out-year calibration covers 25 / 44 series (57 %), so the
  glidepath is labelled "indicative". Early warning is not built: infeasible under the frozen targets
  (see evidence/step4/early_warning_feasibility.txt).
- F8 map: tooltip text equals the table beside the map for every layer and all 22 units; each polygon is drawn
  in its own layer colour; stage layers use status colours with ▲/◆ symbols and words (never colour alone);
  hatching marks a stage below the visibility gate (the same `low_visibility` test as F2's Leak gate). A click
  opens the county (22/22 verified in the running app, evidence/step5/map_click_e2e.json); Keski-Uusimaa,
  Vantaa-Kerava and Helsinki are clicked in a zoomed inset.
- F8 county page: for all 22 counties the funnel shows the gap locator's stage states, every grey stage says
  why, and every number on the page (tables, funnel, captions) appears in the sources drawer with a registered
  source and a locator or derivation. The confidence badge uses only frozen thresholds (visibility gate, published
  n or CI, good and stable twins).
- F5 actions: each rule's spec trigger is encoded as machine conditions over named county facts (config/rules.yaml
  `when` / `when_any`); a fact with no public county data is unknown, so the rule says "needs data" and never fires
  (three-valued logic: a known False still rules it out). Gap rules need a verified gap (Leak) in their own stage;
  data-capture rules (R-DAT-01, R-DET-02) fire on their data trigger. Ranking: stage recording first, then gaps by
  size, then other data capture; top 3; with no verified gap the card says "No verified gap; maintain and improve
  data". Truth tables cover all 12 rules (fires when satisfied, not when each condition is violated, needs data
  when a fact is missing, blocked by low visibility). Hypothesis-graded rules print as "Test"; national-lead rules
  name the national lead. All rule and card text passes the neutrality lint.
- Action Card: the screen and the one-page PDF show the same lines (tested for all 22 counties); the PDF is built
  in well under 3 seconds by a small built-in writer (no extra package, works offline) and overflow raises instead
  of truncating. A clinical review sheet for the 12 rules is in evidence/step6/clinical_review_sheet.csv.
