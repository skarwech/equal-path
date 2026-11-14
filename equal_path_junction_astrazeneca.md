# Equal Path: AstraZeneca challenge, Junction 2026

**Equitable and effective cancer care in Finland. Analysis, solution design, 48-hour execution plan and feature acceptance specification.**

Revision 2, Friday 13 November 2026 (Junction weekend; judging Sunday 15 November, 14:00).
Revision 2 integrates the uploaded implementation roadmap (read in full for sections 1-3 and the data and cost sections), the full national strategy, and THL Ohjaus 21/2016 (national cancer access monitoring).

---

## 0. Conventions

| Term | Meaning |
|---|---|
| **Verified** | Read directly in a source document or a published release during preparation. Sources are listed in Appendix A. |
| **To verify** | Plausible, but not confirmed. Check before it appears on a slide or in the demo. |
| **Team-set** | A threshold we propose. Freeze it before looking at any county result, so nobody can tune it to fit a story. |
| **P0 / P1 / P2** | P0 must work live. P1 is strong but droppable. P2 is cut first. |
| **Evidence grade** | *Strategy-endorsed* (named in the national strategy or roadmap), *Study-supported* (backed by a study cited there), or *Hypothesis* (shown only as something to test). |

### What revision 2 changed

1. **The referral-to-treatment "dark zone" is smaller than first stated.** THL Ohjaus 21/2016 (in force since 1 January 2017) already defines national cancer access monitoring on the Hilmo care register: four dates, three intervals, 16 cancers, reporting by municipality of residence and by provider. Whether a current public report exists in 2026 is not confirmed, so the tool treats it as "defined, availability to verify".
2. **Official cancer-specific target times do not yet exist nationally.** Recommended maximum times exist only for breast, prostate and colorectal cancer. The roadmap schedules cancer-specific access times for the first five cancers in 2026-2028 (measure 3.1.2). The tool therefore uses configurable reference times, never hard-coded "official" ones.
3. **Equal Path is positioned as a bridge.** The roadmap's own timeline (standardised referral criteria 2026-2028, quality indicators 2026-2028, quality register permanent from 2028, first annual register reports 2029-2031) leaves a monitoring gap that this tool fills now.
4. **Lung anchor strengthened.** The 2019-2023 national lung report (compared by wellbeing county) found only 27% of patients routed to curative treatment, stage missing for almost half, and about a fifth without an exact cell type.
5. **New costed actions** from the roadmap: monthly screening reporting (2.4.5), standardised referral criteria with Nordic models (2.5.2), digital pathways and AI pilots (3.5.3), structured recording (4.1.1), quality-register peer review (3.2).
6. **The 90-day pilot now reuses THL's existing time-point definitions** and attaches to national pilots already planned, instead of inventing new definitions.

---

## 1. The challenge at a glance

**Brief.** Build an AI-powered system that supports equal and effective cancer care across Finland. It should ensure that time to diagnosis is optimal and that patients start treatment within target timeframes, wherever they live.

**The solution must:**
1. **Identify the gap.** Detect differences in access to cancer care or treatment outcomes.
2. **Locate the gap in the pathway.** Show whether it emerges at detection, referral from primary to specialist care, diagnosis, or treatment initiation.
3. **Recommend what to do.** This is the most important part. Give concrete, evidence-based proposals that could be implemented at national or wellbeing-county level.

**Minimum requirements:**
- Reliable evidence from public data and/or mentor insights, with sources shown for every claim.
- At least one indicator connected to Goal 3 of the national cancer strategy.
- Actionable recommendations, not only analysis.
- A working demo (slides alone are not sufficient).

**Judging criteria:**

| Criterion | Weight | Question asked |
|---|---|---|
| Actionability | 30% | Are the proposals concrete enough for a health centre or wellbeing services county to implement? |
| Insight | 25% | Does it reveal a real gap and show where it emerges in the pathway? |
| Data quality and transparency | 20% | Are sources clear, limitations acknowledged, findings free of unsupported assumptions? |
| Execution | 15% | Does it work in a live demonstration? |
| Clarity | 10% | Can a decision-maker understand the message and action within two minutes? |

**Key dates and people:**
- **Friday 13 Nov:** mentors available from 18:00 (Hanna Rusila, Marketing; Hanna Toivola, Diagnostics; Kaisa Kaitila, Medical Affairs; Laura Aaltonen, Marketing; Joanna Tuormaa, Business Excellence). Key insights are shared at the AstraZeneca stand at 20:00.
- **Saturday 14 Nov:** Kaisa Kaitila during the day.
- **Sunday 15 Nov, 14:00:** judging (Hanna Rusila, Laura Aaltonen, Joanna Tuormaa).
- **Main contact:** Joanna Tuormaa. Questions go to Laura Aaltonen.
- **Prizes:** 1000 EUR, 750 EUR, 250 EUR.
- **Beyond Junction:** AstraZeneca wants to explore a follow-up project with a Finnish wellbeing services county.

**Data note from the brief:** public, aggregate data only. No patient-level or personal data.

---

## 2. Analysis

### 2.1 What Goal 3 measures (verified)

Goal 3 of the national cancer strategy 2026-2035 is "Varmistetaan yhdenvertainen ja vaikuttava syövänhoito" (ensure equal and effective cancer care). Its tracked measures (strategy, Figure 1, p. 5) are:

- Patients reach treatment within target times (reference: THL Ohjaus 21/2016, "Hoitoonpääsyn seuranta syövän hoidossa").
- Five-year survival of poor-prognosis cancers reaches the Nordic level. Relative to NORDCAN 2023 this means lung +14 percentage points, pancreas +6 and liver +14. "Nordic level" is the average of Sweden and Norway.
- Cancer mortality falls by 10% from today's roughly 13,300 deaths per year.

Related national targets that matter for the pathway:
- At least 80% screening participation in every wellbeing county.
- At least 70% of cancers diagnosed in stage I-II (by 2035).
- HPV vaccination coverage of at least 90% among primary-school leavers in every wellbeing county and in Helsinki.
- Equal participation in screening for people whose mother tongue is not Finnish or Swedish.

### 2.2 What the sources show

**Finding 1: stage data is too patchy to rank counties.**
The strategy states that clinical registry notifications containing stage cover only about 40% of cases (p. 30). The Cancer Registry's Syöpä 2024 report (17 June 2026) examined this regionally for the first time:
- Stage information was available for 42% of cases nationally.
- Pirkanmaa reached 72%, the Sisä-Suomi cooperation area 60%, and the other areas between 33% and 42%.
- The target is at least 70%.

A naive "stage I-II share by county" map would therefore mostly show recording quality, not care quality.

