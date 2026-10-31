# Protocol decisions awaiting the reviewer

**Nothing here is adopted.** Each entry gives the question, the options, their trade-offs, a
recommendation and its consequences. A recommendation is a recommendation; it becomes protocol only
when recorded as a D-entry in `docs/decisions/decision_log.md`.

**Resolved since the last round:** **P008 → D015** (Python + SciPy, no `metafor` cross-validation
claimed). **P011 → D013.**

Ordered by how much each blocks. The first two block the most and are the cheapest to answer.

---

## Tier 1 — blocks full-text screening, answerable now

### P003 · Reference group

**Question.** Is a study eligible when its reference group is an undefined "non-smoker" category,
which may include former smokers — or only when it is explicitly never-smokers?

| Option | Advantages | Disadvantages |
|---|---|---|
| **A. Never-smokers only** | Cleanest contrast; no dilution | Excludes many older case-control studies; may leave too few studies to synthesise |
| **B. Accept both; primary restricted to never-smoker reference; sensitivity analysis adds the rest** | Preserves all evidence while keeping the distinction visible; reuses the planned sensitivity machinery | If few studies have a clean reference, the "primary" may end up chosen after seeing the counts — which is post-hoc and must be reported as such |
| **C. Accept both; pool together** | Largest k; simplest | Former smokers inside the reference group attenuate the estimate toward the null by an unknown amount; needs explicit justification against provenance rule 6 |

**Recommendation: B.** It is the only option that keeps the attenuation measurable rather than
assumed. Guard against the post-hoc risk by fixing now, in writing, what happens if too few
never-smoker-reference studies exist — I suggest: if fewer than 3, the mixed set becomes the
primary with the limitation stated.

**Consequences.** Screening: `no_reference_group` stays a full-text reason. Extraction:
`comparator_type` records `never_smoker` / `non_smoker_undefined` / `other` verbatim. Synthesis:
one extra prespecified sensitivity analysis.

### P004 · Primary exposure contrast

**Question.** Which contrast is the primary analysis — ever vs never, current vs never, or both?

| Option | Advantages | Disadvantages |
|---|---|---|
| **A. Ever vs never** | Most commonly reported, so maximises contributing studies | Mixes current and former smokers, whose risks differ; the pooled estimate averages over an unmeasured mix |
| **B. Current vs never** | Biologically sharper; avoids former-smoker dilution | Fewer studies report it separately; lower k, wider intervals; vulnerable to reverse causation in case-control designs if diagnosis prompted quitting |
| **C. Both as co-primary** | No information lost | Multiplicity; the same study contributes to both, so the analyses are not independent |
| **D. Dose–response as primary** | Strongest coherence evidence | Needs comparable categories across studies; provenance rule 9 forbids auto-harmonising, so k would likely be small |

**Recommendation: A primary, with B and former-vs-never as prespecified secondary analyses**, and
dose–response only if comparable categories turn out to exist. One estimate per `study_id` per
analysis is already fixed by D004.

**Consequences.** Extraction: `exposure_contrast` enumerates `ever`/`current`/`former`/`dose_tier`.
SAP §2 can then be completed. Screening is largely unaffected — P004 touches title/abstract only
through the `no_usable_data` boundary.

---

## Tier 2 — anatomical and histological scope

Evidence, with sources and access dates: **`docs/protocol/anatomical_histological_scope.md`**.
These nine were previously unrecorded in the repository and are now numbered **P014–P022**.

### P014 · Eligible subsite list

**Question.** Adopt an explicit subsite list instead of a code range?

**This is not really optional.** `C02–C06` admits **C02.4 (lingual tonsil)** and **C05.1/C05.2
(soft palate, uvula)**, all oropharyngeal under TNM — VERIFIED from ICD-10-CM inclusion terms. A
range cannot express the protocol.

**Recommendation.** Adopt the explicit list: C02.0–C02.3, C03 (all, including C03.9), C04 (all,
including C04.8/C04.9), **C05.0 only**, C06.0–C06.2, C06.89, C06.9. Treat codes as illustrative,
not required of studies — most papers report no codes at all.

### P015 · Lip

