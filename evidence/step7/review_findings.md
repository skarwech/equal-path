# Step 7 (F7 AI analyst) independent review, 2026-11-14

Three reviewers (adversarial validator, template truth, generation and wiring); each finding re-checked by a
skeptic. 28 confirmed, 0 refuted. All fixed; each fix has a test that fails without it.

## High
- V-1/V-2 Numbers the validator could not see: number words, ranks, Roman numerals, superscripts, digits glued to
  a dot or letters. All rejected now. V-3 access-time claims with 'months', 'delay', 'waited' or number words.
- T-1 A gap was tagged with the alphabetically first source of the stage, not the deciding indicator's source.
- G-1 'Rounding tolerance' let a Claude briefing show a number (42) that is not in the sources drawer. Numbers
  must now be exactly as given (41.90 = 41.9). This is stricter than the spec's 'within rounding tolerance'.

## Medium / low
- V-4 limitation must name each stage that cannot be judged; V-5 more causal variants; V-6 rule ids rejected;
  V-7 unit must match (pp is not %); V-8 signs and Unicode minus rejected; V-9 sections in order, once each;
  V-10 no digits invited by labels or the county code; V-11 lookalike brackets escaped; V-12 loose tags rejected.
- T-2 subgroup shown; T-3 low visibility by visibility (Watch below the gate too); T-4 'What to verify' tied to the
  leak or the unpublished county coverage; T-5 owner level shown; T-6 action trimming at ';'.
- G-2 only network/API errors fall back (our own bugs raise); G-3 only Claude briefings are cached; G-4 the caption
  names the model that wrote the reply (server-side fallbacks); G-5 full request shape and feedback tested;
  G-6 FAILED caption tested; G-7 client creation failures handled; G-8 20 s timeout, 1 retry; G-9 stop on refusal,
  ignore text before a fallback switch; G-10 vacuous assertion removed.
