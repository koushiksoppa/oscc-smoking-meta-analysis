# Eligibility criteria

Status: **partially settled.** Sections marked ⏳ depend on decisions still open in
`docs/decisions/decision_log.md` and must be resolved before screening begins.
Every criterion below traces to a decision-log entry; nothing here was chosen by the pipeline.

## Review question

Is smoked tobacco use associated with an increased risk of squamous cell carcinoma of the oral cavity?

The question is stated as **smoked tobacco**, not cigarettes alone, following D009. Any association
found is an association; the review does not claim causation (provenance rule 19).

## PICO

| Element | Criterion | Source |
|---|---|---|
| **Population** | Human adults. No restriction by country, sex or setting. | Original PICO |
| **Exposure** | Any smoked tobacco: cigarettes, bidis, cigars, pipes, other combusted tobacco. Product type recorded per estimate. | D009 |
| **Comparator** | ⏳ Never-smokers, and/or "non-smokers" as defined by the study. Recorded verbatim in all cases. | P003 |
| **Outcome** | Oral cavity cancer with SCC histologically confirmed, or SCC a stated ≥90% majority. | D008 |
| **Contrast** | ⏳ Primary contrast (ever/current/former vs reference) not yet fixed. | P004 |

## Inclusion criteria

1. Observational design: case–control or cohort (prospective or retrospective).
2. Reports an OR, RR or HR with a 95% CI, **or** sufficient raw data to calculate one.
3. Outcome meets the D008 definition, with an oral-cavity-specific estimate.
4. Exposure meets the D009 definition, with a defined reference group.
5. Human participants.
6. Published in English.

## Exclusion criteria and controlled reasons

The screening vocabulary below is fixed; no free-text reason may replace it.

| Code | Reason | Notes |
|---|---|---|
| `wrong_population` | Not human, not adult, or not a relevant population | |
| `wrong_outcome` | Outcome is not oral-cavity SCC per D008 | Includes **prognostic** studies of survival or recurrence among people who already have OSCC, which search v1 retrieves in quantity because of the term "cohort" |
| `outcome_not_separable` | Oral cavity pooled with oropharynx / larynx / head and neck, no oral-cavity-specific estimate | D008; kept distinct from `wrong_outcome` so the PRISMA flow shows how much evidence is lost this way |
| `wrong_exposure` | Exposure is not smoked tobacco, or smokeless tobacco / betel quid only | D009 |
| `no_reference_group` | No non-smoking or never-smoking comparator | |
| `wrong_design` | Not case–control or cohort | |
| `review_or_meta` | Systematic review, meta-analysis, narrative review | |
| `animal_or_invitro` | Animal, cell or in-vitro study | |
| `no_usable_data` | No effect estimate and no data from which to derive one | |
| `duplicate_publication` | Same study population already included | Links to the retained `report_id` (D004) |
| `conference_abstract` | Abstract with insufficient detail for reliable extraction | |
| `not_english` | Not published in English | |
| `full_text_unavailable` | Full text could not be retrieved | Recorded as *not retrieved* in the PRISMA flow, not as an exclusion |
| `other` | Requires a written justification | |

## Screening process

Single reviewer (D010). Every record carries a reviewer identity, a decision, and — for exclusions at
full text — exactly one reason code. Records needing judgement stay `unresolved` rather than being
forced to a decision. Automated suggestions, if any are ever produced, occupy a separate `suggestion`
field and never satisfy `decision`.

## Notes on what the criteria imply for the search

D008 and D009 make the v1 search blocks demonstrably narrow: the outcome block omits "oral cancer",
"oral cavity", "mouth neoplasms" and the MeSH terms, and the exposure block omits "tobacco" and
inflected forms. This is the basis for a proposed search v2
(`docs/search/search_v1_pubmed.md`, appraisal section). **Drafting v2 awaits authorisation and P007.**
