# Deduplication summary

**Status: RESOLVED — counts are final for these sources**

Sources included: pubmed_v1r

## Counts for the PRISMA flow

| Item | Count |
|---|---|
| Records identified (all sources) | 194 |
| … from `pubmed_v1r` | 194 |
| Duplicate records removed | 0 |
| Unique reports (`report_id`) | 194 |

Records are mapped to a `report_id`, never deleted; `data/processed/dedup/report_index.csv`
retains every input record. A `report_id` is a unique *publication*; the unique *study*
(`study_id`) is established later, at full text, by the reviewer (D004).

## Matching

- Pairs merged on a shared identifier or exact fingerprint: 0
- **Duplicate groups** (canonical reports backed by more than one record): 0
- Candidate pairs needing the reviewer's decision: 0

Pairs and groups count different things: a group of three records is three merged pairs but one canonical report. Pairs awaiting review form no group, because they are not merged.

No record was merged with another: every record is its own canonical report.

No pair required manual review.

## Method

Matching is deterministic and applied in order of decreasing authority (D014):

1. shared PMID
2. shared DOI
3. identical title + first author + year fingerprint
4. similar title in the same year (similarity ≥ 0.92) — **flagged for review, never merged**

DOIs are normalised (lowercased, URL and `doi:` prefixes stripped, trailing punctuation removed) and the fingerprint folds accents and reduces the title to alphanumeric words. Normalised values are used only for matching and never overwrite the values extracted from the export. Empty keys never match. Grouping is the transitive closure of the exact tiers, so group membership does not depend on their order; the order determines only which criterion is reported as the reason for a merge.

The representative record of each group is chosen deterministically: earliest source in `config/sources.yaml`, then lowest numeric PMID, then lowest `record_id`. Field definitions and how to read these counts: `docs/data_dictionary/dedup.md`.
