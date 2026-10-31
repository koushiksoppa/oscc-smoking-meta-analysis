# Data dictionary — extraction schema (specification)

**Status: SPECIFICATION. No extraction has been performed and no extraction file exists.**
Fields marked ⏳ depend on P003/P004. The schema is implemented in code only once those are settled.

Three principles govern every field:

1. **Reported ≠ calculated.** A value copied from the paper and a value derived from it never share a
   field. Derived fields carry a `_calc` suffix and a `derivation` note.
2. **Missing is a value.** Use `NR` (not reported), `NA` (not applicable) or `UNCLEAR`. Never blank,
   never zero, never inferred.
3. **Every number has a location.** `source_location` is required for each extracted estimate.

## Table 1 — `studies` (one row per `study_id`)

| Field | Type | Notes |
|---|---|---|
| `study_id` | id | Unique study population (D004). Unit of analysis. |
| `report_ids` | id list | All publications of this population; `;`-separated |
| `primary_report_id` | id | The report used for extraction when several exist |
| `pmid`, `doi` | text | Of the primary report |
| `first_author`, `pub_year`, `journal`, `country` | text | As reported |
| `source_database`, `search_version` | text | Provenance (rule 4) |
| `full_text_source` | text | How the full text was obtained |
| `design` | enum | `case_control`, `cohort` |
| `design_detail` | enum | `prospective`, `retrospective`, `nested_case_control`, `UNCLEAR` |
| `setting` | enum | `hospital_based`, `population_based`, `UNCLEAR` |
| `centres` | enum | `single`, `multi`, `UNCLEAR` |
| `recruitment_period` | text | As reported |
| `n_total`, `n_cases`, `n_controls` | int | `NA` for cohorts without a control group |
| `n_exposed`, `n_unexposed` | int | Where reported |
| `person_years` | num | Cohorts; `NA` otherwise |
| `age_summary`, `sex_distribution` | text | As reported, with the statistic named |
| `outcome_ascertainment` | text | Registry, pathology records, etc. |
| `histology_confirmed` | enum | `all`, `partial`, `NR` (D008) |
| `scc_proportion` | num | Reported % SCC; must be ≥90 or `all` for eligibility (D008) |
| `anatomical_sites` | text | Subsites included, as reported |
| `site_separable` | bool | Whether an oral-cavity-specific estimate exists (D008) |
| `case_definition` | text | Incident/prevalent, ICD codes if given |
| `extracted_by`, `extraction_date` | text | Reviewer identity (D010) |
| `extraction_confidence` | enum | `high`, `moderate`, `low` |
| `notes` | text | |

## Table 2 — `estimates` (one row per reported effect estimate)

Every estimate the paper reports is preserved, including crude ones (rule 8). Selection of which
estimate enters an analysis happens later and is recorded separately — never by deleting rows.

| Field | Type | Notes |
|---|---|---|
| `estimate_id` | id | |
| `study_id`, `report_id` | id | |
| `source_location` | text | **Required.** e.g. `Table 3, row 2, p. 1145` |
| `measure` | enum | `OR`, `RR`, `HR` |
| `estimate` | num | As reported |
| `ci_low`, `ci_high`, `ci_level` | num | As reported. **Named `ci_low`/`ci_high`** to match `scripts/analysis/`; an earlier draft of this document said `ci_lower`/`ci_upper`, and the code's names are now authoritative |
| `se_reported` | num | If the paper gives it |
| `p_value_reported` | text | As reported, including `<0.001` |
| `log_estimate_calc`, `se_calc` | num | Derived; `derivation` states the formula and inputs |
| `derivation` | text | e.g. `SE from 95% CI`, `OR and SE from 2x2 counts` |
| `adjustment` | enum | `crude`, `adjusted` |
| `adjusted_for` | text list | Full covariate list verbatim, or `NA` if crude |
| `adjusted_alcohol` | enum | `yes`, `no`, `NR` — **own field** (rule 9) |
| `adjusted_age`, `adjusted_sex`, `adjusted_ses`, `adjusted_smokeless_tobacco`, `adjusted_betel_quid`, `adjusted_hpv` | enum | `yes`/`no`/`NR` |
| `exposure_definition` | text | Verbatim (rule 8) |
| `exposure_category` | text | Verbatim category label; **never auto-mapped** (rule 9) |
| `exposure_contrast` | enum | `ever`, `current`, `former`, `dose_tier`, `other` ⏳ P004 |
| `product_types` | text list | `cigarette`, `bidi`, `cigar`, `pipe`, `mixed`, `NR` (D009) |
| `intensity_value`, `intensity_unit` | num/text | e.g. cigarettes/day, pack-years, years smoked |
| `comparator_definition` | text | Verbatim (rule 8) |
| `comparator_type` | enum | `never_smoker`, `non_smoker_undefined`, `other` ⏳ P003 |
| `outcome_site` | text | Site this estimate refers to |
| `n_exposed_cases`, `n_exposed_controls`, `n_unexposed_cases`, `n_unexposed_controls` | int | 2×2 where available |
| `verified` | enum | `yes`/`no` — **required `yes` before an estimate enters synthesis** |
| `verified_by`, `verification_notes` | text | |
| `selected_for_analysis` | enum | `yes`/`no`. **At most one per `study_id` per analysis** (D004), enforced by the validator |
| `selection_rationale` | text | **Required when `selected_for_analysis` is `yes`** |
| `notes` | text | |

### Why selection is a separate, recorded step

All reported estimates are preserved (provenance rule 8), so a study contributing several — crude
and adjusted, ever and current, different models — keeps every one. But only one may enter an
analysis, or the study is counted twice (D004).

Choosing which is a **methodological judgement**, not a mechanical filter: it depends on the
adjusted-vs-unadjusted rule, on P003 and P004, and on which model a paper reports. So it is
recorded per estimate with a written rationale rather than applied by code. Nothing is deleted,
and the choice is auditable. The validator refuses an unverified estimate, a selection with no
rationale, and more than one selection per study.

## Table 3 — `risk_of_bias` (one row per `study_id` per domain)

Tool chosen once the included designs are known. Domain names come from the chosen tool and are not
invented here.

| Field | Type | Notes |
|---|---|---|
| `study_id`, `tool`, `tool_version`, `domain` | text | |
| `judgement` | enum | Per the tool's own scale |
| `supporting_evidence` | text | Quote or location from the paper |
| `justification` | text | The reviewer's reasoning |
| `information_missing` | bool | Missing information ≠ high risk |
| `assessed_by` | text | Human reviewer (D010) |

No numeric score is computed unless the chosen tool explicitly supports one (rule: no arbitrary
scoring).

## Validation (built with the extraction stage)

Errors blocking synthesis: `n_cases > n_total`; any count < 0; `ci_lower > ci_upper`; estimate or CI
bound ≤ 0; percentages outside 0–100; duplicate `study_id` in an analysis dataset; duplicate
`estimate_id`; missing `source_location`; an estimate with `verified = no`; a CI that excludes its own
point estimate; `scc_proportion` < 90 with `histology_confirmed` ≠ `all`.

Warnings: implausibly wide CI; estimate asymmetric on the log scale by more than a set tolerance
(possible transcription error); `adjusted` with an empty `adjusted_for`; exposure category text that
differs from every other study's.