**Question.** Include lip in the primary outcome, exclude it, or include it with separate analysis?

Lip **is** part of the oral cavity (SEER anatomy, VERIFIED). Excluding it is an **aetiological**
choice: external/vermilion lip SCC is predominantly UV-driven.

| Option | Advantages | Disadvantages |
|---|---|---|
| **A. Exclude all lip** | Removes a UV-driven outcome; cleanest aetiologically | Studies reporting "oral cavity including lip" without separation become pooled-outcome exclusions |
| **B. Mucosal lip only** | Ideal in principle; codeable for C00.0–C00.5 | **Largely unimplementable** — SEER groups all lip as C000–C009 and few studies report by aspect, so B collapses toward A while costing more screening effort |
| **C. Include, analyse separately, sensitivity analysis** | Largest evidence base; makes the lip contribution measurable instead of assumed | Needs `lip_proportion` extracted; primary estimate includes a differently-caused outcome |

**Recommendation: C**, with A as a defensible alternative if you prefer aetiological purity over
evidence-base size. **I am not choosing** — this one genuinely turns on what you want the review
to claim.

### P016 · Soft palate and uvula

**Question.** TNM convention (oropharynx) or NCIt's anatomical description (posterior oral cavity)?

The sources **conflict**: SEER's TNM description assigns them to the oropharynx; NCIt describes the
soft palate as posterior oral cavity; ICD-10-CM and SEER's recode place all of C05 in oral
groupings.

**Recommendation.** Adopt the **TNM convention** — it is what published studies will have followed,
and the HPV aetiology of oropharyngeal sites is the reason D008 excludes pooled head-and-neck
outcomes. State it as **a convention adopted**, never as an anatomical fact.

### P017 · Straddling unspecified/overlapping codes

**Question.** C02.8, C02.9, C05.8, C05.9, C06.80 — exclude, or include under a stated assumption?

**Recommendation.** Exclude with a dedicated reason code, since the compartment genuinely cannot be
determined — but record them separately from substantive exclusions so the PRISMA flow shows how
much evidence is lost to coarse reporting rather than to ineligibility.

### P018 · Registry-grouped studies

**Question.** SEER's "Tongue" (C019–C029) and "Gum and Other Mouth" groups mix eligible and
ineligible subsites — VERIFIED. Exclude as non-separable, or include with contamination documented?

**Recommendation.** Include with contamination documented, and stratify a sensitivity analysis by
reported purity. Excluding them selects on **reporting granularity rather than study validity**,
which is its own bias. Requires disciplined extraction of composition for every study, or the
"documented" claim is empty.

### P019 · Site-purity threshold

**Question.** Adopt a threshold parallel to the ≥90% histology rule, or stratify instead?

**No threshold can be calibrated from available evidence** — justifying 90% over 80% would need
subsite-specific smoking effect estimates to model the bias.

**Recommendation.** No hard threshold. Record the reported subsite composition for every study and
run a **purity-stratified sensitivity analysis**, letting the data show whether contamination
matters rather than asserting a cut-off.

### P020 · What "separately reported" means

**Question.** Does D008 require a site-specific **effect estimate**, or do site-specific **case
counts** suffice?

**Recommendation.** Require a site-specific **effect estimate** — the stricter reading, and the
natural reading of D008's wording. Counts alone would require me to compute an estimate the authors
did not report, which is a derivation, not an extraction.

### P021 · SCC variants

**Question.** Do verrucous (8051/3), basaloid (8083/3), papillary (8052/3) and spindle-cell
squamous (8074/3) count as SCC for the ≥90% rule? Codes VERIFIED via NCIt.

**Recommendation.** Count basaloid, papillary and spindle-cell squamous as SCC — all three are
explicitly squamous in NCIt's own terms and definitions. Verrucous is **genuinely uncertain**: its
NCIt definition does not state that it is squamous.

**⚠ This needs the WHO Classification of Head and Neck Tumours 5th ed., which was inaccessible.**
My recommendation rests on NCIt terminology, not on WHO's formal variant list. Treat it as
provisional until the Blue Book is checked.

### P022 · Non-SCC and borderline entities

