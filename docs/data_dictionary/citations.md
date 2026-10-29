# Data dictionary — citation table

File: `data/processed/citations/<source_id>_citations.csv`, produced by `scripts/acquisition/parse_citations.py`.
Companion file `<source_id>_records.jsonl` holds every raw tag of every record (lossless) plus the raw file's SHA-256.

All values are copied as reported by the database. Empty means **not reported**; nothing is inferred. Multi-valued fields are joined with `"; "`.

| Field | Source tag (PubMed) | Description |
|---|---|---|
| `record_id` | — | `<source_id>:<PMID>`. Unique per database record. |
| `source_id` | — | Key into `config/sources.yaml` (database × search version). |
| `database` | — | Database searched. |
| `search_version` | — | Search strategy version (`docs/search/`). |
| `raw_line_start` | — | 1-based line in the raw export where the record starts (traceability). |
| `pmid` | PMID | PubMed identifier. Required. |
| `doi` | AID/LID `[doi]` | First DOI found (AID before LID), as reported, not normalised. |
| `doi_all` | AID/LID `[doi]` | All distinct DOIs; more than one triggers a validation warning. |
| `title` | TI (or BTI for books) | Article title. Required. |
| `title_tag` | — | Which tag supplied the title. |
| `first_author` | FAU[0] (else AU[0]) | First listed author. |
| `authors` | FAU (else AU) | All authors, in order. |
| `author_count` | — | Number of authors listed. |
| `journal` | JT | Full journal title. |
| `journal_abbrev` | TA | Journal abbreviation. |
| `pub_year` | DP | First four digits of the publication date. Required; left empty if DP has no leading year. |
| `pub_date_raw` | DP | Publication date exactly as reported. |
| `abstract` | AB | Abstract text. |
| `publication_types` | PT | PubMed publication types (used at screening, e.g. Review, Meta-Analysis). |
| `languages` | LA | Language codes. |
| `mesh_terms` | MH | MeSH headings (with subheadings as reported). |
| `keywords` | OT | Author keywords. |
| `entrez_date` | EDAT | Date added to PubMed. The latest value bounds the search date from below. |
