# Association Between Tobacco Smoking and Oral Squamous Cell Carcinoma: A Systematic Review and Meta-analysis

## Overview

This repository documents a systematic review and meta-analysis investigating the association between smoked tobacco use and the risk of squamous cell carcinoma of the oral cavity.

The project is being built to meet the reporting expectations of PRISMA 2020, PRISMA-S and MOOSE. It does not yet claim compliance with them: compliance is asserted only once the workflow and reporting actually support it (see **Current Status**).

---

## Research Question

**Is smoked tobacco use associated with an increased risk of squamous cell carcinoma of the oral cavity?**

Scope, as settled in [`docs/protocol/eligibility_criteria.md`](docs/protocol/eligibility_criteria.md):

- **Exposure** — any smoked tobacco (cigarettes, bidis, cigars, pipes). Smokeless tobacco and betel quid are treated as confounders, not exposures (decision D009).
- **Outcome** — oral cavity cancer with squamous histology confirmed, or a stated ≥90% SCC majority. Estimates that pool the oral cavity with the oropharynx, larynx or "head and neck" are not eligible unless an oral-cavity-specific estimate is reported (decision D008).
- Associations only. No causal claim is made from observational evidence.

---

## Objectives

### Primary Objective

- Evaluate the association between tobacco smoking and Oral Squamous Cell Carcinoma.

### Secondary Objectives

- Compare findings across different populations.
- Assess study quality.
- Estimate the pooled effect size using meta-analysis.
- Evaluate heterogeneity and publication bias.

---

## Study Design

- Systematic Review
- Meta-analysis
- Observational Studies (Case-Control and Cohort Studies)

---

## Workflow

- [x] Evidence-provenance rules ([`docs/protocol/provenance_rules.md`](docs/protocol/provenance_rules.md))
- [~] Research protocol — eligibility criteria settled except the comparator and primary contrast (P003, P004)
- [x] Search strategy v1 documented and preserved ([`docs/search/search_v1_pubmed.md`](docs/search/search_v1_pubmed.md))
- [~] Literature search — v1 executed (138 records); the export is awaiting restoration, and a v2 strategy is proposed but not drafted
- [x] Acquisition pipeline built and tested (parser, intake gate, validation)
- [x] Deduplication built and tested (identifier and fingerprint matching; similar titles flagged for review, never merged)
- [ ] Title/abstract screening
- [ ] Full-text retrieval and screening
- [ ] Data extraction ([schema specified](docs/data_dictionary/extraction_schema.md))
- [ ] Risk of bias assessment
- [ ] Statistical analysis plan ([skeleton](docs/methods/statistical_analysis_plan.md))
- [ ] Meta-analysis, forest plot, funnel plot, sensitivity analyses
- [ ] Manuscript

`[~]` means partially complete. No stage past acquisition has been run on real data.

---

## Repository Structure

```
oscc-smoking-meta-analysis/
├── data/
│   ├── raw/            # original database exports — read-only, checksummed
│   ├── processed/      # script-generated datasets (citations, dedup, screening)
│   └── extraction/     # study-level extraction data
├── docs/
│   ├── protocol/       # provenance rules, eligibility criteria
│   ├── search/         # versioned, database-specific search strategies
│   ├── methods/        # pipeline, dependencies, SAP, PRISMA flow template
│   ├── data_dictionary/# field definitions for every dataset
│   └── decisions/      # methodological decision log
├── scripts/
│   ├── common/         # paths, source registry
│   ├── acquisition/    # NBIB parsing, intake and checksum gate
│   ├── dedup/          # duplicate matching and report_id assignment
│   └── validation/     # dataset validation reports
├── tests/
├── results/validation/ # generated reports
├── config/sources.yaml # one entry per database × search version
├── CLAUDE.md           # working conventions and standing prohibitions
└── README.md
```

Folders are added as each pipeline stage is built. Nothing in `results/` is edited by hand.

---

## Reproducing the pipeline

