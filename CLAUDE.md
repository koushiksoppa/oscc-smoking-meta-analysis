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
6. **An AI assistant is not a reviewer.** Screening and risk-of-bias decisions belong to the human
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
scripts/         common | acquisition | validation | dedup | screening | (later: extraction, analysis)
data/screening/  screening worksheets — TRACKED, not regenerable, unlike data/processed/
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
           -> deduplicate -> screening -> [extraction] -> [risk of bias] -> [synthesis] -> [reporting]
```

Stages in brackets are not built. Each stage re-verifies the raw checksum before reading, writes a
report to `results/validation/`, and exits non-zero on missing, altered or invalid input.
Stage details: `docs/methods/pipeline.md`. Receiving the export: `docs/methods/intake_checklist.md`.

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

Stages 1 and 2 are built and tested. No stage has yet run on real data: `pubmed_v1r` (194 records,
the v1 query re-run unfiltered) is on disk with a clean intake report but is **not registered** —
that is the researcher's call. `pubmed_v1`, the original 138-record execution, is lost and recorded
as `export_missing`.

Decisions D001–D013 are settled. Open: P003 (comparator), P004 (contrast), P006 (PROSPERO),
P007 (other databases), P008 (R/metafor), P009 (historical v1 search date), P010 (fixture policy),
P012 (~9-record residual in the 138 reconciliation), P013 (v2 retrieves 4,770 records — feasibility
under single-reviewer screening). Search v2 is drafted and syntax-validated but **not executed**.

Nothing is committed yet and Git has no user identity configured.
