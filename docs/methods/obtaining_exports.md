# Obtaining and filing exports (PubMed → Windows → repository)

For the researcher. Nothing here has been done on your behalf: no NCBI account was accessed and no
file was downloaded for you. Each export is a research act with its own date, count and checksum.

Record four things for **every** export, at the moment you run it, because none can be reconstructed
later: the **query string as submitted**, the **filters you clicked**, the **count PubMed displayed**,
and the **date you ran it**.

## A. Running a search in PubMed

1. Go to <https://pubmed.ncbi.nlm.nih.gov/>.
2. Use **Advanced** → paste the full query into the query box, or paste it into the main search bar.
   Pasting the whole parenthesised query at once is safest: PubMed preserves your field tags and does
   not apply automatic term mapping to tagged terms.
3. After the results load, **copy the "Search details"** box (bottom right, or under Advanced →
   History) — this is PubMed's own record of how it interpreted your query, and it is the single most
   useful thing to paste into the strategy document.
4. **Write down the result count** exactly as displayed (e.g. "4,770 results").
5. **Apply no filters** unless the strategy document says to. Per **D013** we retrieve unfiltered and
   exclude by language and species at screening.
6. Note the date.

> **Recovering the v1 search date (P009).** If you were signed in to NCBI when you ran the original
> search, it may still be in your search history: sign in → **Advanced** → **History and Search
> Details**, or <https://www.ncbi.nlm.nih.gov/myncbi/>. Browser history for `pubmed.ncbi.nlm.nih.gov`
> around that period, or a saved-search email from NCBI, may also carry the date. If none of them
> does, P009 stays unresolved — do not estimate it.

## B. Exporting the records

1. On the results page click **Save**.
2. **Selection:** `All results`. (The default is "All results on this page" — only 10 records.)
3. **Format:** `PubMed`. This produces the `.nbib` / MEDLINE tagged format the parser expects.
   Not CSV, not RIS, not "Summary (text)".
4. Click **Create file**. The browser saves it to your Downloads folder, typically as
   `pubmed-<something>-set.nbib`.
5. If the download is large it may take a few seconds — wait for it to finish before moving it.

> If **Save → All results** is unavailable for a very large set, use **Send to → File** on the
> Advanced page, or export in batches and keep each batch as a separate file. Do **not** merge
> batches by hand: give each file its own registry entry, and let Stage 2 deduplication reconcile
> them.

## C. Filing the file, without overwriting anything

Each export gets a **distinct filename**. Never reuse a filename, and never save a new export over
an existing one — the whole provenance chain depends on one file per execution.

| Export | Save as |
|---|---|
| v2 PubMed search | `data/raw/pubmed/pubmed-v2-<YYYY-MM-DD>.nbib` |
| A further v1 re-run, if ever needed | `data/raw/pubmed/pubmed-v1r2-<YYYY-MM-DD>.nbib` |
| Already filed | `data/raw/pubmed/pubmed-v1r-reexecution-194.nbib` — **do not touch** |

In PowerShell, from the repository root (adjust the source filename):

```powershell
Copy-Item "$env:USERPROFILE\Downloads\pubmed-abc123-set.nbib" "data\raw\pubmed\pubmed-v2-2026-11-05.nbib"
```

Use `Copy-Item`, not `Move-Item`, so the download survives if the copy goes wrong. If the
destination name already exists, **stop** — do not overwrite; pick a new name and say so.

**Do not open the file in an editor and re-save it.** Notepad, Word and some editors change the
encoding or line endings, which changes the checksum and makes the file a different artifact. To
look inside it safely, use:

```powershell
Get-Content "data\raw\pubmed\pubmed-v2-2026-11-05.nbib" -TotalCount 40
```

Get its checksum with:

```powershell
Get-FileHash "data\raw\pubmed\pubmed-v2-2026-11-05.nbib" -Algorithm SHA256
```

## D. Registering it in the repository

1. **Add a registry entry** in `config/sources.yaml`. Copy the `pubmed_v1r` block and fill in:
   `source_id` (e.g. `pubmed_v2`), `search_version`, `execution: new`, `strategy_doc`, `raw_file`,
   `expected_records` (the count PubMed displayed), `count_source` (how you got that count),
   `search_date`, `filters_applied` (`[]` if none), `status: awaiting_registration`.
2. **Inspect it — read-only, registers nothing:**

```bash
.venv/Scripts/python -m scripts.acquisition.verify_raw --source pubmed_v2 --report-only
```

3. **Read the report** at `results/validation/pubmed_v2_intake_proposed.md`. Check the three record
   counts agree and the anomaly list is empty. Field-by-field explanation of the report, and how to
   read each anomaly: `docs/methods/intake_checklist.md`.
4. **Only if the report is clean, register the checksum:**

```bash
.venv/Scripts/python -m scripts.acquisition.verify_raw --source pubmed_v2 --register
```

5. **Parse, validate, deduplicate:**

```bash
.venv/Scripts/python -m scripts.acquisition.parse_citations --source pubmed_v2
.venv/Scripts/python -m scripts.validation.validate_citations --source pubmed_v2
.venv/Scripts/python -m scripts.dedup.deduplicate
```

Deduplication runs across **all** registered sources, so records shared between v1r and v2 are
mapped to one `report_id` and counted once. It stops with a non-zero exit if any pair of similar
titles needs your decision.

## E. What not to do

- Do not register an export against a registry entry describing a different execution. A different
  file is a different search (**D005**, **D011**).
- Do not edit a count in `config/sources.yaml` to make validation pass. If the counts disagree, the
  disagreement is the finding.
- Do not delete or re-save anything in `data/raw/`.
- Do not apply filters the strategy document does not list, and if you do apply any, record them in
  `filters_applied` — the field exists precisely because v1 and v1r differ there.
