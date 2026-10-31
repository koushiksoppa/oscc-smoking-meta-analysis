# Screening — how to run it

## What this module is, and what it is not

**It is infrastructure for recording screening. It is not screening.**

The module generates a worksheet from the deduplicated reports, checks that whatever the reviewer
records is internally consistent and complete, and computes the PRISMA flow from what has actually
been decided. It produces **no decisions of any kind** — no suggestion, pre-sort, ranking or
automated classification. Every decision is the human reviewer's (D010), and an automated
suggestion could not satisfy a `decision` field even if one existed.

So "the screening module works" and "the screening is done" are different claims. The current
state of the second is in `results/validation/prisma_counts.md`, which states it in a banner at the
top of the file.

## Where the files live, and why

| Path | Tracked in Git? | Why |
|---|---|---|
| `data/screening/screening_ta.csv` | **yes** | Screening decisions are human research work and cannot be regenerated from anything. They must be version-controlled |
| `data/screening/screening_ft.csv` | **yes** | same |
| `data/processed/**` | no — gitignored | Regenerable from the raw export by re-running the pipeline |

This is why the worksheets are **not** under `data/processed/`: that directory is ignored as
regenerable, and putting irreplaceable decisions there would mean losing them on any fresh clone.

## 1. Generate the worksheet

```bash
.venv/Scripts/python -m scripts.screening.worksheet --stage ta
```

One row per **unique report** (`report_id`), taken from `data/processed/dedup/report_index.csv`,
so duplicates are already collapsed. The raw export's checksum and the raw-to-derived consistency
of the parsed data are verified first; if either fails, no worksheet is written.

Running it again **refuses to overwrite**, because the file may hold your decisions. To pick up
records added by a later search:

```bash
.venv/Scripts/python -m scripts.screening.worksheet --stage ta --refresh
```

`--refresh` merges on `report_id`: every recorded decision is carried across, and only genuinely
new reports are added. If a report that holds a decision has disappeared from the source set, the
command **fails** rather than dropping it — that would discard your work silently.

## 2. Record decisions

Edit only these columns: **`decision`, `reason_code`, `reviewer`, `screened_date`, `notes`**.
Everything else is derived and is checked against the source data; an edit there is reported as an
error, because it usually means a spreadsheet re-import has damaged the file.

| Column | Values |
|---|---|
| `decision` | `include` · `exclude` · `unresolved` · empty (not yet screened) |
| `reason_code` | required for `exclude`, forbidden otherwise; from `config/screening.yaml` |
| `reviewer` | required whenever a decision is recorded |
| `notes` | required when `reason_code` is `other` |

**`unresolved` is a legitimate entry, not a failure.** Use it whenever the abstract does not let
you decide honestly; the record then carries forward to full text. Leaving something unresolved is
always preferable to guessing.

### A spreadsheet caveat

Opening the CSV in Excel is fine, but import it as **UTF-8** and save back as CSV, not as XLSX.
A mis-set import can truncate abstracts, drop rows or reformat PMIDs. The validator detects all
three — it re-checks the row set and the derived columns against the upstream data — but it is
easier to avoid than to repair.

## 3. Validate

```bash
.venv/Scripts/python -m scripts.screening.validate_screening --stage ta
```

Writes `results/validation/screening_ta_validation.md`. Exit 1 on any error.

**Errors:** unknown decision · exclusion with no reason · reason not permitted at this stage ·
reason recorded on an inclusion · decision with no reviewer · `other` without justification ·
duplicate `report_id` · rows added or deleted · a derived column edited · a retrieval status used
as an exclusion reason.

**Warnings:** reports not yet screened · reports left `unresolved` · full text retrieved but not
yet screened.

## 4. Full text

```bash
.venv/Scripts/python -m scripts.screening.worksheet --stage ft
.venv/Scripts/python -m scripts.screening.validate_screening --stage ft
```

The full-text worksheet is built from the title/abstract **includes** only. It adds
`full_text_status` (`sought` · `retrieved` · `unavailable`). A report whose full text is
`unavailable` **cannot carry an eligibility decision** — PRISMA reports it as *not retrieved*, which
is not an exclusion, and the validator enforces that.

## 5. PRISMA counts

```bash
.venv/Scripts/python -m scripts.screening.prisma
```

Writes `results/validation/prisma_counts.md`. Every number is derived from a dataset that exists or
printed as `<pending>`; **nothing is estimated**. `<pending>` means the stage has not been done,
which is deliberately distinguished from a zero — the two are different claims.

It also checks identities that the flow must satisfy, and fails if any is violated:
identified − duplicates = unique reports · unique reports = rows in the worksheet · decisions sum
to the number screened · reports sought ≤ title/abstract includes · full-text decisions ≤ assessed ·
full-text exclusions = sum of reason counts.

Included **studies** and studies in synthesis stay `<pending>` regardless of screening progress,
because `study_id` is assigned by the reviewer at full text: several reports can describe one
population (D004), and the pipeline cannot infer that.

## Unresolved protocol decisions this module does not settle

Two things are **configurable and explicitly unresolved**, not quietly decided:

1. **Stage assignment of exclusion reasons is a proposal, not protocol.** The table in
   `docs/protocol/eligibility_criteria.md` fixes the reason codes but assigns no stages. The
   `stages` values in `config/screening.yaml` restrict `no_reference_group`, `no_usable_data`,
   `outcome_not_separable` and `duplicate_publication` to full text, on the grounds that they
   cannot be judged from an abstract without guessing. **This needs the reviewer's endorsement**
   before decisions made under it count as protocol-conformant.
2. **No anatomical or histological reason codes exist yet.** The subsite and histology audits
   proposed `wrong_subsite_oropharynx`, `wrong_subsite_lip`, `subsite_not_separable` and
   `non_scc_histology`. None is implemented, because the decisions behind them are open — lip
   scope, the soft-palate/uvula convention, the straddling codes C02.8/C02.9/C05.8/C05.9/C06.80,
   site purity, and whether SCC variants count as SCC. Until they are settled a screener records
   `unresolved`, or `other` with a written justification.

Also still open and relevant: **P003** (whether an undefined "non-smoker" reference group is
eligible) and **P006** (protocol registration, which should precede screening). **P004** affects
extraction rather than title/abstract eligibility.
