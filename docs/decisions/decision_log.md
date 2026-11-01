# Research decision log

Each entry records a decision, its rationale, its methodological basis, and its effect on the analysis.
**Type** distinguishes *protocol* decisions (made before seeing screening/extraction results) from *post-hoc* decisions (made after). Post-hoc decisions must be reported as such in the manuscript.

## Decided

### D001 — Preserve the original PubMed search as v1
- **Type:** protocol
- **Decision:** The executed PubMed query and its export are kept unchanged as search v1. Any refinement becomes a new, separately documented version; records from all versions are merged and deduplicated.
- **Rationale:** Reproducibility; PRISMA-S requires the exact strategy as run.
- **Impact:** None on results; enables an audit trail across search versions.

### D002 — Raw exports are read-only
- **Type:** protocol
- **Decision:** Files in `data/raw/` are never modified; every transformation is scripted and writes to `data/processed/`. Checksums are recorded.
- **Rationale:** Traceability from every number in the manuscript back to the source export.
- **Impact:** None on results.

### D003 — Adopt the evidence-provenance rules
- **Type:** protocol
- **Decision:** `docs/protocol/provenance_rules.md` governs all stages. It covers no fabrication, immutable raw inputs, the report/study distinction, a separate alcohol-adjustment field, no automatic harmonisation of exposure categories, outcome-site eligibility, and the analysis gate.
- **Rationale:** Set by the review lead before any data handling.
- **Impact:** Constrains extraction and analysis design. No pooled analysis is run before the gate conditions and the SAP are met.

### D004 — Separate identifiers for records, reports, studies and estimates
- **Type:** protocol
- **Decision:** `record_id` (database record) → `report_id` (unique publication, after deduplication) → `study_id` (unique population, by human judgement at full text) → `estimate_id`. The unit of analysis is `study_id`.
- **Rationale:** Prevents duplicate publications and overlapping cohorts from being counted as independent studies.
- **Impact:** Determines the number of studies (k) in every analysis.

### D005 — If the original v1 export is lost, it is not recreated
- **Type:** protocol
- **Decision:** A new PubMed retrieval, even with the identical query, is recorded as a new search version with its own date and count. It is never labelled v1.
- **Rationale:** PubMed content changes over time, so a re-run is a different search.
- **Impact:** The PRISMA flow would report the search that was actually used.

### D006 — Checksum registration semantics
- **Type:** protocol (engineering)
- **Decision:** The SHA-256 is registered once, on first verified import. Registration requires the record count to equal the count reported at search time. Later runs fail on any mismatch.
- **Rationale:** No checksum was recorded when v1 was downloaded, so registration establishes integrity only from import onward. Provenance of the file itself relies on its origin and the count check.
- **Impact:** None on results.

### D007 — Tests contain no bibliographic content
- **Type:** protocol (engineering)
- **Decision:** Unit tests use format fragments and structural stubs only. Tests on real data run against the registered raw exports and are skipped when the exports are absent.
- **Rationale:** No synthetic citations may exist in the repository (provenance rule 6).
- **Impact:** None on results.

### D008 — Outcome definition (resolves P001)
- **Type:** protocol
- **Decision:** Eligible outcome is cancer of the **oral cavity** where squamous cell carcinoma is histologically confirmed, or where SCC is a stated majority of **≥90%** of cases. Histological confirmation and the reported SCC proportion are extracted as fields. Estimates that pool the oral cavity with the oropharynx, larynx, pharynx or "head and neck" as a single outcome are **not eligible** unless an oral-cavity-specific estimate is reported separately.
- **Rationale:** Restricting to the literal phrase "oral squamous cell carcinoma" would capture a non-representative subset, because most aetiological case-control literature reports "oral cancer" or "oral cavity cancer" and states squamous histology in the methods. The ≥90% threshold keeps the synthesis aligned with the research question while admitting studies that report a small non-SCC minority. The exclusion of pooled head-and-neck outcomes follows provenance rule 12: anatomical subsites have different aetiology (notably HPV in the oropharynx).
- **Basis:** SCC accounts for the large majority of oral cavity malignancies; subsite-specific analysis is standard in head-and-neck epidemiology.
- **Impact:** Widens eligibility relative to search v1; makes the v1 outcome block (`"Oral Squamous Cell Carcinoma"[tiab] OR OSCC[tiab]`) demonstrably too narrow, which is the principal argument for a v2 search. Creates a planned sensitivity analysis restricted to 100%-SCC studies.

