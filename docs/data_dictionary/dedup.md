# Data dictionary — deduplication outputs

Produced by `scripts/dedup/deduplicate.py` (Stage 2). Inputs are the citation tables of every
registered source with a verified export. **No record is ever deleted:** deduplication assigns a
shared `report_id` to records that describe the same publication and leaves every input record in
place.

## Identifier chain (D004)

| Identifier | Unit | Assigned |
|---|---|---|
| `record_id` | one record in one database export, `<source_id>:<PMID>` | Stage 1 |
| **`report_id`** | **one unique publication** | **Stage 2, here** |
| `study_id` | one underlying study population | full text, by the reviewer |
| `estimate_id` | one reported effect estimate | extraction |

Stage 2 stops at the *publication*. Two reports of the same cohort remain two `report_id`s and are
collapsed to one `study_id` only at full text, by human judgement — the pipeline cannot know that
two different papers describe one population.

## Provenance gate

Before reading anything, each selected source must pass two checks. Both are required because
neither implies the other, and a failure stops the stage rather than being reported:

1. its raw export matches the checksum registered in `data/raw/SHA256SUMS`;
2. the parsed data in `<source_id>_records.jsonl` records **that same** checksum as the file it was
   produced from.

Without (2) an export could be re-registered or re-parsed while the citation table was left stale,
silently feeding outdated records into the PRISMA count. A missing or unreadable `raw_sha256` is an
error, never an implicit pass. Sources whose registry entry records a missing export are skipped
from the default selection and their entries are left untouched (D011).

## Matching

Applied in order of decreasing authority (**D014**). Normalisation is used **only** for comparison
and never overwrites the citation dataset.

| Priority | Key | Normalisation | Resolution |
|---|---|---|---|
| 1 | **PMID** | whitespace stripped | `merged` |
| 2 | **DOI** | lowercased; `https://doi.org/`, `http://dx.doi.org/`, `doi:` prefixes stripped; trailing `.;,` removed | `merged` |
| 3 | **Fingerprint** — normalised title + first-author surname + year | title: accents folded, lowercased, reduced to alphanumeric words; surname: text before the first comma, alphanumeric only; year: four digits | `merged` |
| 4 | **Similar title**, same year, sequence similarity ≥ 0.92 | as above | **`needs_review` — never merged** |

**Empty keys never match.** A record with no DOI is not grouped with every other record lacking one.

**Fallback for records with neither PMID nor DOI** (priority 3): the fingerprint requires all three
of title, first-author surname and year; if any is missing the fingerprint is empty and the record
matches nothing on this tier. Such a record can still be caught at tier 4 and flagged for review.

Grouping is the transitive closure of tiers 1–3: if A shares a PMID with B and B shares a DOI with
C, all three form one group. Because it is a closure over all tiers, **group membership does not
depend on the tier order** — the order determines only which criterion is *reported*.

Tier 4 exists because a near-identical title may be a conference abstract, an erratum, a reanalysis
or a different paper. Only the reviewer can decide (D010), so the stage exits non-zero while any
such pair is unresolved: a PRISMA identification count cannot be stated while duplicate status is
undecided.

## `data/processed/dedup/report_index.csv`

One row per **input record**. Every record appears exactly once; the stage fails if this is not so.

| Field | Description |
|---|---|
| `record_id`, `source_id`, `search_version`, `pmid`, `doi`, `pub_year`, `first_author`, `title` | Copied unchanged from the citation table |
| `report_id` | Canonical publication identifier, `R0001`-style, shared by every member of a group |
| `is_primary` | `yes` for the record representing the group, `no` otherwise |
| `duplicate_of` | The group's primary `record_id`; empty when this record *is* the primary |
| `merged_with` | The record this one was **directly matched against**. Empty for a primary |
| `merge_criterion` | The evidence for that direct match: `shared PMID`, `shared DOI`, or `identical title + first author + year fingerprint`. Empty for a primary. Where several criteria matched the same pair, the **strongest** is reported (PMID > DOI > fingerprint), with the lower `record_id` breaking ties |

**Read `merged_with` and `merge_criterion` together.** A group can be a chain: if A matches B by PMID
and B matches C by DOI, all three share one `report_id` and `duplicate_of` names A for both B and C —
but C's DOI match is with **B**, not A. `merged_with` says so, and the criterion describes that pair.
Where `merged_with` differs from `duplicate_of`, the record joined the group through a chain, and
`dedup_audit.csv` holds every link in it.

`merge_criterion` may also read `transitive`, with `merged_with` empty. This is a defensive fallback
for a broken invariant and is not expected: a record can only be grouped by taking part in at least
one pair, so a direct match always exists. Seeing it means something is wrong, not that a chain occurred.

The primary is chosen deterministically: earliest source in `config/sources.yaml`, then lowest
numeric PMID, then lowest `record_id`. Determinism does not depend on input order.

## `data/processed/dedup/dedup_audit.csv`

One row per **candidate pair**. This is the full audit trail: every comparison that produced a match
appears here, including several rows for one pair when more than one criterion matched.

| Field | Description |
|---|---|
| `pair_id` | `P0001`-style |
| `record_a`, `record_b` | The two records compared; `record_a` is the lower `record_id` |
| `criterion` | The rule that matched |
| `matched_value` | The shared value, or the similarity score for tier 4 |
| `resolution` | `merged`, or `needs_review` — the latter is **not** merged |

## `results/validation/dedup_summary.md`

| Count | Meaning and interpretation |
|---|---|
| Records identified | Total input records across all sources — the PRISMA *identification* number |
| … per source | Each execution's contribution before deduplication |
| Duplicate records removed | Records identified − unique reports. The PRISMA *duplicates removed* number. "Removed" means removed from the count, not deleted from any file |
| Unique reports | Distinct `report_id` values — the number of records entering screening |
| Pairs merged | Merged rows in the audit. **Not** the number of duplicates: one group of three records is three pairs but a single canonical report |
| **Duplicate groups** | Canonical reports backed by more than one record, listed with members, primary and criteria. This is the count to read for "how many duplicates were found" |
| Pairs needing review | Tier-4 candidates. **While this is non-zero the counts above are provisional** and the stage exits non-zero |

A status line states whether the counts are final or provisional.

## What this stage does not do

It applies no eligibility criterion, excludes no record on scientific grounds, and makes no
screening decision. Those come later and are the reviewer's (D010).
