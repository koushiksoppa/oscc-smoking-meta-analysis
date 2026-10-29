# Proposed intake report — pubmed_v1r

**This report is a proposal, not a registration.** Nothing in `data/` has been created or
modified, and `data/raw/SHA256SUMS` has not been written. The checksum below becomes the
project's authoritative value only when the reviewer authorizes
`verify_raw --source pubmed_v1r --register`.

**Verdict: CONSISTENT — awaiting the reviewer's authorization to register**

## File

| Property | Value |
|---|---|
| Path | `data/raw/pubmed/pubmed-v1r-reexecution-194.nbib` |
| Size | 958,710 bytes |
| SHA-256 | `1d153fa80edd6bc97c92498bce8076873cc514f412de5113412fa71827e4ca1e` |
| Database | PubMed |
| Search version | v1r |
| Execution type | re_execution |
| Filters applied at retrieval | none |
| Strategy document | `docs/search/search_v1r_pubmed_reexecution.md` |
| Execution date | *not recorded* |
| Checksum already registered | no |

## Record count

Counted two independent ways; both must agree with the count reported for this source.

| Method | Count |
|---|---|
| Record parser | 194 |
| `PMID-` tag scan | 194 |
| Reported for this source | 194 |

Provenance of the reported count: Count reported by the researcher from the PubMed results page at execution, and consistent with the 194 records in the export.

## Anomalies

None.

## Notes

- Latest Entrez date in the file: 2026/10/25 03:36. This is a LOWER BOUND on the search date, not the search date itself (decision-log P009).
- Publication years span 1998–2026.

## Next step

If you confirm this is the export produced by the re_execution search described in `docs/search/search_v1r_pubmed_reexecution.md` (filters applied: none), authorize:

```
python -m scripts.acquisition.verify_raw --source pubmed_v1r --register
```