**Question.** Adenosquamous (8560/3) and sarcomatoid NOS (8032/3, 8033/3) excluded but kept in the
≥90% denominator? Is primary SCC of a **minor** salivary gland eligible?

**Recommendation.** Exclude adenosquamous and sarcomatoid NOS as distinct entities, but count them
in the denominator so they consume the 10% allowance. Minor salivary gland SCC: eligible if
reported as oral-cavity SCC, recorded in notes — note that C06.9 explicitly admits "minor salivary
gland, unspecified site", so it is eligible under D008 as currently written whether or not that was
intended. **Also needs the Blue Book.**

---

## Tier 3 — process and reporting

### P006 · Protocol registration

**Question.** Register on PROSPERO (or elsewhere) before screening begins?

**Recommendation: register before screening.** Free, and the standard expectation. Registering
*after* screening destroys the evidential value of the protocol/post-hoc distinction that this
project's decision log exists to preserve. **Note the ordering problem:** P003, P004 and P014–P022
are protocol content a registration must state, so P006 cannot sensibly be completed before them.
If registration would delay screening unacceptably, the honest alternative is to screen unregistered
and declare it — but then every decision rests on the decision log alone, with no external timestamp.

**This is your action; I cannot register on your behalf.**

### P007 · Database coverage

**Question.** Which databases beyond PubMed, and which supplementary methods?

**No access status is documented anywhere in the repository**, so Tier-2 items below are
conditional on your library.

- **Free, do regardless:** Europe PMC · **IndMED/IMSEAR** and **LILACS/SciELO**, justified
  specifically because D009 admits bidi, beedi, kretek and reverse smoking, whose literature is
  concentrated in South Asian and Latin American journals with incomplete MEDLINE indexing ·
  reference-list checking of included studies and prior meta-analyses · forward citation checking.
- **Verify with your library:** **Embase** (highest added value) · **one** of Scopus or Web of
  Science, for citation searching.
- **Supplementary only:** Google Scholar — not reproducible, never a primary source.

**Recommendation.** Record the access status of every database considered, **including "no
access"**, as a documented limitation. An unavailable database that is named and explained is
defensible; silence is not. **Settle P007 before finalising P013** — each database adds its own
strategy, registry entry and screening volume.

### P013 · v2 retrieval volume

**Question.** The drafted v2 query returns **4,770** records against v1r's **194** (both measured
2026-10-29). Under single-reviewer screening (D010) that is **13–60 hours** of title/abstract work
at an assumed 10–45 s per record.

**A measured finding that removes one option:** v1r is a **strict subset** of v2
(`v1 NOT v2 = 0`). So "screen only v2 records not already in v1r" means 4,576 instead of 4,770 — a
**4% saving**, not a workload strategy.

| Option | Volume | Note |
|---|---|---|
| **A. Run v2 as drafted** | 4,770 | Most sensitive; highest workload |
| **B. v2 + a second screener** | 4,770 | The only route that addresses workload without losing sensitivity; revisits D010 |
| **C. Restrict the design block to MeSH only** | 3,282 (−31%) | Loses the unindexed records the free-text terms exist to reach |
| **D. Keep v1r as the only search** | 194 | Feasible today, but PubMed-only with a narrow query; sensitivity must be stated as a major limitation |

**Recommendation.** For a defensible review, **A** (or **B** if a second screener is available). For
a demonstrable milestone today, **D** with the limitation stated plainly — and that is a legitimate
staged plan, provided the write-up does not imply v2 was executed. **No option is adopted**, and
the query is **not** narrowed for convenience.

---

## The minimum set of questions

Answer these four and screening plus extraction are unblocked:

1. **P003** — recommendation B?
2. **P004** — recommendation A primary, B secondary?
3. **P015 (lip)** — A, B or C? *The one where I decline to recommend.*
4. **P013** — A, B, C or D for today?

These four need nothing I cannot supply, and no library or paywalled source.

Then, when convenient: **P014, P016, P017, P018, P019, P020** (recommendations above, all
actionable now) · **P021, P022** (need the WHO Blue Book) · **P006, P007** (your actions).