**Finding 2: screening participation is public by county, education and mother tongue.**
The Cancer Registry's 2024 screening statistics (release 30 June 2026) report participation and results by wellbeing county, education level and mother tongue:
- Etelä-Pohjanmaa, Etelä-Savo and Kainuu had the highest participation.
- The lowest participation was below 68%, against the 80% goal.
- The release singles out Helsinki as clearly lagging.
- The 2024 screening programmes found 2,360 cancers and 5,272 precursor lesions.
- About 1,200 breast cancers were diagnosed below screening age in 2023-2024.
- The Cancer Society's delegation names access barriers in primary care as the current bottleneck for early detection.
- The roadmap (2.4.5) notes that county-specific screening statistics are published with a delay, and proposes monthly reporting to the screening registers.

**Finding 3: lung cancer is the best anchor, and its data is better than first assumed.**
The national cancer quality register project's lung cancer report (years 2019-2023, results compared by wellbeing county) found:
- Only 27% of patients were routed to curative treatment.
- Stage information was missing for almost half of patients.
- About a fifth of patients had no exact cell type recorded, and not every diagnosis rested on a tissue or cell sample.
- Multidisciplinary team meeting coverage could not be assessed from the Hilmo register.

Lung cancer accounts for about 3,000 new cases a year, causes the most cancer deaths, and is the first cancer in the quality-register pilot. It also carries the largest numeric Nordic-gap target in Goal 3. (An earlier article described a 2018-2022 edition of this work; use the latest report for figures.)

**Finding 4: the access-time measure exists on paper but is only partly operational.**
- The strategy says symptom-to-diagnosis data is not systematically collected (2.5) and that no national cancer quality register exists yet (3.2).
- THL Ohjaus 21/2016 defines the national cancer access monitoring system. It covers 16 cancers (almost three quarters of new cases) and uses four dates: referral arrival at specialised care, first physician visit, placement in the treatment queue, and first cancer treatment. It measures three intervals: referral to first treatment, referral to first physician visit, and queue placement to first treatment.
- The guidance says reports would be published by the patient's municipality of residence and by provider, once data quality is acceptable. Whether a current public cancer access report exists in 2026 is **not confirmed**.
- **Recommended maximum times exist only for breast, prostate and colorectal cancer** (from queue placement; Figures 2-5, pp. 18-19 of the guidance). For other cancers, including lung, the guidance reports duration bands for comparison only (under 2, 2-4, over 4-6, over 6-8, over 8-12 weeks) and says explicitly that these are not recommended times.
- The roadmap (3.1.2) schedules the definition of cancer-specific access times for the first five cancers in 2026-2028.
- A 2010 STM working group proposed indicative limits that the guidance restates (Appendix D).
- A study comparing the Hilmo register with the Cancer Registry (2014 data) found good agreement for most cancers, with deficiencies for brain/CNS and stomach cancer, and said the reliability of referral and first-treatment dates still needed verification.

**Finding 5: the referral stage has a visible, if indirect, indicator.**
THL publishes primary-care access statistics (monthly database reports by wellbeing county and unit), according to a 2023 news report on the data, and a 2026 county document still points to the same THL source. These are not cancer-specific but cover the stage the Cancer Society calls the bottleneck. Current availability and granularity are **to verify**.

**Context from the roadmap and strategy (verified):**
- Regional survival variation persists (Seppä et al., Acta Oncologica 2020), and cancers are on average found at a later stage among people living far from hospitals or in rural areas.
- NSCLC survival is worse when patients live more than 50 km from the treatment unit (Paakkola et al., Acta Oncologica 2024). Palliative radiotherapy is used less beyond 100 km.
- An unpublished lymphoma study reports roughly double the time to diagnosis through the public route compared with private providers. Treat this as a hypothesis only.
- Lung cancer screening piloting started in early 2026 in Helsinki and eight wellbeing counties.
- Breast screening is planned to extend to ages 46-74 (about 9 million EUR in 2028-2031, then 6 million EUR a year).
- The roadmap's first-period investment estimate is about 140 million EUR with expected savings of 298 million EUR (the strategy text quoted 156 and 305 million; the roadmap supersedes it).

### 2.3 What can and cannot be seen

| Pathway stage | Public visibility | Comment |
|---|---|---|
| Detection | Good | Screening participation by county, education and language; HPV coverage. Annual, with publication delay. |
| Referral | Partial | THL primary-care access (monthly, not cancer-specific); standardised referral criteria still being written. |
| Diagnosis | Partial | Stage I-II share exists but stage coverage is 33-72% by area; lung cell-type completeness is about 80%. |
| Treatment | Partial | Lung curative-route share and first-line treatment mix by county; survival by area from the Cancer Registry. |
| Referral-to-treatment timing | **Defined, availability to verify** | THL Ohjaus 21/2016 monitoring exists by design; no confirmed current public series. Cancer-specific targets are still being defined (2026-2028). |

---

## 3. Thesis and out-of-the-box angles

Most solutions will draw a prettier map of unequal outcomes. **Equal Path** makes three claims instead:
1. It states what we cannot see, county by county.
2. Where we can see, it names the pathway stage that leaks.
3. For each leak it issues a costed, source-linked action that a county can start within 90 days.

**Positioning.** The roadmap builds the national instruments (care-chain descriptions with access times, referral criteria, quality indicators, the quality register) over 2026-2031. Equal Path is the interim monitoring and decision layer for 2026-2028, and it shows exactly which data those instruments must deliver to close each leak.

Six angles that set it apart:
1. **Turn the data gap into a finding.** Show, per county, how much of the pathway is invisible, and what the dashboard would look like if the minimum data existed.
2. **Localise the leak, not just the gap.** Compare each county against its structural twin, stage by stage.
3. **Twin-county benchmarking.** "Your twin does this better" is easier to act on than a league table.
4. **Glidepath plus early warning.** Compare annual indicators with the trajectory needed for the 2035 targets, and run change-point detection on monthly series where they exist.
5. **Gap-to-action library.** Each located gap type maps to an intervention taken from the strategy and roadmap, with owner, KPI and cost reference.
6. **Impact simulator with ranges.** Sliders with sources, labelled "scenario, not forecast".

**Handling missing stage data.** Show the stage I-II share among known-stage cases, and next to it a tipping point: how much later the unknown-stage cases would have to be for a ranking to flip (formula in section 7.4). If stage is public only for the five cooperation areas, run the analysis at that level and say so on screen.

---

## 4. Product design: modules

