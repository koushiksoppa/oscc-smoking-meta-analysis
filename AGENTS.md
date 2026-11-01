# Working conventions for this repository

This is a live systematic review and meta-analysis, not a demonstration project. Its outputs are
intended to support an academic manuscript. Read `docs/protocol/provenance_rules.md` before touching
anything; this file is the short operational summary.

## Standing prohibitions

1. **Never fabricate.** No invented citations, study characteristics, effect estimates, screening
   decisions, risk-of-bias judgements, statistics or search dates. Missing stays missing and is flagged.
2. **No synthetic data in `data/`.** Tests use MEDLINE format fragments and structural stubs with no
   bibliographic content, in pytest temp directories only (D007; see open question P010).
3. **`data/raw/` is immutable.** Never edit, re-save, re-encode or recreate a raw export. The v1
   export is lost; it is **not** recreated or substituted. Any new retrieval is a separate execution
   with its own registry entry, date, count and checksum (D005, D011). Filenames are never reused.
   Never edit a recorded count to make validation pass — a disagreement is the finding.
4. **No commits, pushes or installs without explicit authorisation.** Git identity is currently unset.
   Never rewrite history or force-push. `main` is the working branch.
5. **No pooled analysis before the gate** in provenance rule 13 is met and the SAP is approved.
6. **Automated tooling is not a reviewer.** Screening and risk-of-bias decisions belong to the human
   reviewer (D010). Automated output goes in a `suggestion` field, never a `decision` field.
7. **No causal language** from observational associations.
8. Material methodological decisions are escalated to the reviewer, not made silently, and are
   recorded in `docs/decisions/decision_log.md`.

## Layout

```
data/raw/        immutable exports + SHA256SUMS (append-only)
data/processed/  script-generated datasets
data/extraction/ study-level extraction data
docs/            protocol, search versions, decisions, methods, data dictionary
scripts/         common | acquisition | validation | dedup | screening | extraction | analysis
data/screening/  screening worksheets — TRACKED, not regenerable, unlike data/processed/
data/extraction/ extraction tables   — TRACKED, same reason
results/         validation reports, tables, figures — generated, never hand-edited
tests/
config/sources.yaml   one entry per database x search EXECUTION (D011)
```

A registry entry carries `execution` (historical / re_execution / new), `status`
(export_missing / awaiting_registration / registered), the `filters_applied` actually used, and
`count_source` for `expected_records`. An entry exists only when an export exists, or to record that
one is missing — never for a merely drafted search.

## Pipeline

```
raw export -> verify_raw (count + checksum gate) -> parse_citations -> validate_citations
           -> deduplicate -> screening -> extraction -> [risk of bias] -> synthesis -> [reporting]
```

Stages in brackets are not built. Every other stage is built and tested. Acquisition, validation,
deduplication and **title/abstract screening** have been run on real data; **full-text retrieval,
extraction, appraisal and synthesis have not**, so no study is yet judged eligible and no pooled
estimate exists. Screening, extraction, appraisal and the judgements behind them are the human
reviewer's (D010) and cannot be generated.

Each stage re-verifies provenance before reading, writes a report to `results/validation/`, and
exits non-zero on missing, altered or invalid input. Three gates refuse in sequence: extraction
needs full-text includes, synthesis needs extracted estimates, and the analysis CLI rejects
anything marked synthetic.

Stage details: `docs/methods/pipeline.md`. Guides: `intake_checklist.md`, `screening.md`,
`extraction.md`, `analysis_validation.md`.

## Conventions

- Python 3.14 in `.venv`; stdlib only so far (`csv`, `json`, `hashlib`) plus `pyyaml` and `pytest`.
  Dependencies are added per stage and pinned in `requirements.txt`.
- Run modules with `-m` from the repository root: `.venv/Scripts/python -m scripts.acquisition.verify_raw --source pubmed_v1r`.
- Errors that violate a provenance rule raise `PipelineError` and are never caught silently.
- Identifiers: `record_id` → `report_id` → `study_id` → `estimate_id` (D004). The unit of analysis is
  `study_id`; a `study_id` may appear at most once per analysis.
- Inspecting a file and declaring it the research input are separate acts: `--report-only` writes a
  proposal, `--register` writes the authoritative checksum.

## Current state

`pubmed_v1r` (194 records, the v1 query re-run unfiltered) is registered, parsed, validated and
deduplicated. `pubmed_v1`, the original 138-record execution, is lost and recorded as
`export_missing`.

**Title/abstract screening is complete**: 194 of 194 reports screened, 109 excluded with a reason,
85 taken forward, 0 unresolved. The full-text worksheet exists with those 85 rows and **every
reviewer field empty** — nothing has been retrieved or assessed. A decision-log entry describing
how the title/abstract pass was conducted is still outstanding and is needed for PRISMA item 8.

Decisions D001–D015 are settled. Open: P003 (comparator), P004 (contrast), P006 (PROSPERO),
P007 (other databases), P009 (historical v1 search date), P010 (fixture policy), P012 (~9-record
residual in the 138 reconciliation), P013 (v2 retrieves 4,770 records — feasibility under
single-reviewer screening), P014–P022 (anatomical and histological scope). Search v2 is drafted and
syntax-validated but **not executed**. The stage assignment of exclusion reasons in
`config/screening.yaml` is still a proposal awaiting endorsement, and no identifier yet covers
whether populations restricted to premalignant oral lesions are in scope.
