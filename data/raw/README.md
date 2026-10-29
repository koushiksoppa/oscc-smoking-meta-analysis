# Raw data — immutable

Files here are exports from bibliographic databases (rules: `docs/protocol/provenance_rules.md`).

1. **Never edit, re-save, re-encode, or recreate a file here.** Cleaning happens in scripts that write to `data/processed/`.
2. Every file has an entry in `config/sources.yaml` describing **one search execution** — database, search version, execution type, the filters actually applied, the record count and where that count came from (D011).
3. Its SHA-256 is recorded once in `SHA256SUMS` (append-only, `sha256sum -c` compatible) by
   `python -m scripts.acquisition.verify_raw --source <id> --register`. Registration succeeds only if the record count matches the count reported for that source.
4. Line-ending conversion by Git is disabled for this directory (`.gitattributes`), so checksums stay valid on every OS.
5. **One file per execution.** A re-run of the same query is a separate file with a separate registry entry, never a replacement (D005, D011). Filenames are never reused.

Adding a new export: `docs/methods/obtaining_exports.md`.

## Status

| Source | Execution | File | Records | Status |
|---|---|---|---|---|
| `pubmed_v1` | historical (v1 query, Humans + English) | — | 138 *claimed, unverified* | **Export missing.** Not on this machine; a filesystem-wide search found no copy. Not recreated, not substituted (D005). Contributes no records to the PRISMA flow unless recovered. |
| `pubmed_v1r` | re-execution (v1 query, **no filters**) | `pubmed/pubmed-v1r-reexecution-194.nbib` | 194 | **Awaiting registration.** Intake report clean (194 = 194 = 194, no anomalies). Registration is the researcher's call. |

`pubmed_v1r` is **not** the original v1 export. The 138-vs-194 difference is analysed in
`docs/search/search_v1r_pubmed_reexecution.md`; about 9 records remain unexplained (P012).