| Module | What it does | Why it scores |
|---|---|---|
| **A. Visibility score** | Per county and stage: share of the pathway observable from public data. | Data transparency (20%). Turns a weakness into a finding. |
| **B. Gap locator** | Four-stage scorecard with a gap versus the twin median and the national value, and a confidence badge. | Insight (25%). |
| **C. Twin benchmark** | The three nearest counties on structural covariates, with the better performers highlighted. | Actionable and less political than rankings. |
| **D. Glidepath and early warning** | Annual trends versus the linear path to the 2035 target; change-point detection on monthly series such as primary-care access. | Early-warning element with enough data points to be meaningful. |
| **E. Action engine** | Rule-based map from gap type to action, owner, KPI, cost reference, evidence grade. | Actionability (30%). |
| **F. Simulator** | Scenario sliders with Monte Carlo ranges. | Shows impact without false precision. |
| **G. Grounded AI analyst** | Claude narrates a county in under two minutes. A validator blocks any number not in the computed data. | Clarity (10%) and data integrity. |

---

## 5. Pathway-to-indicator map

| Stage | Indicators | Source to use | Status |
|---|---|---|---|
| Detection | Screening participation by county, education, mother tongue; HPV vaccination coverage; share of breast cancers diagnosed below screening age | Cancer Registry screening reports; THL | Verified to exist |
| Referral | Primary-care access (contextual, not cancer-specific) | THL primary-care access database reports | To verify (current, granularity) |
| Diagnosis | Stage I-II share (coverage-flagged); stage-recording coverage; lung cell-type completeness | Cancer Registry statistics application; Syöpä 2024; lung quality report | Partly verified |
| Treatment | Lung curative-route share and first-line treatment mix; five-year relative survival by area; optional distance to nearest radiotherapy unit | Lung quality report; Cancer Registry (survival published nationally and by area, strategy 3.2); NORDCAN benchmark | Partly verified |
| Timing (cross-stage) | Referral to first physician visit; referral to first treatment; queue placement to first treatment | THL Ohjaus 21/2016 monitoring (Hilmo) | Defined; public availability to verify |

**Not confirmed:** whether stage I-II share and survival are published per wellbeing county or only per cooperation area; whether a current public THL cancer access report exists; the exact tables behind the lung report.

---

## 6. Action library (rule-based and transparent)

| ID | Trigger | Action | Owner | KPI (strategy measure) | Cost reference | Evidence grade |
|---|---|---|---|---|---|---|
| R-DET-01 | Participation below 80% with the largest gap by language or education | Community-based multilingual screening outreach with local NGOs (roadmap 1.3.1) | Wellbeing county, Cancer Registry, NGOs | Participation parity by mother tongue | 400,000 EUR national budget (roadmap) | Strategy-endorsed |
| R-DET-02 | Screening statistics arrive late or only annually | Monthly reporting of screening data to the registers and a near-real-time county situation picture, plus an annual screening quality day (roadmap 2.4.5) | Cancer Registry, counties | Reporting delay | 300,000 EUR (roadmap) | Strategy-endorsed |
| R-DAT-01 | Stage coverage below 70% | Structured cancer recording template and automated reporting, with part-time recording leads in each county (strategy 3.2 and 4.1; roadmap 4.1.1: 30% of cancers structured in 2 years, 60% in 5, 100% in 10; clinical notifications 90% automated by 2030) | County, Cancer Registry | Stage coverage | 1.75 million EUR over 5 years nationally, 350,000 EUR a year (roadmap 4.1.1) | Strategy-endorsed; precondition for any equity claim |
| R-REF-01 | Stage I-II below twin, or slow symptom route | Standardised referral criteria and symptom-based pathways with direct investigation routes, built on the Nordic models (Danish Kræftpakkeforløb, Swedish SVF, Norwegian Pakkeforløp). Roadmap schedule: at least the five most common cancers in 2026-2028, pilots in wellbeing counties, then all major cancers 2029-2031 (roadmap 2.5.2) | FICAN with counties | Stage I-II share; referral criteria in all national care chains | Part of the 25 million EUR / 5-year national guideline mechanism (roadmap 3.1.1) | Strategy-endorsed |
| R-REF-02 | Primary-care access deteriorating | Strengthen the own-doctor / own-nurse continuity model (roadmap 2.5.1; national lead STM) and track continuity effects on diagnostic delay | STM, counties | Primary-care access and continuity | Part of the national own-doctor programme | Strategy-endorsed (national lead) |
| R-REF-03 | Named care coordinator not in use | Named coordinator model for cancer care (roadmap 1.2.3) | County, FICAN | Coordinator model in use | 100,000 EUR for the national guideline (roadmap) | Strategy-endorsed |
| R-SYM-01 | Late-stage pattern with low symptom awareness | Symptom-awareness communication in groups with known delays (roadmap 1.3.2, modelled on UK Be Clear on Cancer) | FICAN, Cancer Society, counties | Stage I-II share | 400,000 EUR national (roadmap) | Strategy-endorsed |
| R-TRT-01 | Long distance and low curative-intent share | Hub-and-spoke remote oncology with university-hospital tumour-board links (roadmap regional-inequality section; Paakkola 2024; Jääskeläinen et al. 2023) | County, university hospital | Share receiving curative-intent care | Not itemised | Study-supported |
| R-TRT-02 | Lung treatment mix or curative-route share deviates from the national pattern | Annual national peer review and a response mechanism for deviations (roadmap 3.2.2 and 3.2.3) | FICAN, Cancer Registry, county | Treatment-mix convergence | 300,000 EUR (3.2.2) and 3 million EUR (3.2.3) nationally | Strategy-endorsed |
| R-GER-01 | High share aged 75+ | G8 frailty screening and geriatric-oncology assessment at referral (strategy 3.4; roadmap 3.4.1-3.4.3) | County | G8 use in cancer units | About 0.75-1.0 million EUR per measure (roadmap) | Strategy-endorsed |
| R-DIG-01 | Low access and no digital pathway in use | Digital care pathways and AI-based tools, starting with limited pilots in some counties for prioritised cancers (roadmap 3.5.3) | FICAN, counties | Digital pathway use rate | 1.14 million EUR (roadmap) | Strategy-endorsed |
| R-AUD-01 | Suspected public-private diagnostic delay | Timestamp audit of the pathway, using the THL access dates extended back to the first primary-care contact. This tests the unpublished lymphoma finding; note that Hilmo covers public providers and only part of private care | County | Time from first contact to diagnosis | Not itemised | **Hypothesis** (shown as "test", never "implement") |

**Neutrality rule.** All actions are product-neutral: no brand names, no drug names, no sponsor name. Drug-access topics (strategy 4.5) are out of scope for a pathway tool, and staying vendor-agnostic builds credibility with a pharma sponsor in the room.

---

## 7. Architecture and data model

### 7.1 Stack
- Python (pandas, scikit-learn, scipy) for the pipeline and analytics.
- Streamlit with Plotly for the interface; a tile-grid map as fallback if county GeoJSON becomes a time sink.
- Precomputed parquet files so the demo never depends on live APIs.
- Claude API for the analyst, behind a deterministic fallback template.

