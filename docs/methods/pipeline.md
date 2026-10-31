# Pipeline — stages, inputs, outputs, exit codes

Every stage is a module run from the repository root with `-m`. Stages fail loudly: a non-zero exit
means the stage refused to produce output, never that it produced partial output.

Legend: ✅ built and tested · ⏳ not built

Operational walkthrough for receiving the export: [`intake_checklist.md`](intake_checklist.md).

## Stage 1 — Acquisition ✅

### 1a. Intake inspection (read-only)

```
.venv/Scripts/python -m scripts.acquisition.verify_raw --source pubmed_v1r --report-only
```

| | |
|---|---|
| Input | the raw export named in `config/sources.yaml` |
| Output | `results/validation/<source_id>_intake_proposed.md` |
| Writes to `data/` | **never** |
| Exit 0 | file readable, record count agrees three ways, no anomalies |
| Exit 1 | file missing, unreadable, or any anomaly — nothing is registered either way |

Reports path, size, SHA-256, record count by two independent methods, duplicate PMIDs, records
missing PMID/title/date, and the latest Entrez date (a *lower bound* on the search date, not the
search date). This is the first thing to run on a newly supplied file.

### 1b. Registration (authorised act)

```
.venv/Scripts/python -m scripts.acquisition.verify_raw --source pubmed_v1r --register
```

Appends `<sha256>  <path>` to `data/raw/SHA256SUMS`. Refuses if the record count disagrees with the
count the database reported. An existing entry is never overwritten. Run only after the reviewer has
confirmed the intake report.

### 1c. Verification gate (every later stage calls this first)

```
.venv/Scripts/python -m scripts.acquisition.verify_raw --source pubmed_v1r
```

Exit 1 if the file is missing, the count is wrong, the checksum is unregistered, or the checksum no
longer matches.

### 1d. Parsing

```
.venv/Scripts/python -m scripts.acquisition.parse_citations --source pubmed_v1r
```

