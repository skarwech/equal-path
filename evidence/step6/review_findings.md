# Step 6 (F5 + Action Card) independent review, 2026-11-14

Three reviewers (rule engine vs spec, card and PDF, app wiring and tests); each finding re-checked by a skeptic in
a scratch copy. 21 confirmed, 0 refuted. All fixed or disclosed; each fix has a test that fails without it.

## High
- C-1/W-2 Card figures (41.9 % coverage, 5.2 pp gap) cited the rule's policy sources. 'Why' and coverage lines now
  cite the data source of the figure (Cancer in Finland report, lung report, distance sources).
- W-1 The card date was frozen when the app started (cached); it is now computed on every view.

## Medium
- E-1 A verified gap whose only rule needs data no longer claims 'actions for the verified gaps'.
- E-2 Every fact the rules use must exist for every county; Kymenlaakso's plan is pinned. E-3 printed gap sizes tested.
- E-4 Second 'any' arms and the spec boundaries (5 pp fires, visibility 0.5 not blocked) tested; guard list pinned.
- C-2 'Needs data' reasons with parentheses kept whole. C-3 the visibility limitation names the grey stage.
- C-4 Timing gaps are not printed as pp. C-5 Text widths use upper bounds (unknown glyph = 1 em; bold +15 %).
- C-6 Cost locator no longer cites the unread cost annex. W-3 Downloaded PDF checked to be the selected county's
  card. W-4 the rule table's 'Needs data' column checked. W-5 drawer card rows checked line by line with sources.

## Low
- E-6 'Low access' needs the 3 pp practical gap.
- E-7 Primary-care trend: the series breaks at the 9/2023 and 1/2025 law changes, so the fact stays unknown
  ('needs data' with that reason) instead of a misleading trend.
- C-7 Pilot wording aligned with spec sections 7.5 and 13. C-8 unpublished coverage handled. W-6 screen order checked.

## Not fixed
- E-5 (low) R-REF-01 keeps its diagnosis-visibility guard, as approved in Stage 1 (pinned by tests/test_rules.py), so
  its 'slow symptom route' arm is also blocked while diagnosis is unseen. Today this changes nothing (no referral leak).
- C-5 partly: widths use conservative upper bounds instead of the exact Helvetica-Bold metrics table.