### D009 — Exposure definition (resolves P002)
- **Type:** protocol
- **Decision:** The exposure is **any smoked tobacco** — cigarettes, bidis, cigars, pipes and other combusted tobacco products. The product type(s) are extracted for every estimate, supporting a planned subgroup analysis of cigarette-only versus mixed or other products. **Smokeless tobacco and betel quid / areca nut are not exposures**; they are extracted as potential confounders, as is alcohol.
- **Rationale:** A cigarette-only review would exclude much of the most informative literature, particularly South Asian studies of bidi and reverse smoking, where the exposure burden is greatest. Combusted products share the relevant carcinogenic mechanism. Smokeless tobacco and betel quid have distinct dose–response relationships and are strongly associated with both smoking and oral cancer, so they are confounders rather than part of the exposure.
- **Impact:** Widens eligibility. Introduces exposure heterogeneity that the product-type subgroup analysis is designed to examine. Aligns the protocol with the README title ("Tobacco Smoking"); the narrower wording "cigarette smoking" in the original research question is superseded and the question is restated accordingly.

### D010 — Single-reviewer screening and extraction (resolves P005)
- **Type:** protocol
- **Decision:** Screening and data extraction are performed by one human reviewer. This is reported as a limitation under PRISMA 2020 items 8 and 9. Consequences carried through the pipeline: reviewer identity is recorded on every decision; any automated pre-sort is stored in a separate `suggestion` field that can never satisfy a `decision` field; and the review is never described as independently duplicated.
- **Rationale:** Resource constraint, declared openly rather than overstated.
- **Basis:** PRISMA 2020 requires reporting how many reviewers screened each record and whether they worked independently. Single-reviewer screening raises the risk of erroneous exclusion.
- **Impact:** A recognised limitation affecting the reliability of study selection and extraction. It does not alter effect estimates, but it must appear in the Limitations section. Automated tooling is not a reviewer and is not reported as one.

### D011 — Separate registry entries for separate search executions
- **Type:** protocol
- **Decision:** `config/sources.yaml` records one entry per database × **execution**, with an `execution` type (`historical` / `re_execution` / `new`), a `status` (`export_missing` / `awaiting_registration` / `registered`), the `filters_applied` **actually** used, and a `count_source` stating where `expected_records` came from. The historical v1 execution keeps the id `pubmed_v1` with `raw_file: null` and `status: export_missing`; the October 2026 re-run of the same query is a separate entry, `pubmed_v1r`. No entry is created for a merely drafted search, because an entry asserts that an export exists.
- **Rationale:** A 194-record export of the v1 query string arrived while the registry had a single `pubmed_v1` slot expecting 138 records. Registering it there would have misrepresented a later re-execution as the original search. The database's content changes over time and the filters actually applied may differ, so a re-run is a different search even with an identical query string.
- **Basis:** PRISMA-S requires the strategy, platform, filters and date **as run** for each search. D005.
- **Impact:** The PRISMA flow attributes records to the execution that actually produced them. `pubmed_v1` contributes no records unless its export is recovered. The 138 figure is retained as an unverified documented claim and is **not** changed to 194.

### D012 — Re-execution export renamed
- **Type:** protocol (engineering)
- **Decision:** The export was renamed from `pubmed-OralSquamo-set.nbib` to `pubmed-v1r-reexecution-194.nbib` before registration. File content was not touched; the SHA-256 is unchanged at `1d153fa8…27e4ca1e` (verified before and after).
- **Rationale:** A re-execution must not occupy the original export's filename. The original name is left free in case the original export is ever recovered.
- **Impact:** None on results.

### D013 — Retrieve unfiltered; apply language and species limits at screening (resolves P011)
- **Type:** protocol — **deviation from the v1 strategy, to be reported as such**
- **Decision:** Searches are run **without** the Humans and English database filters. The 194-record unfiltered set is retained. Non-English and non-human records are excluded at screening with a recorded reason code (`not_english`, `wrong_population`).
- **Rationale:** The Humans filter operates on the MeSH term `Humans`, so it discards every record PubMed has not yet indexed — 42 of the 194 records here, which are the most recent and therefore plausibly among the most relevant. A screening-level exclusion is auditable and appears in the PRISMA flow; a database filter removes records invisibly.
- **Basis:** Standard guidance against species filters in sensitive searches; PRISMA 2020 expects exclusions to be reported with reasons.
- **Impact:** Eligibility criteria are **unchanged** (English, human) — only the point of application moves. `not_english` and `wrong_population` will carry non-zero counts in the PRISMA flow. Screening volume rises by the number of records a filter would have removed.

