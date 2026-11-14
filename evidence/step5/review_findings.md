# Step 5 (F8) independent review, 2026-11-14

Three reviewers (gate tests, provenance and logic, map and interaction); each finding re-checked by a skeptic
who tried to refute it in a scratch copy. 24 confirmed, 2 refuted (written against an older tree). All 24 fixed,
each with a test that fails without the fix (see mutation_check.txt).

## High (wrong figures on the page)
- P-1 National stage-recording coverage showed the lung row (43.6 %) instead of all sites (41.9 %), chosen by row
  order. Now the 'all' series, and more than one candidate row is an error. The drawer cites its locator.
- P-2 'Typical nearest-twin distance' was the upper-middle of 22 values (1.082); now the median (1.038), as the
  drawer says. This figure dates from Step 3 and is also on the approved main branch; it changes when Step 5 merges.

## Medium
- G-1 Tooltip = table is now also checked end to end: each layer chosen in the running app, the rendered Plotly
  tooltips (main map and inset) compared with the rendered table; test labels are literals, not imported.
- G-2 Hatching and Leak/Watch/OK/Unknown symbols checked per polygon on both maps. G-3 score layer and palette
  checked against literal values.
- G-4 Every funnel card's confidence level and every grey-stage reason checked on the rendered page, 22 counties.
- G-5 Data rows in the drawer cite the sources of the indicators they come from, never the rule register.
- P-3 No drawer rows for missing figures. P-4 Derivations recomputed exactly (published national row vs pooled,
  published CI vs Wilson, the twins that entered the median). P-5 The 80 % goal cites the national strategy.
  P-6 The Leak rule row describes the test actually used (Wilson or published CI at the stage's Bonferroni z).
- M-1 Clicking the county that is already open did nothing (Plotly toggled the selection off). The chart is now
  re-drawn after each navigating click, so every click is fresh.
- M-2 Streamlit turns on map panning when clicks are enabled; the code comment wrongly said it was locked. Added
  'Reset map view'; the view also resets whenever a county opens. Panning itself is not prevented.

## Low
- G-6 Branch 'observable but nothing could be judged' now tested. G-7 The page may only contain element types the
  drawer harvest reads. G-8 The All counties overview is checked against the gap locator.
- P-7 Drawer national lookup mirrors the gap locator's selection. P-8/P-9/P-10/P-11 Wording: 'no usable n or CI';
  stability never rounds up to the bar; timing is 'not judged by the gap locator'; 'latest' cites that year only.
- M-5 The three tiny units' symbols are drawn in the inset only. M-6 Every state has a symbol (✓ and ○ added).
  M-7 Hatch note on the score layer says 'visibility score below 50'.
