# Search strategy v1 — PubMed (original, preserved verbatim)

Status: **executed, but its export is missing.** Registry entry: `pubmed_v1`
(`status: export_missing`). The query and filters below are preserved exactly as recorded; the
record count below is a **documented but unverified claim**, because no export survives against
which to check it.

> **Do not confuse this entry with the re-execution.** A later re-run of this same query string
> exists as `pubmed_v1r` (`docs/search/search_v1r_pubmed_reexecution.md`, 194 records, no filters
> applied). It is **not** this execution, and the file
> `data/raw/pubmed/pubmed-v1r-reexecution-194.nbib` must never be registered against `pubmed_v1`
> (D005, D011). Per D005 the original export is not recreated and not substituted.

This record must not be edited except to fill in missing provenance fields. Any change to the
strategy is a new version (v2, v3, …).

## Query

```
("Oral Squamous Cell Carcinoma"[Title/Abstract] OR OSCC[Title/Abstract])
AND
(smoking[Title/Abstract] OR cigarette[Title/Abstract])
AND
("case-control"[Title/Abstract] OR cohort[Title/Abstract])
```

## Filters

- Humans
- English

## Provenance (PRISMA-S items)

| Item | Value |
|---|---|
| Database / platform | PubMed (NCBI) |
| Date searched | **unknown (P009)** — not recoverable from any file in the repository |
| Date limits | None stated |
| Records retrieved | 138 — *documented claim, unverified; no export survives* |
| Export format | PubMed/MEDLINE (`.nbib`) |
| Export status | **Missing.** Not present on the researcher's machine; a filesystem-wide search found no copy |
| Searcher | Soppa Shiva Sai Koushik |
| Peer review of strategy (PRESS) | Not performed |

### On the 138 figure

Re-running this exact query string on 2026-10-29 returned **194 records unfiltered** and **150 with
the Humans and English filters applied**. The gap between 150 and the documented 138 is partly
explained (3 records were added to PubMed after the project was paused on 2026-09-20) and partly
**unexplained (~9 records, recorded as P012)**. The full analysis is in
`search_v1r_pubmed_reexecution.md`. The figure 138 is left unchanged: it is what was recorded at the
time, and altering it to match a later count would falsify the history of the search.

### Contribution to the PRISMA flow

Unless the original export is recovered, this execution contributes **no records** to the flow. The
records actually screened come from `pubmed_v1r` and any later search version. The flow reports the
searches actually used, and this entry is reported as a search whose export was lost.

## Appraisal of v1 (not yet acted on)

The strategy is reproducible but has low sensitivity for the research question. Specific concerns:

1. **Study-design block restricted to title/abstract words.** Many eligible case-control and cohort studies do not use the literal words "case-control" or "cohort" in the abstract (e.g., "hospital-based study", "population-based", "controls", "prospective study"). MeSH `Case-Control Studies`, `Cohort Studies`, and `Risk Factors` are not used. This block is likely the largest source of missed studies.
2. **Outcome block is narrow.** Many aetiological studies report "oral cancer", "oral cavity cancer", "mouth neoplasms", or "cancer of the tongue/gum/floor of mouth" and confirm squamous histology in the methods rather than the title/abstract. MeSH `Mouth Neoplasms` and `Carcinoma, Squamous Cell` are not used.
3. **Exposure block omits "tobacco" and inflected forms.** `smoking` does not match "smokers" or "smoked"; `cigarette` does not match "cigarettes" unless PubMed's automatic term expansion applies. MeSH `Tobacco Smoking` / `Cigarette Smoking` are not used.
4. **The "cohort" term will pull in many prognostic studies** (smoking and survival/recurrence among patients who already have OSCC). These address a different question and will be excluded at screening as *wrong outcome*; this is expected, not a flaw in screening.
5. **Single database.** PRISMA 2020 / MOOSE expect multiple sources (typically at least Embase and Web of Science or Scopus in addition to PubMed), plus reference-list checking.

## Status of a v2 strategy

The eligibility decisions that determine the content of the search blocks are now settled: **D008**
fixes the outcome as oral cavity cancer with confirmed or ≥90% SCC histology, and **D009** fixes the
exposure as any smoked tobacco. Both confirm that the v1 blocks are narrower than the protocol
requires — concerns 1–3 above are therefore not hypothetical.

A v2 strategy has **not** been drafted. It awaits:

- the reviewer's authorisation to draft it, and
- **P007**, the set of databases to be searched, since a v2 cannot be written as a single query to be
  copied across platforms; each database needs its own syntax, field tags and controlled vocabulary,
  documented in its own file.

When drafted, v2 will be a new file (`search_v2_pubmed.md`), not an edit to this one. Records from
all versions are merged and deduplicated, and the PRISMA flow reports each version's contribution
separately.