### D014 — Identifier priority for deduplication, and the fallback for records lacking identifiers
- **Type:** protocol
- **Decision:** Records are matched in order of decreasing authority: **PMID**, then **DOI**, then an exact fingerprint of normalised title + first-author surname + year. Where several criteria match one pair, the strongest is the one reported as the merge reason. Records whose titles are merely *similar* (same year, sequence similarity ≥ 0.92) are flagged `needs_review` and **never merged automatically**; the stage exits non-zero while any remain unresolved. Normalisation is used only for comparison and never overwrites the citation dataset. Empty keys never match.
- **Rationale:** PMID is PubMed's own stable key for a citation, whereas DOI strings vary in form and are occasionally shared between records or recorded incorrectly, so PMID is the more reliable evidence when both are present. The fingerprint is the documented fallback for records carrying neither identifier; it requires all three components, so a record missing any of them matches nothing on that tier and can only be caught as a review candidate. A near-identical title may be a conference abstract, an erratum, a reanalysis or a different paper, which is a judgement only the reviewer can make (D010).
- **Impact on results:** **None on grouping.** Group membership is the transitive closure of all exact tiers and is therefore independent of their order; this was verified against both constructed cases and all 194 records of `pubmed_v1r`, which produced identical groups and identical `report_id` assignments under both orders. The priority changes only which criterion is *reported* as the reason for a merge.
- **Defect corrected:** before this decision the reported merge reason was decided by alphabetical sorting of the criterion strings, not by any priority. A pair that shared a PMID could therefore be recorded as an `identical title + first author + year (no shared identifier)` match — a false statement about the evidence, since the records did share an identifier. The criterion label no longer asserts the absence of identifiers, and the reason is now selected by priority. This affects only the audit trail's accuracy, not which records were grouped.

### D015 — Python + SciPy as the statistical implementation (resolves P008)
- **Type:** protocol (engineering with methodological consequences)
- **Decision:** The meta-analysis is implemented in **Python with SciPy** (`scripts/analysis/`). R and `metafor` are **not** used, and **no cross-validation against `metafor` is claimed**.
- **Rationale:** Approved by the reviewer. SciPy was already available, which avoided installing and learning a second toolchain under time pressure. The implementation is fully readable and sits inside the existing tested pipeline rather than beside it.
- **Basis / validation:** Cochran's Q p-value and the I² formula are checked against published values (Cochrane Handbook v6.5 §10.10.4.5); the fixed-effect and DerSimonian–Laird paths against arithmetic worked by hand in the tests. Full record: `docs/methods/analysis_validation.md`.
- **Limitations, explicitly accepted:** **(a)** REML has **no external validation** — it is tested only for self-consistency (its τ² is a fixed point of its own update) and limiting behaviour, so it establishes that the implementation solves the equation it encodes, not that the equation is correct. Every REML result carries this caveat in its own notes, and a REML estimate should be checked against `metafor::rma(method="REML")` before it appears in a manuscript. **(b)** The pooled estimate, weights and τ² have no external reference check, because no published worked example with per-study data was accessible. **(c)** No Hartung–Knapp–Sidik–Jonkman interval, which the Cochrane Handbook favours when k > 2 and τ² > 0 — the likely situation here. **(d)** No Mantel–Haenszel or Peto methods, so rare-event and zero-cell data have no route. **(e)** No meta-regression or dose–response model.
- **Impact:** All statistics are reproducible from the repository with pinned dependencies. The limitations above must appear in the manuscript's methods and limitations sections. `run_analysis.py` refuses to run until extracted study data exist, so no pooled estimate can be produced prematurely.

## Pending — require the review team's decision

**P014–P022 are the anatomical and histological decisions.** The evidence for them, with sources,
access dates and the distinction between verified facts and interpretation, is in
`docs/protocol/anatomical_histological_scope.md`. Recommendations are in
`docs/methods/protocol_decisions_for_researcher.md`. **None is adopted**; D008 remains the
operative outcome definition until the reviewer decides.

