# PRISMA 2020 flow — template

**Status: TEMPLATE. No count below has been determined.** Every `<pending>` is filled by
`scripts/` from the underlying datasets, never typed by hand (provenance rule 16). A count that
cannot be generated from a dataset stays `<pending>` and the reason is stated.

## Identification

| Item | Count | Source dataset |
|---|---|---|
| Records identified — PubMed, search v1 | `<pending>` | `data/processed/citations/pubmed_v1_citations.csv` |
| Records identified — other databases | `<pending>` | per `config/sources.yaml`; none yet (P007) |
| Records identified — other methods (reference lists, citation searching) | `<pending>` | P007 |
| Records removed before screening — duplicates | `<pending>` | dedup audit (Stage 2) |
| Records removed before screening — other reasons | `<pending>` | stated explicitly if any |

## Screening

| Item | Count | Source dataset |
|---|---|---|
| Records screened (title/abstract) | `<pending>` | screening dataset |
| Records excluded | `<pending>` | screening dataset |
| Reports sought for retrieval | `<pending>` | full-text tracking |
| Reports not retrieved | `<pending>` | full-text tracking (`full_text_unavailable`) |
| Reports assessed for eligibility | `<pending>` | screening dataset |

## Full-text exclusions, by reason

One row per controlled reason code from `docs/protocol/eligibility_criteria.md`. The codes are fixed;
counts are generated. Every excluded full text has exactly one code — none may be uncounted.

| Reason code | Count |
|---|---|
| `wrong_outcome` | `<pending>` |
| `outcome_not_separable` | `<pending>` |
| `wrong_exposure` | `<pending>` |
| `no_reference_group` | `<pending>` |
| `wrong_design` | `<pending>` |
| `wrong_population` | `<pending>` |
| `review_or_meta` | `<pending>` |
| `animal_or_invitro` | `<pending>` |
| `no_usable_data` | `<pending>` |
| `duplicate_publication` | `<pending>` |
| `conference_abstract` | `<pending>` |
| `not_english` | `<pending>` |
| `other` | `<pending>` |

## Included

| Item | Count | Source dataset |
|---|---|---|
| Reports of included studies (`report_id`) | `<pending>` | extraction dataset |
| **Studies included in the review (`study_id`)** | `<pending>` | extraction dataset |
| Studies included in quantitative synthesis | `<pending>` | analysis dataset |

`report_id` and `study_id` counts differ whenever several publications report the same population
(D004). The difference is stated in the Results, not hidden.

## Consistency checks (automated, Stage 8)

- identified − duplicates = screened
- screened − excluded = sought for retrieval
- sought − not retrieved = assessed
- assessed − (sum of all reason codes) = included reports
- included reports ≥ included studies ≥ studies in synthesis
- no `study_id` appears more than once in an analysis dataset

Any check that fails blocks figure generation.
