# Intake checklist — accepting an export as research input

How to read an intake report and decide whether to register an export. Steps 1–3 change nothing in
`data/`; step 4 is the authorised act that declares the file to be the project's research input.

To obtain and file a new export in the first place: `docs/methods/obtaining_exports.md`.

## Where the project stands

| Source | Next action |
|---|---|
| `pubmed_v1` | Nothing to do. Its export is missing and is **not** recreated or substituted (D005). It has no file by design, and `verify_raw` refuses it with that explanation. |
| `pubmed_v1r` | **Awaiting your decision.** The intake report is clean. Register it (step 4) to let it become the screening set. |

## Step 1 — Place the file (researcher)

Copy the export, byte for byte, to the `raw_file` path its registry entry names in
`config/sources.yaml`. Copy the file; do **not** open and re-save it in an editor, which can change
the encoding or line endings and so the checksum. `.gitattributes` disables Git's line-ending
conversion for `data/raw/`, so the file stays byte-identical across checkouts.

One file per execution, and filenames are never reused. A file that is not the export its entry
describes needs its **own** entry, not someone else's (D005, D011).

## Step 2 — Read-only inspection (no authorisation needed)

```bash
.venv/Scripts/python -m scripts.acquisition.verify_raw --source pubmed_v1r --report-only
```

Writes `results/validation/<source_id>_intake_proposed.md`. Registers nothing. Never writes
`data/raw/SHA256SUMS`. Exit 0 means no anomalies; exit 1 means anomalies are listed in the report.

### Report fields

| Field | Meaning |
|---|---|
| Path, Size, SHA-256 | The file inspected. The checksum is **proposed** — authoritative only after step 4 |
| Database, Search version | From `config/sources.yaml` |
| Execution type | `historical`, `re_execution` or `new` — which search run this file belongs to |
| Filters applied at retrieval | The filters **actually** used. This is where v1 and v1r differ |
| Strategy document | The search this export came from |
| Execution date | From the registry; blank when not yet recorded |
| Checksum already registered | yes/no |
| Record count — parser / `PMID-` tag scan / reported for this source | Three counts that must agree |
| Provenance of the reported count | Where `expected_records` came from, so a documented claim is never mistaken for a verified figure |
| Anomalies | Count disagreements, duplicate PMIDs, records missing PMID/title/date, encoding or parse failures, checksum mismatch |
| Notes | Byte-order mark, publication-year span, latest Entrez date |

### Reading the anomalies

- **Counts disagree** — the file may not be the export this entry describes. Do **not** register it,
  and do **not** edit the count to match. Decide whether it is a different execution (then it gets
  its own entry) or whether the recorded count was wrong (then correct it with a decision-log entry
  explaining the evidence).
- **Duplicate PMIDs within one export** — abnormal for a PubMed export; investigate first.
- **Records missing PMID, title or date** — these block parsing, which requires those fields.
- **Checksum mismatch** — the raw file changed after registration. Stop and find out why.

### On execution dates

The report gives the latest Entrez date in the file. That is a **lower bound** on when the search
ran, never the date itself, and it is never written into `config/sources.yaml`. The date must come
from the researcher's own record (**P009** for the historical v1 search).

## Step 3 — Approval gate (researcher)

Confirm the path is the file you intended, the three record counts agree, and the anomaly list is
empty. Registration is a separate command precisely so that inspecting a file can never be mistaken
for accepting it.

## Step 4 — Register the checksum (authorised)

```bash
.venv/Scripts/python -m scripts.acquisition.verify_raw --source pubmed_v1r --register
```

Appends `<sha256>  <path>` to `data/raw/SHA256SUMS`. Refuses if the record count disagrees with the
count recorded for that source, or if no count is recorded at all. An existing entry is never
overwritten, and from this point any change to the raw file makes every later stage fail.

Record `search_date` in `config/sources.yaml` at the same time, once you have it.

## Step 5 — Parse, validate, deduplicate

```bash
.venv/Scripts/python -m scripts.acquisition.parse_citations --source pubmed_v1r
.venv/Scripts/python -m scripts.validation.validate_citations --source pubmed_v1r
.venv/Scripts/python -m scripts.dedup.deduplicate
```

Each step re-verifies the registered checksum first and exits non-zero rather than producing partial
output. For `pubmed_v1r` expect a 194-row citation table. Deduplication runs across all registered
sources and stops with a non-zero exit if any similar-title pair needs your decision.

For `pubmed_v1r` validation reports **no errors and no warnings**. Two findings appear as counts in
the report's Summary: **2** records with no English language tag (PMIDs 28763915 and 26733026), and
**42** records without MeSH `Humans`. The report deliberately claims nothing about why the MeSH term
is absent: the MEDLINE indexing-status field is not part of the citation dataset, so **species
eligibility is unknown from these records** and is assessed at screening. Per **D013** both groups
are resolved at screening with a recorded reason code, not filtered out silently.

The report derives these from `filters_applied` in the registry, so it never claims a filter was
used that was not. Had this source claimed an English or Humans filter, those same records would be
**errors**: a record a claimed filter would have removed means either the filter was not applied or
the file is not the export the entry describes.

The real-data test in `tests/test_raw_sources.py` stops being skipped once a checksum is registered;
re-run `pytest` to confirm.

## What this does not do

Screening does not follow automatically. It needs **P003** (whether an undefined "non-smoker"
reference satisfies the eligibility criteria) and **P006** (registration before screening begins);
**P004** constrains extraction and reaches screening only through the `no_usable_data` boundary.
Screening is the researcher's work in any case: the pipeline records decisions, it does not make
them (D010).