Rules governing all data handling: [`docs/protocol/provenance_rules.md`](docs/protocol/provenance_rules.md).

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows; use .venv/bin/python elsewhere
.venv/Scripts/python -m pytest
```

Stage 1 — citation acquisition, per source in `config/sources.yaml`. Inspecting a file and declaring
it the research input are deliberately separate steps:

```bash
# 1. read-only inspection: path, size, SHA-256, record count, anomalies. Registers nothing.
.venv/Scripts/python -m scripts.acquisition.verify_raw --source pubmed_v1r --report-only

# 2. after the reviewer confirms the file is the original export, record its checksum (one-off)
.venv/Scripts/python -m scripts.acquisition.verify_raw --source pubmed_v1r --register

# 3. parse to a citation dataset, validate it, then deduplicate across sources
.venv/Scripts/python -m scripts.acquisition.parse_citations --source pubmed_v1r
.venv/Scripts/python -m scripts.validation.validate_citations --source pubmed_v1r
.venv/Scripts/python -m scripts.dedup.deduplicate
```

Step-by-step walkthrough for receiving the export, including every report field and the approval
gate: [`docs/methods/intake_checklist.md`](docs/methods/intake_checklist.md).
Stage details, inputs, outputs and exit codes: [`docs/methods/pipeline.md`](docs/methods/pipeline.md).
Each step exits with an error rather than continuing on missing, altered or invalid input.

---

## Software

In use: PubMed (searching), Python 3.14 with `pyyaml` and `pytest` (pipeline), Git and GitHub.

Planned, not yet installed or adopted: R with `metafor` for the synthesis (pending decision P008),
`matplotlib` for figures. Reference-manager and screening tools (e.g. Zotero, Rayyan) may be used by
the reviewer, but no stage of this pipeline depends on them.

Full list with rationale: [`docs/methods/dependencies.md`](docs/methods/dependencies.md).

---

## Current Status

**Phase 1 — infrastructure and protocol.** Acquisition and deduplication have run on the `pubmed_v1r`
export. Screening, extraction, risk-of-bias assessment and synthesis have not begun, so this
repository contains no effect estimate and the review does not yet satisfy PRISMA 2020.

Complete:
- Evidence-provenance rules, decision log (D001–D014), eligibility criteria except P003/P004
- Search v1 preserved verbatim with a documented sensitivity appraisal; its export is lost and recorded as missing, not recreated
- Search v1r (the v1 query re-run unfiltered, 194 records) documented as its own execution, with the 138-vs-194 difference analysed against independently measured counts
- Search v2 drafted and syntax-validated against PubMed, **not executed**
- Acquisition pipeline: NBIB parser, read-only intake inspection, checksum gate, citation dataset, validation report
- Deduplication: deterministic identifier and fingerprint matching, full pair-level audit, `report_id` assignment
- `pubmed_v1r` accepted as research input: its SHA-256 is recorded in the project's provenance record (`data/raw/SHA256SUMS`), and it has been parsed (194 citation records), validated (0 errors, 0 warnings) and deduplicated (194 unique reports, 0 duplicates, 0 pairs needing review). **This is checksum registration within this repository only — it is not external protocol registration such as PROSPERO or OSF, which remains open as P006.**
- Test suite of 123 tests — 122 pass, 1 skips while the historical v1 export is absent — covering format parsing, intake anomalies, the checksum registration gate, source-registry invariants, search-filter cross-checks, record-count conservation, raw-to-derived provenance, and duplicate matching

Awaiting the researcher:
- **External protocol registration (P006)** has not been done: there is no PROSPERO or OSF record, and no registration identifier. This is independent of the checksum registration above.
- The original 138-record v1 export is lost and will not be recreated or substituted (decision D005). Its search date is unrecorded (P009) and cannot be derived.
- Open decisions P003, P004, P006–P010, P012, P013 — see [`docs/decisions/decision_log.md`](docs/decisions/decision_log.md). P013 is the notable one: v2 retrieves 4,770 records against v1r's 194, which is a feasibility problem for single-reviewer screening.

Screening needs **P003** and **P006** settled first; **P004** constrains extraction rather than eligibility.

---

## Author

**Soppa Shiva Sai Koushik**

B.Tech Biotechnology  
National Institute of Technology Rourkela

---

## License

License will be added before public release of the completed project.