### 7.2 Long-format data model

`observations`:

| Column | Meaning |
|---|---|
| `county_id` | One of 22 units (21 wellbeing counties plus Helsinki) |
| `indicator_id` | Key into the indicator catalog |
| `period` | Year, month or pooled period, always explicit |
| `value` | The published value |
| `numerator`, `denominator` | For proportions |
| `quality_flag` | e.g. suppressed, low coverage, cooperation-area level, provider-based |
| `source_id` | Key into `sources.csv` |

`indicator_catalog`: stage, definition, direction (higher is better or worse), unit, period, limitation, URL, retrieval date.

`sources.csv`: `source_id, title, publisher, url, retrieved_on, period_covered, limitation`.

### 7.3 Rule file format (example)

```yaml
- id: R-DET-01
  stage: detection
  trigger: "participation < 0.80 AND max_subgroup_gap_pp >= 5"   # 5 pp is team-set
  action: "Community-based multilingual screening outreach with local NGOs"
  owner: "Wellbeing county; Cancer Registry; NGOs"
  kpi: "Participation parity by mother tongue"
  cost_ref: "400000 EUR national budget (roadmap 1.3.1)"
  evidence_grade: strategy-endorsed
  sources: [S_ROADMAP_1_3_1]
  do_not_fire_if: ["visibility_detection < 0.5"]
```

### 7.4 Core computations

- **Wilson interval** for a proportion p with n cases and z = 1.96:
  `(p + z^2/2n +/- z*sqrt(p(1-p)/n + z^2/4n^2)) / (1 + z^2/n)`.
- **Gap** = county value minus reference (twin median or national), signed so that a positive gap always means "worse" (uses the indicator direction).
- **Tipping point for stage ranking.** Let `c` be stage coverage and `p` the early-stage share among known-stage cases. If unknown-stage cases have an early share `p - d`, the overall early share is `p - (1 - c) * d`. Two counties A and B swap rank at
  `d* = (p_A - p_B) / (c_B - c_A)`
  (defined when `c_A != c_B`). Report `d*` in percentage points: the smaller it is, the more fragile the ranking.
- **Glidepath required slope** = `(target - latest value) / (2035 - latest year)`; observed slope is the Theil-Sen estimate with a bootstrap interval.
- **Early warning on monthly series** = EWMA or CUSUM change-point on a county's monthly series, with the reference level fixed from a baseline window.
- **Access intervals (THL Ohjaus 21/2016 definitions):** (1) referral arrival to first treatment, (2) referral arrival to first physician visit, (3) treatment-queue placement to first treatment. Duration bands for comparison: under 2, 2-4, over 4-6, over 6-8, over 8-12 weeks (not recommended times).
- **Distance** (optional) = haversine distance from county population centroid to nearest radiotherapy unit, labelled as a proxy.

### 7.5 The "Pathway Clock" data specification (for the pilot)

Reuse THL's existing definitions and extend them at both ends:

| Time point | Source of definition | Gap it closes |
|---|---|---|
| First symptom contact in primary care | **New** (strategy 2.5: not systematically recorded) | Detection to referral delay |
| Referral arrival at specialised care | THL Ohjaus 21/2016 | Referral stage |
| First physician visit | THL Ohjaus 21/2016 | Referral to diagnosis stage |
| Diagnosis date | Cancer Registry (verify match with Hilmo first-diagnosis date) | Diagnosis stage |
| Treatment-queue placement (treatment decision) | THL Ohjaus 21/2016 | Diagnosis to treatment stage |
| First cancer treatment | THL Ohjaus 21/2016 | Treatment initiation |
| Multidisciplinary team meeting date | **New** (cannot be assessed from Hilmo today) | Coordination quality |

Output is county-level aggregates only (medians and duration-band shares), consistent with the challenge's aggregate-data rule.

---

## 8. Feature specifications and acceptance criteria

**How to read each feature:** *Does* (what it computes), *Verifies* (checks it runs on itself), *Expect* (what correct output looks like, and "if you see X, suspect Y"), *Valid when* (the pass/fail gate).

### 8.1 Three layers of "correct"

A feature is valid only if it passes every layer that applies:
1. **Data correct.** Values match the published source and reconcile to national totals.
2. **Logic correct.** Code reproduces hand calculations and behaves correctly on planted test cases.
3. **Claim correct.** Every sentence a judge hears traces to a value and a source, and claims no more than its evidence grade allows.

**Reconciliation anchors (verified):**
- 2024: 38,853 new cancers and 13,490 cancer deaths in Finland.
- Stage information captured for 42% of cases nationally; 72% in Pirkanmaa; 60% in Sisä-Suomi; 33-42% in the other areas.
- 2024 screening programmes found 2,360 cancers and 5,272 precursor lesions; lowest participation under 68%; goal 80%.
- Lung (2019-2023 report): 27% of patients routed to curative treatment nationally; stage missing for almost half.

Use these as test targets wherever county-level data can be summed back to national figures.

### F0. Data spine (P0)

- **Does:** stores all indicators in the long format of section 7.2, with an indicator catalog and source registry, for 22 units (21 wellbeing counties plus Helsinki).
- **Verifies:**
  - Exactly 22 units, no duplicate keys.
  - Every row's `source_id` resolves to the registry.
  - For proportions, numerator <= denominator and denominator > 0.
  - Every row has an explicit period tag. Values from different periods (for example the pooled 2019-2023 lung report versus the 2024 screening data) are never compared without a visible flag.
  - Suppressed or missing cells stay missing; no silent imputation.
  - Definitions match source footnotes (for example, whether participation is measured among those invited).
  - Provider-based data (such as Hilmo specialised-care indicators) is mapped to the county of residence where the source allows, and flagged `provider-based` otherwise. HUS serves several Uusimaa units, so treat those carefully.
- **Expect:** gaps cluster in the referral, diagnosis and timing stages. If every cell is full, suspect hidden imputation.
- **Valid when:**
  - Schema tests pass 100%.
  - Summed counts match national anchors within +/-1%, and percentages within +/-0.5 pp.
  - A random spot-check of 10 cells against the live source pages gives 10/10 identical values (screenshots saved in an `/evidence` folder).

### F1. Visibility score (P0)

