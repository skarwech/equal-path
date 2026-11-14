# Step 8 (hardening) independent review, 2026-11-14

Two reviewers (offline mode, cache and rehearsal; trust, data-gap and limitations panels); each finding re-checked
by a skeptic. 15 confirmed, 0 refuted. All fixed; each fix has a test that fails without it.

## High
- O-1 The rehearsal passed even with no cache. It now reads the page's own briefing caption, requires every demo
  briefing from the offline cache, clears Streamlit caches between runs, counts refused network calls, and reports
  gate_met only for >= 5 runs.
- O-2 Edited words in a cache entry were shown as template text. Entries now carry a text hash; template entries
  must equal the template for the current facts.
- O-3 With an SDK and credentials but no network, the cache was skipped. A current cache entry now always wins.
- O-4 Cached Claude text lost its provenance; the caption always shows model and cache date.
- P-1 'Unsupported numbers shown' was zero by construction; it now counts every number problem the validator reports.
- P-2 The data-gap reason for stage-recording coverage was false (Pirkanmaa and Sisä-Suomi are loaded); corrected.

## Medium / low
- O-5 a corrupt cache falls back to the template; O-6 the network block also covers connect_ex, sendto, sendmsg and
  DNS lookups, and counts refusals; O-7 cold start measured in a fresh process (scripts/cold_start.py).
- P-3 the page and the trust panel share one selection function; the badge shows how many briefings come from the
  cache. P-4 the badge shows anchors as pass / fail / not checked of 11. The spec says 'counties reconciled'; the
  reconciliation is by published national and area anchors, not per county (disclosed).
- P-5 panel tests check computed values; P-6 data gaps selected by the store; P-7 no crash without own coverage;
  P-8 the glidepath limitation uses the computed calibration label.