| ID | Question | Why it matters | Needed before |
|---|---|---|---|
| P003 | Reference group: never-smokers only, or accept "non-smokers" (which may include former smokers)? *Recommendation: accept both, record the comparator verbatim, restrict the primary analysis to a never-smoker reference, and add a sensitivity analysis including undefined "non-smoker" references.* | Mixing reference groups biases pooled estimates toward the null. | Extraction / SAP |
| P004 | Primary exposure contrast: ever vs never, current vs never, or both as separate analyses? *Recommendation: primary ever vs never; secondary current vs never and former vs never; dose–response only where categories are comparable, with no forced harmonisation; one estimate per study per analysis.* | Defines the primary analysis. | Extraction / SAP |
| P006 | Protocol registration (e.g., PROSPERO) before screening begins? | Registration after screening weakens the protocol/post-hoc distinction. | Screening |
| P007 | Additional databases (Embase, Scopus/Web of Science) and supplementary methods (reference lists, citation searching); constrained by institutional access. | Search sensitivity; PRISMA/MOOSE expectations. | Search v2 |
| P008 | *Resolved by **D015*** — Python + SciPy, with no claim of R/`metafor` cross-validation. | — | — |
| P009 | Date the v1 search was run. | Required for PRISMA-S reporting. Cannot be derived: the latest `EDAT` in the export is a lower bound only, and file timestamps and today's date are not substitutes. | Milestone A |
| P010 | Does the prohibition on synthetic data (rule 20, D007) permit clearly labelled synthetic *test fixtures* outside `data/`? Current code follows the stricter reading: format fragments and structural stubs only, never under `data/`, never usable as evidence. | A provenance-rule amendment; affects only test design, not results. | Any further test work |
| P011 | *Resolved by **D013*** — retrieve unfiltered, apply language and species limits at screening. | — | — |
| P012 | The documented v1 count of 138 cannot be fully reconciled. The same query string run on 2026-10-29 returns 194 unfiltered and **150** with Humans + English applied; 3 records postdate the 2026-09-20 pause, leaving **~9 records unexplained**. Candidate explanations — records that have since become MeSH-indexed and so entered the filtered set, or an approximate original figure — cannot be distinguished without the original export or the original search date. | Affects only how the search history is reported, not which records are screened: the screened set comes from `pubmed_v1r`. Must be disclosed in the search-reporting section rather than reconciled by altering 138. | Manuscript (search reporting) |
| P014 | **Eligible oral-cavity subsites.** Adopt an explicit subsite list rather than a code range? `C02–C06` is unsafe: it admits C02.4 (lingual tonsil) and C05.1/C05.2 (soft palate, uvula). | Determines which studies are eligible at full text. | Full-text screening |
| P015 | **Lip (C00).** Part of the primary outcome, excluded on aetiological grounds, or included with separate and sensitivity analysis? Lip **is** anatomically oral cavity, so excluding it is a deliberate choice. The external/mucosal split is codeable for C00.0–C00.5 but not for C00.6/C00.8/C00.9. | Changes the evidence base and the primary estimate. | Full-text screening |
| P016 | **Soft palate and uvula (C05.1, C05.2).** Adopt the TNM convention (oropharynx) or NCIt's anatomical description (posterior oral cavity)? The sources genuinely conflict; the protocol must state which convention it adopts rather than assert a fact. | Determines eligibility for a whole subsite group. | Full-text screening |
| P017 | **Straddling unspecified/overlapping codes:** C02.8, C02.9, C05.8, C05.9, C06.80. Exclude, or include under a stated assumption? These cannot be assigned to a compartment from the code alone. | Affects borderline studies and the PRISMA exclusion counts. | Full-text screening |
| P018 | **Registry-grouped studies.** SEER's "Tongue" (C019–C029) and "Gum and Other Mouth" groups mix eligible and ineligible subsites. Exclude as non-separable, or include with contamination documented? | A strict rule may exclude good studies for reporting coarsely — selection on reporting quality. | Full-text screening |
| P019 | **Site-purity threshold.** D008 sets a ≥90% threshold for histology but none for anatomy. Adopt a parallel site threshold, or stratify a sensitivity analysis by reported purity? No threshold can be calibrated from available evidence. | Determines handling of mixed-site studies. | Extraction / SAP |
| P020 | **Definition of "separately reported"** in D008: does it require a site-specific **effect estimate**, or do site-specific **case counts** suffice? | Changes whether multi-site studies are eligible. | Full-text screening |
| P021 | **SCC variants.** Do verrucous (8051/3), basaloid (8083/3), papillary (8052/3) and spindle-cell squamous (8074/3) count as SCC for the ≥90% rule? | Determines histological eligibility. **Requires the WHO Blue Book, which was inaccessible.** | Extraction |
| P022 | **Non-SCC and borderline entities.** Adenosquamous (8560/3) and sarcomatoid NOS (8032/3, 8033/3) excluded but retained in the ≥90% denominator? Is primary SCC of a **minor** salivary gland eligible — C06.9 explicitly admits "minor salivary gland, unspecified site"? | Determines histological eligibility. **Requires the WHO Blue Book.** | Extraction |
| P013 | **v2 retrieval volume.** The drafted v2 query returns **4,770** records against v1r's 194 (counts validated 2026-10-29). Under single-reviewer screening (D010) that is roughly 20 hours of title/abstract work. Options: **(a)** screen all 4,770 — most sensitive, highest workload; **(b)** keep v2 as the primary search but add a second human screener for the title/abstract pass, revisiting D010; **(c)** treat v1r (194) as the primary set and v2 as a supplementary search, screening only v2 records not already in v1r — far less sensitive, and the shortfall must be stated as a limitation; **(d)** restrict the v2 design block to MeSH terms only, which drops the free-text aetiology terms and so loses unindexed records. **No option is adopted; the query is not narrowed for convenience.** | Determines the review's sensitivity and whether the search can honestly be called systematic. | Executing v2 |
