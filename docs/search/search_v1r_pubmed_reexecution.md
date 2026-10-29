# Search v1r — PubMed re-execution of the v1 query

Registry entry: `pubmed_v1r` in `config/sources.yaml`.
Export: `data/raw/pubmed/pubmed-v1r-reexecution-194.nbib`.

**This is not the original v1 export.** It is a later re-execution of the same query string, run by
the researcher, and it must never be presented as the original v1 execution (D005, D011). The
original v1 export is missing and is not recreated; its registry entry `pubmed_v1` records that fact.

## What was executed

Query string — **identical** to v1 (`search_v1_pubmed.md`), reproduced here for self-containment:

```
("Oral Squamous Cell Carcinoma"[Title/Abstract] OR OSCC[Title/Abstract])
AND
(smoking[Title/Abstract] OR cigarette[Title/Abstract])
AND
("case-control"[Title/Abstract] OR cohort[Title/Abstract])
```

| Item | Value |
|---|---|
| Platform | PubMed (NCBI), web interface |
| Filters applied | **None** — this is the material difference from v1, which documents Humans + English |
| Records retrieved | 194 |
| Export format | PubMed/MEDLINE (`.nbib`) |
| File size | 958,710 bytes |
| SHA-256 | `1d153fa80edd6bc97c92498bce8076873cc514f412de5113412fa71827e4ca1e` |
| Executed by | the researcher |
| Execution date | **not yet recorded.** Entrez dates in the export bound it to on/after **2026-10-25** |
| Registration status | awaiting the researcher's approval of the intake report |

## Evidence that no filters were applied

Established by inspecting the export itself, not assumed:

- **Language tags:** 191 records `eng`, 2 records `chi`, 1 record `eng` + `por`. An English filter
  would have removed the two Chinese-language records.
- **MEDLINE status:** 152 `MEDLINE`, 40 `PubMed-not-MEDLINE`, 2 `Publisher`. 42 records carry no
  MeSH headings at all. The Humans filter operates on the MeSH term `Humans`, so it would have
  removed all 42 — including the most recently added records.
- 152 records carry MeSH `Humans`; **0** records are MEDLINE-indexed but non-human.

## Reconciliation of 194 against the documented 138

Counts obtained by re-running the v1 query string through NCBI E-utilities on **2026-10-29**
(executed by Claude, read-only, no account access; recorded separately from the researcher's own
executions):

| Query as run | Count | Date |
|---|---|---|
| v1 query string, **no filters** | **194** | 2026-10-29 |
| v1 query string, **Humans + English** | **150** | 2026-10-29 |
| v1 query string, Humans + English, as documented in `search_v1_pubmed.md` | **138** | unknown (P009) |

Two independent confirmations follow:

1. The unfiltered count (194) **equals the number of records in the export exactly**, confirming the
   export is a complete, faithful retrieval of the v1 query string without filters.
2. The filtered count (150) **equals the figure predicted from the export's own language and MeSH
   tags**, independently confirming which filters were absent.

So the 56-record difference decomposes as:

- **44 records** — the two absent filters (194 → 150).
- **3 records** — added to PubMed on or after 2026-09-20, when the project was paused.
- **~9 records** — **unexplained.** Recorded as **P012**.

Plausible explanations for the residual, none of which can be confirmed from available evidence:
records that were not MEDLINE-indexed at the time of the original search have since acquired the
MeSH term `Humans` and thereby entered the filtered set; or the 138 figure was approximate. **No
explanation is adopted, and 138 is not changed.** The 138 figure remains a documented but
unverified claim, because no export survives against which to check it.

## Consequences for the review

- Per **D013** the unfiltered set is retained. Non-English and non-human records are excluded at
  screening with a recorded reason code rather than removed invisibly by a database filter. The
  reason codes `not_english` and `wrong_population` will therefore appear in the PRISMA flow with
  non-zero counts, where a filtered search would have shown none.
- Eligibility is **unchanged**: English-language publications, human participants (see
  `docs/protocol/eligibility_criteria.md`). Only the point at which the restriction is applied moves.
- This is a **documented deviation** from the v1 strategy and is reported as such in the manuscript.
- The v1 query string itself remains narrow for the protocol's eligibility criteria (D008, D009).
  Its appraisal is unchanged and is the basis for the proposed v2 strategy
  (`search_v2_pubmed.md`), which is drafted but **not executed**.
