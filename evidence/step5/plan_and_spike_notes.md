# Step 5 (interface, F8): plan and click spike, 2026-11-14 ~16:00 EET

Stop time set for the Step 5 gate: 18:30 EET (F5 and F7 must follow before the midnight freeze).

## Spec gates (F8)
- Map: 22 polygons coloured by the chosen layer, hatched where visibility is low, colour-blind-safe scale.
  Valid when 22/22 are clickable and tooltip values equal the table values (automated comparison).
- County page: four stages (Leak/Watch/OK/Unknown), confidence badge, twin panel, glidepath, sources drawer.
  Every grey stage explains why. Valid when each stage state equals the gap-locator output and every
  displayed figure appears in the sources drawer.

## Click spike result (Streamlit 1.51, Plotly 6.3)
- `st.plotly_chart(fig, on_select="rerun", selection_mode="points")` on a go.Choropleth works: a click returns
  selection.points[0].location == unit code (e.g. "13"), plus point_index.
- A Scattergeo overlay with hoverinfo="skip" does not block hover; set selected/unselected opacity 1 so
  other polygons are not dimmed after a click (confirmed visually).
- Still to check: a click landing exactly on a hatch line; Helsinki/Vantaa-Kerava hit size.
- Scattergeo lines are drawn as great-circle arcs: densify hatch segments.
- Apply a map selection only when it changes (selections persist across reruns), and do not give the
  county selectbox both index= and a session-state value.

## Design decisions (to state at the gate)
- One low-visibility predicate shared by F2's gate, hatching and the badge: visibility < min_stage_visibility (0.5, frozen).
  Real data: only diagnosis (all 22) and timing are below 0.5, so only those layers hatch.
- Confidence badge uses frozen thresholds only: low if visibility < 0.5; high if visibility >= 0.5 and every
  assessed series has a published n or CI and the twin set is good and stable (>= twin_stability_jaccard 0.6);
  medium otherwise. Write tests before computing it; disclose if it comes out constant per stage.
- Use thresholds.twin_stability_jaccard in the view instead of the hard-coded 0.6.
- Sources drawer as pure data (figure id, value, display string, source ids, locator) for reuse by F7 and the Action Card.
  Coverage test harvests numbers from the rendered page, not from the drawer builder.
- Keep the Stage 1 cooperation-area highlight (as an outline) and its table filter.
- Smoke helper `_table` picks the first dataframe with a column: drawer column names must not hijack old assertions.