| | |
|---|---|
| Input | verified raw export |
| Output | `data/processed/citations/<source_id>_citations.csv` (fields: `docs/data_dictionary/citations.md`)<br>`data/processed/citations/<source_id>_records.jsonl` (every raw tag, in order, with the raw line number and the file's SHA-256) |
| Exit 1 | verification fails, or the record count is not conserved raw → parsed → CSV → JSONL |

Values are copied as reported. Empty means not reported.

### 1e. Validation

```
.venv/Scripts/python -m scripts.validation.validate_citations --source pubmed_v1r
```

| | |
|---|---|
| Output | `results/validation/<source_id>_citations_validation.md` |
| Exit 1 (errors) | count mismatch; missing `record_id`/`source_id`/`pmid`/`title`/`pub_year`; non-numeric PMID or year; duplicate PMID, DOI or `record_id` |
| Exit 1 (errors), cont. | a record that contradicts a filter `config/sources.yaml` records as applied at retrieval — e.g. a non-English record in a source claiming an English filter, or a record without MeSH `Humans` in one claiming a Humans filter. Either the filter was not used or the file is not the export the entry describes |
| Exit 0 with warnings | malformed DOI, multiple DOIs, implausible year, a filter cross-check that cannot be applied (no record carries MeSH), records not matching the documented query terms (diagnostic only — never used to exclude) |
| Summary counts | records a filter would have removed had one been claimed: no English language tag, no MeSH `Humans`. Reported as counts, since under D013 they are resolved at screening |

Filter cross-checks read `filters_applied` and never assume a filter was used: asserting one in a
report without evidence is itself a provenance error. **Limitation:** PubMed's Humans filter matches
the MeSH term `Humans`, which unindexed records lack, so if *no* record in an export carries MeSH the
check is skipped with a warning — an all-unindexed export and an export that omitted MeSH cannot be
told apart from the records alone.

## Stage 2 — Deduplication ✅ (built; never run on real data)

```
.venv/Scripts/python -m scripts.dedup.deduplicate                 # all parsed sources
.venv/Scripts/python -m scripts.dedup.deduplicate --source pubmed_v1r
```

| | |
|---|---|
| Input | `data/processed/citations/<source_id>_citations.csv` for each source |
| Output | `data/processed/dedup/report_index.csv` — every input record with its `report_id`, primary flag, `duplicate_of` and merge criterion<br>`data/processed/dedup/dedup_audit.csv` — every candidate pair with criterion, matched value and resolution<br>`results/validation/dedup_summary.md` — counts before and after, for the PRISMA flow |
| Exit 1 | a citation table is missing or empty; an unknown `source_id`; record count not conserved; **or any pair still needs the reviewer's decision** |

Matching is deterministic, applied in order of decreasing authority:

1. **Shared DOI** — normalised (lowercased, `https://doi.org/` and `doi:` prefixes stripped, trailing punctuation removed) → merged
2. **Shared PMID** → merged
3. **Exact normalised fingerprint** of title + first-author surname + year → merged, and flagged in the audit as having no shared identifier
4. **Similar title in the same year** (sequence similarity ≥ 0.92) → **`needs_review`, not merged**

Empty keys never match, links are transitive, and normalised values are used only for matching —
they never overwrite what the database reported.

Level 4 exists because a near-identical title may be a conference abstract, an erratum, a reanalysis
or a different paper. The stage exits non-zero while any such pair is unresolved, because a PRISMA
identification count cannot be stated while duplicate status is undecided (D010: the pipeline records
decisions, it does not make them). Records are mapped to a `report_id`, never deleted.

A `report_id` is a unique *publication*. The unique *study* (`study_id`) is established later, at full
text, by the reviewer — several reports of one cohort collapse to one `study_id` (D004).

## Stage 3 — Screening ✅ infrastructure built · ⏳ **no record screened yet**

```
.venv/Scripts/python -m scripts.screening.worksheet --stage ta            # create (refuses to overwrite)
.venv/Scripts/python -m scripts.screening.worksheet --stage ta --refresh  # add new records, keep decisions
.venv/Scripts/python -m scripts.screening.validate_screening --stage ta
.venv/Scripts/python -m scripts.screening.prisma
```

| | |
|---|---|
| Input | `data/processed/dedup/report_index.csv` (one row per unique report); raw checksum and raw-to-derived provenance verified first |
| Output | `data/screening/screening_{ta,ft}.csv` — **tracked in Git**, unlike `data/processed/`, because decisions cannot be regenerated<br>`results/validation/screening_{ta,ft}_validation.md`<br>`results/validation/prisma_counts.md` |
| Exit 1 | any validation error; an unreconcilable PRISMA flow; an attempt to overwrite an existing worksheet |

The generator writes **every decision column empty**. It produces no suggestion, pre-sort or
automated classification of any kind; decisions are the human reviewer's (D010). Exclusion reasons
are restricted to the stage at which they can honestly be judged, so reasons needing the methods
section are unavailable at title/abstract and the reviewer records `unresolved` instead.

Full guide, including the spreadsheet caveat and the unresolved protocol decisions this module does
**not** settle: [`screening.md`](screening.md).

Blocked on **P003** — whether an undefined "non-smoker" reference group satisfies inclusion
criterion 4, which sets the boundary of the `no_reference_group` code — and **P006**, registration
before screening begins. **P004** constrains extraction, not eligibility; it reaches screening only
through the `no_usable_data` boundary, for a study reporting no contrast the protocol uses.

## Stage 4 — Full-text retrieval ⏳

Tracks retrieval status and source per `report_id`. PDFs are gitignored; only status is tracked.

## Stage 5 — Extraction ✅ infrastructure built · ⏳ **nothing extracted yet**

```
.venv/Scripts/python -m scripts.extraction.template              # create (refuses to overwrite)
.venv/Scripts/python -m scripts.extraction.template --refresh    # add new studies, keep values
.venv/Scripts/python -m scripts.extraction.validate_extraction
```

| | |
|---|---|
| Input | full-text includes from `data/screening/screening_ft.csv` |
| Output | `data/extraction/{studies,estimates}.csv` — **tracked in Git**, since extracted values cannot be regenerated<br>`results/validation/extraction_validation.md` |
| Exit 1 | no full-text includes exist; any validation error; an attempt to overwrite an existing table |

Reported and calculated values are kept in separate fields; `source_location` is required for every
estimate; alcohol adjustment is its own field (D009); exposure categories are recorded verbatim and
never harmonised (rule 9). All reported estimates are preserved, and the **one** that enters an
analysis is marked with a written rationale (D004) rather than chosen by code.

`comparator_type` (**P003**) and `exposure_contrast` (**P004**) are marked unresolved: a value is
recorded and reported as pending, and an unexpected one warns rather than errors.

Full guide: [`extraction.md`](extraction.md). Blocked on P003 and P014–P022 for eligibility.

## Stage 6 — Risk of bias ⏳

Tool selected once the included designs are known. Domain-level judgements with supporting evidence.
Missing information recorded as missing, never as high risk.

## Stage 7 — Synthesis ⏳

Gated on provenance rule 13 and an approved SAP (`docs/methods/` — template pending). Blocked on P008.

## Stage 8 — Reporting ⏳ partly built

```
.venv/Scripts/python -m scripts.visualization.prisma_diagram
```

| | |
|---|---|
| Input | the counts from `scripts.screening.prisma.gather()` — the same source as `results/validation/prisma_counts.md`, so the figure and the table cannot disagree |
| Output | `results/figures/prisma_flow.png` |
| Exit 1 | **the flow does not reconcile** — no diagram is drawn, because a flow diagram asserts that its numbers add up |

A stage that has not run shows **`n = pending`**, never `n = 0`, and a partially screened stage
shows both numbers (`n = 50 of 194`). The figure carries the same screening-status banner as the
counts table, so an unscreened flow cannot be mistaken for a null finding.

Still to build: characteristics table, risk-of-bias summary. Forest and funnel plots exist in
`scripts/analysis/plots.py` but have no real data to draw.