- **Does:**
  - For each county and each of the four pathway stages, computes the weighted share of catalogued indicators that are observable (available, unsuppressed, adequate denominator).
  - Combines the stages into a 0-100 score, with fixed, documented weights.
  - Maps stage-recording coverage to tiers: at least 70% = target, 50-69% = partial, below 50% = low (team-set; 70% is the registry's stated goal).
- **Verifies:**
  - Weights sum to 1 within each stage.
  - Scores stay in [0, 100].
  - Monotonicity: adding an available indicator never lowers a score.
  - The timing indicators (THL access intervals) have zero availability unless a real, current source is loaded. They are never filled with synthetic data in the real view.
- **Expect:**
  - Pirkanmaa at or near the top on stage coverage (72% reported) and the only county at or above the 70% target; if another county exceeds it, re-check the source.
  - The referral stage partly visible if the THL primary-care access series loads, and the timing stage dark if no current THL cancer access report is found.
  - If county-level stage coverage is not public, show cooperation-area values and label them as such.
- **Valid when:**
  - Property tests (range, monotonicity, weights) pass.
  - Hand calculation for 3 counties matches to 1e-6.
  - A test that tries to inject synthetic timing values into the real view leaves the stage dark.

### F2. Gap locator (P0)

- **Does:**
  - For each county and stage, compares each indicator to two references: the county's twin median and the national value.
  - Applies the direction sign so a positive gap always means "worse".
  - Assigns each stage one of four states:
    - **Leak:** significant, practically meaningful, adequately observed.
    - **Watch:** only some of those conditions hold.
    - **OK.**
    - **Unknown:** not observable.
  - Names the primary leak as the stage with the largest verified gap.
- **Verifies:**
  - Significance via a Wilson interval on the county proportion versus the reference.
  - Practical size: gap of at least 3 pp (team-set).
  - Minimum denominator of 30 (team-set), otherwise the value is greyed out.
  - The leak must hold under both references.
  - A stage with visibility below 0.5 (team-set) can never be labelled Leak, only Unknown or Watch.
  - Indicators only feed their own stage.
- **Expect:**
  - Detection is the most observable stage, so most leaks will surface there first.
  - The registry release singles out Helsinki as clearly behind on participation. If the detection layer does not show this, check age bands and programme definitions before trusting the module.
  - Etelä-Pohjanmaa, Etelä-Savo and Kainuu rank among the top participation counties, as the release names them. If they do not, suspect the aggregation across programmes.
  - For lung, the curative-route share varies between counties around the 27% national figure; if every county sits at 27%, suspect a copied national value.
  - If every stage is Unknown, the output must say "cannot localise; the data gap is the finding".
- **Valid when:**
  - *Planted-gap test:* a fixture with an 8 pp gap at n = 2,000 is flagged Leak, and a 1.5 pp gap is not.
  - *Noise test:* over 1,000 pure-noise simulations the false-Leak rate is at most 5% per stage.
  - *Invariance test:* shuffling the county order gives identical results.
  - *Self-reference test:* comparing a county to itself gives a gap of exactly 0.

### F3. Twin benchmark (P1)

- **Does:**
  - Finds the 3 nearest counties by structural covariates: share aged 75+, education, income, density, share of non-Finnish/Swedish speakers, distance to a university hospital.
  - Among those, picks the better-performing ones on the indicator under examination as "better twins". If none is better, reports "leader among peers".
- **Verifies:**
  - **No outcome leakage:** outcome variables are excluded from the distance. Removing them must leave the twin sets unchanged.
  - Symmetry and zero self-distance.
  - Stability: adding +/-5% noise to covariates keeps the twin-set Jaccard overlap at 0.6 or higher (team-set).
  - If the nearest twin is farther than the 90th percentile of all pairwise distances, show "no good twin" and fall back to the national reference.
- **Expect:**
  - Ageing, sparsely populated counties pair with each other; Helsinki has few or no good twins.
  - The tool displays which covariates drive each similarity.
- **Valid when:**
  - Leakage, symmetry and stability tests pass.
  - A team member who knows Finland judges at least 18 of 22 twin lists plausible.
  - A mentor sanity-checks at least 3 pairs.

### F4. Glidepath and early warning (P1)

- **Does:**
  - *Glidepath:* compares each county's observed trend with the linear path to the target (80% screening participation; 70% stage I-II by 2035). Fits a Theil-Sen slope, bootstraps a confidence interval, and projects to the target year.
  - *Early warning:* where a monthly series exists (for example THL primary-care access by county), runs an EWMA/CUSUM change-point detector against a fixed baseline window and flags counties drifting away from their own normal.
- **Verifies:**
  - Annual series with fewer than 4 points show "insufficient data" instead of a guess.
  - A county already at target shows "target met" with no required slope.
  - Indicator direction and period definitions are consistent across years.
  - The stage glidepath appears only where the stage visibility tier allows it.
  - The early-warning detector requires at least 24 monthly points and a documented baseline window (team-set).
- **Expect:**
  - Three glidepath states: On track (median projection at or above target), Off track (upper CI below target), Uncertain (otherwise).
  - The county below 68% should not be "on track".
  - Early warning fires rarely on stable counties and visibly on counties with sustained deterioration.
- **Valid when:**
  - A perfectly linear synthetic series recovers its slope exactly.
  - A single +/-10 pp outlier year does not flip the classification (Theil-Sen robustness).
  - *Calibration:* if enough years exist, fit on all but the last year and check that the 80% interval covers the held-out value in 65-95% of series. If there are too few years, label the glidepath "indicative".
  - *Early-warning test:* on planted step changes of 1 standard deviation the detector fires within 6 months in at least 90% of runs, and the false-alarm rate on stationary noise is at most 5% per year.

### F5. Action engine (P0)

- **Does:**
  - Applies the rule table of section 6. Each rule has an ID, trigger, action, owner, KPI, cost reference, evidence grade, source IDs, and "do not fire if" conditions.
  - Shows the top 3 actions per county. If there is no verified gap, it says "no verified gap; maintain and improve data" instead of forcing a recommendation.
- **Verifies:**
  - Every rule field is non-empty and every source ID resolves.
  - No rule fires on a stage that is Unknown, except the data-capture rules (R-DAT-01, R-DET-02).
  - Hypothesis-graded actions appear only as "test", never "implement".
  - A neutrality lint passes: no brand names, no drug names, no sponsor name in any action text.
  - Rules whose national lead is not the county (for example R-REF-02) are labelled with the correct owner, so the card never asks a county to do what only the ministry can.
  - The same input always yields the same output.
- **Expect:**
  - Any county with low stage coverage always receives the data-capture action first, because it is a precondition for every other claim.
  - Low-participation counties receive the outreach action.
- **Valid when:**
  - Truth-table tests pass 100%: for each rule, a fixture satisfying its trigger fires it, and a fixture violating it does not.
  - A clinical reviewer (for example Kaisa Kaitila on Saturday) rates at least 90% of rules "clinically reasonable and implementable at county level" and none "misleading". Fix or remove any that fail.

### F6. Simulator (P2)

- **Does:**
  - For a screening scenario: extra people screened = eligible population x (target participation - current participation).
  - Converts this into additional detected cancers via a detection rate per 100 screened (with a range), then applies a stage-shift assumption.
  - Runs a Monte Carlo (about 5,000 draws, fixed seed) and reports the median with an 80% interval.
  - Any mortality effect appears only as a literature-based range.
- **Verifies:**
  - Units are consistent, and screened never exceeds eligible.
  - Setting target = current yields exactly zero.
  - Outputs never decrease as the target rises (monotonicity).
  - Every parameter has a low/base/high triple and a source ID.
  - A sensitivity ranking shows which parameter drives the uncertainty.
- **Expect:**
  - Illustrative arithmetic: with 50,000 eligible people and participation rising from 66% to 80%, about 7,000 additional people are screened.
  - Every output carries the label "scenario, not forecast".
- **Valid when:**
  - *Backcast test:* run at baseline participation, the model reproduces the observed 2024 national screen-detected counts within +/-15% per programme. If not, the detection-rate parameter is wrong.
  - All property tests pass.
  - Two runs with the same seed give identical numbers.

### F7. AI analyst and number validator (P0)

- **Does:**
  - Produces a briefing of at most 120 words per county in fixed sections: top finding, where it leaks, confidence, top action, what to verify.
  - The model receives only a structured JSON of computed values and source IDs.
  - Every number in the output carries a source tag.
- **Verifies:**
  - **Number validator:** extracts every number from the text. Each must match a value in the JSON within rounding tolerance. Otherwise the text is regenerated up to 2 times, then replaced by a deterministic template.
  - Causal wording ("causes", "due to") is allowed only for Study-supported rules.
  - Never states an access-time number (for example a median wait to treatment) unless a real, current THL series is loaded for that county.
  - Mentions the limitation whenever visibility is low.
  - Strings from data fields are escaped so injected instructions cannot change behaviour.
- **Expect:**
  - A briefing readable in under 30 seconds.
  - Asked "what is the average time to treatment in Kainuu?", it answers from the loaded THL series if one exists; otherwise it says this is not available here and points to the data-gap panel.
- **Valid when:**
  - Across 22 counties x 3 runs, zero unsupported numbers pass the validator, and 100% of numeric claims have source tags.
  - The fallback template works with the API blocked.
  - A human faithfulness review of 5 counties finds at least 95% of claims traceable.
  - *Clarity test:* 3 people outside the team read a card; at least 2 of 3 can name the leak and the action within 2 minutes.

### F8. Interface (P0, with P1 parts marked)

| Component | Does | Valid when |
|---|---|---|
| **Map (P0)** | 22 polygons coloured by the chosen layer, hatched where visibility is low, colour-blind-safe scale. | 22 of 22 are clickable and tooltip values equal the table values in an automated comparison. |
| **County page (P0)** | Four pathway stages (Leak / Watch / OK / Unknown), confidence badge, twin panel, glidepath, sources drawer. Every grey stage explains why. | Each stage state equals the gap locator output for that county, and every displayed figure appears in the sources drawer. |
| **Action Card (P1)** | One printable page: 3 actions, owner, KPI, cost reference, 90-day pilot, limitations, date. | The PDF builds for all 22 counties in under 3 seconds each, fits on one page, and sampled text equals the on-screen content. |
| **Trust panel (P1)** | A small live badge: counties reconciled, tests passing, unsupported numbers blocked. | Its figures come from the actual test run, not hard-coded text. |
| **Offline mode (P0)** | Everything runs from cached files. | With the network disabled, all 22 counties load, cold start takes under 10 seconds, and cached analyst text appears. |

### F9. Distance to radiotherapy unit (P2, optional)

- **Does:** estimates distance from each county to the nearest radiotherapy unit. The roadmap cites worse NSCLC outcomes beyond about 50 km.
- **Verifies:** a county-seat shortcut understates rural burden, so the figure is labelled a proxy.
- **Valid when:** 3 hand-checked distances agree within +/-10%.

---

## 9. Execution plan

**Team (assumed 4):** data and pipeline; modelling and tests; front end and visualisation; evidence, pitch and mentor liaison. Adjust once the team is confirmed.

### Step 1 (Fri 18:00-20:00): scope and questions
- Freeze scope: lung as the anchor, plus one screened cancer (colorectal or breast). Breast and colorectal also have recommended access times in the THL guidance, which makes them the best cases for any timing view.
- Assign roles, create the repository and the `/evidence` folder.
- Ask the mentors the questions in section 12.
- **Done when:** scope is written on one page and thresholds are frozen in Appendix B.

### Step 2 (Fri 20:00-02:00): data spine
- Attend the 20:00 AstraZeneca insight session and update scope if needed.
- Check, in this order, what actually exists publicly: THL cancer access reports, THL primary-care access database, Cancer Registry statistics application (county granularity), the lung quality report tables.
- Build `county_master.parquet` and `sources.csv`: load screening reports, registry statistics, stage coverage, primary-care access, Sotkanet covariates, StatFin demographics and the NORDCAN benchmark.
- **Done when:** F0 tests pass and a skeleton UI shows all 22 units.

### Step 3 (Sat 08:00-12:00): analytics core
- Implement F1 (visibility), F2 (gap locator), F3 (twins), F4 (glidepath and early warning) and the tipping point.
- **Done when:** unit tests reproduce three hand-calculated counties, and planted-gap and noise tests pass.

### Step 4 (Sat 12:00-16:00): interface skeleton
- Map, county page, funnel view, confidence badges, sources drawer.
- **Done when:** the whole flow runs end to end on real data.

### Step 5 (Sat 16:00-20:00): actions and simulator
- Implement the rule engine (F5) from section 6, with each rule linked to its source.
- Build the simulator (F6) if time allows.
- Ask Kaisa Kaitila to review the action library.
- **Done when:** the Action Card exports as one PDF page for any county, and the clinical review is done.

### Step 6 (Sat 20:00-02:00): AI analyst and hardening
- Implement F7 with the number validator and the fallback template.
- Add the limitations panel, the data-gap panel and the trust panel; cache every demo county.
- **Feature freeze at midnight.**

### Step 7 (Sun 08:00-12:00): rehearsal
- Five full run-throughs, a backup demo video, and at most three slides.
- Run on mobile data and offline to check for network dependence.
- **Done when:** five consecutive offline rehearsals finish with zero validator rejections on the demo counties.

**Cut line.** If you fall behind, drop F6 (simulator) first, then F9, then the early-warning half of F4. Never drop the visibility score or the action card.

### Go/no-go gates

| Gate | Condition |
|---|---|
| Fri 02:00 | Data spine passes schema and reconciliation, and the skeleton UI shows all 22 units. |
| Sat 12:00 | Visibility, gap locator and twin tests are green. |
| Sat 20:00 | All P0 features meet their "Valid when" conditions, and the clinical review is done. |
| Sun 10:00 | Five full offline rehearsals complete with zero validator rejections on the demo counties. |

If a P0 feature misses its gate, fix it before adding anything new. A smaller tool that passes its own tests will beat a larger one that cannot.

---

## 10. Demo, judging alignment and Q&A

### 10.1 Two-minute demo script

1. **0:00-0:20.** "Finland's key Goal 3 measure, treatment within target times, is not yet a published county-level series, and stage is recorded for only 42% of cases."
2. **0:20-0:50.** Map by county; open one. The funnel shows which stage leaks and how confident we are.
3. **0:50-1:20.** Twin comparison and glidepath: "your twin does this better, and you are off track for 2035."
4. **1:20-1:45.** The action card: owner, KPI, cost reference, 90-day pilot.
5. **1:45-2:00.** The ask: a pilot with a wellbeing county, attached to the national referral-criteria and digital-pathway pilots already planned for 2026-2028.

### 10.2 Alignment with judging criteria

| Criterion | How Equal Path answers it |
|---|---|
| Actionability (30%) | Rule-based, costed, owner-assigned actions on a one-page card, each tied to a roadmap measure. |
| Insight (25%) | Stage-localised gaps plus the visibility finding. |
| Data transparency (20%) | Per-field sources, the number validator, hypotheses labelled as hypotheses, unconfirmed data availability stated openly. |
| Execution (15%) | Precomputed data, offline mode and a recorded fallback. |
| Clarity (10%) | One county, one leak, one action in under two minutes. |

### 10.3 Likely judge questions

- **Why not just show time to treatment?** THL defined the monitoring in 2016, but we could not confirm a current public county series, and official cancer-specific targets are still being defined (roadmap 3.1.2, 2026-2028). We show what is verifiable and propose the minimum data to close the rest.
- **Which target times do you use?** Recommended maxima exist only for breast, prostate and colorectal cancer; the tool uses configurable reference times and labels them as indicative.
- **Isn't stage affected by recording quality?** Yes. That is why every stage carries a visibility badge and a tipping-point analysis.
- **How do you know a twin is valid?** Outcomes are excluded from the distance, stability is tested, and a poor-match twin falls back to the national reference.
- **Is this clinical advice?** No. It is decision support for service managers. Actions come from the national strategy and roadmap, and are labelled by evidence grade.
- **What changes with real data?** The same pipeline takes the THL time points plus first primary-care contact and turns the timing stage from "defined" into "measured".

---

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| County-level stage data is not public | Fall back to the five cooperation areas and state it on screen. |
| No current public THL cancer access series | Show the timing stage as "defined, not available" and present the Pathway Clock as the pilot. Never substitute synthetic values in the real view. |
| Hilmo date reliability and provider coverage | State that Hilmo covers public providers and part of private care, and that date reliability was flagged for verification in earlier work. |
| Small-number noise | Show intervals; never rank on raw rates; grey out denominators below 30. |
| Overclaiming | Every simulator output carries assumptions and "scenario, not forecast". |
| Unverified claims reaching the slides | Anything not confirmed appears only as a labelled data gap or hypothesis. |
| Live demo failure | Everything runs from cached files, with a recorded video as backup. |
| Sponsor-bias perception | Product-neutral actions and the neutrality lint. |

---

## 12. Questions for the mentors (Friday 18:00 and the 20:00 session)

1. Is there a current public cancer-specific access report (THL Ohjaus 21/2016 monitoring), and at what geographic level?
2. Which cancers are first in line for the national care-chain descriptions and access-time definitions (roadmap 3.1.2), and which counties are piloting referral criteria and digital pathways?
3. Which cancers show the largest regional variation, and where do experts believe the delay sits?
4. Which interventions have worked or failed in Finnish counties?
5. What would a wellbeing county need to see before agreeing to a joint pilot, and how would it coordinate with FICAN's regional cancer centres?
6. Which reference times should a demo use for lung, where no recommended maximum exists?

---

## 13. Follow-up pitch for AstraZeneca

Propose a 90-day pilot with one wellbeing county, coordinated with FICAN's regional cancer centre and attached to the national pilots the roadmap already plans for 2026-2028 (referral criteria in the most common cancers, limited digital-pathway pilots, quality-register work):
- Capture the Pathway Clock time points (section 7.5) for lung cancer and one other cancer, as county-level aggregates, from the existing county data lake. Reuse THL's definitions and add first primary-care contact and tumour-board date.
- Build the monitoring view and run a monthly equity review.
- The pilot supports the strategy's own data goals (3.2 and 4.1) and the roadmap's structured-recording measure (4.1.1), so the county is asked to start something it is already committed to.

---

## Appendix A: Sources and verification log

| Source | What it supports | Status |
|---|---|---|
| National Cancer Strategy 2026-2035 (STM/FICAN): https://files.hackjunction.app/resources/Kansallinen_syopastrategia_2026_2035_FINAL.pdf | Goal 3 measures (p. 5), stage coverage (p. 30), quality register (pp. 35-36), costs (p. 54) | Verified (read in full, uploaded copy) |
| Implementation roadmap 2026-2031: https://files.hackjunction.app/resources/Kansallinen_syopastrategia_toimeenpanon_tiekartta_2026_2031.pdf | Regional-inequality section, measures 1.2.3, 1.3.1, 1.3.2, 2.3.3, 2.3.4, 2.4.4, 2.4.5, 2.5.1-2.5.3, 3.1.1-3.1.4, 3.2.1-3.2.4, 3.3.1, 3.4, 3.5.3, 4.1.1, cost summary | Verified for those sections. Measures 3.3.2 onwards in 3.3, 3.5.1-3.5.2 and 4.2-4.5 and the cost annex tables were not read. |
| Source link pack: https://files.hackjunction.app/resources/Sy%C3%B6p%C3%A4strategiat%20ja%20sy%C3%B6p%C3%A4data_linkkikokoelma.pdf | List of data sources (Cancer Registry, THL Sotkanet, StatFin, NORDCAN, Kela, Findata, FICAN) | Verified (read) |
| THL Ohjaus 21/2016, Hoitoonpääsyn seuranta syövän hoidossa: https://core.ac.uk/download/78470017.pdf | Access monitoring definitions, 16 cancers, three intervals, recommended maxima for breast, prostate and colorectal cancer, STM 2010 indicative limits, reporting bands | Verified (read in full). Current public reporting to verify. |
| Cancer Society / Cancer Registry press release, Syöpä 2024 report, 17 June 2026: https://www.sttinfo.fi/tiedote/72146240/syovan-levinneisyystiedoissa-suuria-alueellisia-eroja-suomessa?lang=fi | 38,853 cases, 13,490 deaths | Verified |
| Verkkouutiset on the Syöpä 2024 report: https://www.verkkouutiset.fi/a/syopatiedoissa-isot-alueelliset-erot-yksi-seutu-erottuu/ | Stage coverage by area: 42% national, 72% Pirkanmaa, 60% Sisä-Suomi, 33-42% others | Verified |
| Cancer Society release on 2024 screening statistics, 30 June 2026: https://www.sttinfo.fi/tiedote/72173590/kolme-aluetta-erottuu-edukseen-syopaseulonnoissa-helsingissa-osallistuminen-jaa-selvasti-jalkeen?lang=fi | Participation by county, top areas, Helsinki lag, 80% goal | Verified |
| Verkkouutiset on the national lung cancer report (2019-2023): https://www.verkkouutiset.fi/a/keuhkosyopa-todetaan-usein-liian-myohaan-vain-joka-neljas-saa-parantavaa-hoitoa/ | 27% curative route, stage missing for almost half, cell-type gaps, county comparison | Verified (news summary); underlying tables to verify |
| Verkkouutiset on regional lung treatment differences: https://www.verkkouutiset.fi/a/keuhkosyovan-hoidossa-on-suuria-alueellisia-eroja/ | Earlier edition (2018-2022) of the lung work | Verified (news summary); superseded by the 2019-2023 report |
| Verkkouutiset on primary-care access (2023): https://www.verkkouutiset.fi/a/laakarille-paasy-on-hidastunut-selitetaan-tietojarjestelmien-muutoksilla/ | THL primary-care access database reports by county, monthly | Verified for 2023; current availability to verify |
| Hilmo versus Cancer Registry comparison study (2014 data): https://core.ac.uk/download/270319454.pdf | Hilmo diagnosis agreement and open verification needs for referral and treatment dates | Verified |
| Cancer Registry statistics application: https://syoparekisteri.fi/tilastot/tautitilastot/ | Incidence, mortality and survival statistics | URL known; county granularity to verify |
| THL Sotkanet, StatFin, NORDCAN, OECD Cancer Country Profile 2023 | Covariates, benchmark, context | In link pack or strategy; indicators and granularity to verify |

### Still to verify before anything reaches a slide
- Whether a current public THL cancer access report exists, and at what level (county, hospital district, provider).
- Whether stage I-II share and survival are published per wellbeing county or only per cooperation area.
- The exact county tables behind the 2019-2023 lung report.
- Whether the Hilmo first-diagnosis date matches the Cancer Registry diagnosis date.
- Roadmap measures not read (see Appendix A), for further actions and KPIs.

### Resolved in revision 2
- Official target times: no cancer-specific national targets exist yet beyond the THL recommended maxima for breast, prostate and colorectal cancer; FICAN defines the first five in 2026-2028.
- Roadmap sections 2.5, 3.1 and 3.2: read; their actions, schedules and cost estimates are in section 6.

---

## Appendix B: Threshold register (team-set; freeze before analysis)

| Parameter | Value | Used in |
|---|---|---|
| Stage-coverage tiers | 70% target / 50-69% partial / below 50% low | F1 |
| Minimum denominator | 30 | F2 |
| Minimum practical gap | 3 pp | F2 |
| Minimum stage visibility for a Leak or an action | 0.5 | F2, F5 |
| Subgroup gap trigger for outreach | 5 pp | F5 (R-DET-01) |
| Twin stability (Jaccard) | 0.6 | F3 |
| Minimum annual series length for glidepath | 4 points | F4 |
| Minimum monthly series for early warning | 24 points | F4 |
| Early-warning detection and false-alarm targets | 6 months at 1 SD, at least 90%; at most 5% a year | F4 |
| False-Leak rate under noise | 5% or lower per stage | F2 |
| Reconciliation tolerance | +/-1% counts, +/-0.5 pp percentages | F0 |
| Simulator backcast tolerance | +/-15% | F6 |
| Analyst brief length | 120 words | F7 |
| Validator regeneration attempts | 2 | F7 |

---

## Appendix C: Acceptance checklist

**Data (F0)**
- [ ] 22 units, no duplicates
- [ ] Every row has a resolvable `source_id` and an explicit period
- [ ] National anchors reproduced (38,853 / 13,490 / 42% stage coverage / 27% lung curative route)
- [ ] 10-cell spot-check against live sources, screenshots saved
- [ ] Provider-based data flagged; HUS-served units handled

**Analytics (F1-F4)**
- [ ] Visibility property tests and 3 hand-checked counties pass
- [ ] Timing stage dark unless a real current THL series is loaded
- [ ] Planted-gap, noise, invariance and self-reference tests pass
- [ ] Twin leakage, symmetry and stability tests pass; 18/22 twin lists judged plausible
- [ ] Glidepath synthetic-slope and outlier tests pass
- [ ] Early-warning step-change and false-alarm tests pass (if monthly data loaded)

**Actions and simulation (F5-F6)**
- [ ] Rule truth tables pass 100%; neutrality lint clean; owners correct
- [ ] Clinical review at least 90% reasonable, none misleading
- [ ] Simulator backcast within +/-15%; fixed-seed reproducibility

**AI analyst (F7)**
- [ ] Zero unsupported numbers across 22 x 3 runs
- [ ] No access-time number stated without a loaded real series
- [ ] Fallback template works offline
- [ ] 2 of 3 outside readers can name the leak and action within 2 minutes

**Interface and demo (F8)**
- [ ] 22 of 22 counties clickable and consistent with the tables
- [ ] Action Card PDF under 3 seconds, one page
- [ ] Offline cold start under 10 seconds
- [ ] Five consecutive offline rehearsals with zero validator rejections
- [ ] Backup demo video recorded

---

## Appendix D: Reference time limits (indicative; configurable in the tool)

These come from the STM working group on cancer care development (STM Selvityksiä 6/2010), restated on p. 13 of THL Ohjaus 21/2016, where their introduction was proposed as indicative. They are **not** binding national targets and are not cancer-specific. Cancer-specific access times for the first five cancers are due from FICAN in 2026-2028 (roadmap 3.1.2).

| Interval | Indicative limit |
|---|---|
| Referral arrival to first treatment (suspected cancer) | 6 weeks |
| Very urgent cancers: diagnosis to treatment start | Within days, at most 2-3 weeks |
| Imaging: radiologist report after the request | 1 week |
| Tissue sample (biopsy or needle sample) after the request arrives at the unit | 1 week |
| Pathologist report after the sample, when no special stains are needed | 1 week |
| Adjuvant (radiotherapy or drug) treatment after surgery | 4 weeks, unless a patient-related reason requires longer |

Recommended maxima for breast, prostate, colon and rectal cancer pathways (from queue placement, weeks to months) are in Figures 2-5, pp. 18-19 of the guidance. Read them directly from the source before using any value.
