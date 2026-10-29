# Evidence-provenance rules

These rules govern every stage of the review. Code enforces them where possible; the rest are checked at the quality-control audit. A rule changes only through a decision-log entry.

## 1. Sources and searches
1. The original PubMed search is **Search v1** and is never discarded or overwritten.
2. If the original v1 export cannot be recovered, it is **not** recreated. Any new retrieval, even with an identical query, is a new search version with its own date, record count and file.
3. Raw exports in `data/raw/` are immutable. Their SHA-256 is recorded once in `data/raw/SHA256SUMS` (append-only), and every stage re-verifies it before reading. Git line-ending conversion is disabled for raw files (`.gitattributes`).
4. A checksum registered at import proves the file is unchanged **from import onward**. It does not prove the file is the original download. Evidence that it is the original is recorded separately (record count against the count reported at search time, and file origin).

## 2. No fabrication
5. Bibliographic, extraction and statistical data are never fabricated, inferred or filled in. Missing values stay missing and are flagged.
6. No placeholder data, synthetic study results or invented citations exist anywhere in the repository. Tests use format fragments or structural stubs that carry no bibliographic content and cannot enter the pipeline.
7. Suspicious values are flagged, never silently repaired.

## 3. Identifier model (reports vs. studies)

| Identifier | Unit | Assigned at | Relation |
|---|---|---|---|
| `record_id` | one record in one database export (`<source_id>:<native id>`) | Stage 1 (parsing) | many records → one report |
| `report_id` | one unique publication | Stage 2 (deduplication) | many reports → one study |
| `study_id` | one underlying study population or cohort | full-text stage (human judgement) | unit of analysis |
| `estimate_id` | one reported effect estimate | extraction | many estimates → one study |

Multiple reports of the same population are linked to one `study_id` and are **never** treated as independent. The analysis dataset must contain each `study_id` at most once per analysis. The pipeline fails otherwise.

## 4. Traceability required for every included study
PMID; DOI where available; first author; publication year; source database and search version; `report_id`; `study_id`; the full-text source (where and how the text was obtained); and, for every extracted number, its **exact location** (page, table or figure) whenever possible.

## 5. Effect estimates
8. All reported estimates are preserved. Each one records: measure (OR/RR/HR), adjusted vs. unadjusted (crude vs. multivariable), exposure definition as reported, comparator definition as reported, and the full list of adjustment variables.
9. **Alcohol adjustment** is extracted explicitly for every estimate (yes/no/not reported), as its own field.
10. Incompatible exposure categories are never automatically mapped to a common category. Any harmonisation is a documented decision.
11. Different measures are not combined without a documented justification.

## 6. Outcome eligibility
12. Oral cavity, oropharyngeal, head-and-neck and other cancer outcomes are not combined merely because they mention smoking. Each outcome is confirmed against the protocol's outcome definition. Mixed-site estimates are eligible only as the protocol specifies.

## 7. Analysis gate
13. No pooled analysis is run until all of the following hold: eligibility criteria finalised; search documented; deduplication complete; screening complete; included studies identified; extraction complete; risk of bias assessed; and a statistical analysis plan (SAP) documented.
14. The SAP specifies before any pooling: primary effect measure, model, heterogeneity statistics, handling of adjusted estimates, subgroup analyses, sensitivity analyses, publication-bias assessment, and criteria for when pooling is inappropriate.
15. Methods are chosen from the study designs and data, never for a more favourable result. Deviations from the SAP are reported as post-hoc.

## 8. Automated validation (fail loudly)
The pipeline exits with an error on: duplicate PMIDs; duplicate DOIs; missing required fields; invalid confidence intervals; impossible event counts; inconsistent sample sizes; and duplicate unique studies in an analysis dataset. Each stage writes a validation report to `results/validation/`.

## 9. Outputs and separation
16. Tables and figures are generated from the analysis dataset by code. They are never typed by hand.
17. Raw data (`data/raw/`), processed data (`data/processed/`), extraction/analysis data (`data/extraction/`), code (`scripts/`), outputs (`results/`) and documentation (`docs/`) are kept separate.
18. Every material methodological decision is recorded in `docs/decisions/decision_log.md`.

## 10. Interpretation
19. Observational associations are not described as proving causality.
