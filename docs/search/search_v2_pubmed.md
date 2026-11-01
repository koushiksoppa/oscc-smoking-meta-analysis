# Search strategy v2 — PubMed (DRAFT — NOT EXECUTED AS A SEARCH)

**Status: drafted and syntax-validated. No export exists and no records have been retrieved.**
There is deliberately no entry for v2 in `config/sources.yaml`: a registry entry asserts that an
export exists. One is added only when the researcher runs the search and exports the results
(`docs/methods/obtaining_exports.md`).

The counts below were obtained by submitting the query to PubMed and to NCBI E-utilities on
**2026-10-29 by automated tooling** (read-only, no sign-in, no account access) purely to confirm
the syntax parses, that each block behaves as intended, and what retrieval volume to expect. That
is **not** the systematic search: the search of record is the one the researcher executes and
exports, with its own date and count.

## Why v2 is needed

The v1 query string is narrower than the protocol's own eligibility criteria:

| Protocol decision | What v1 requires | Problem |
|---|---|---|
| **D008** — oral cavity cancer with SCC confirmed or ≥90% | the literal phrase "oral squamous cell carcinoma" or "OSCC" in title/abstract | Most aetiological studies report "oral cancer" or "oral cavity cancer" and state squamous histology only in the methods. No MeSH term is used. |
| **D009** — any smoked tobacco | `smoking` or `cigarette` in title/abstract | Misses "tobacco", "smokers", "smoked", "bidi", "cigar", "pipe". No MeSH term is used. |
| Case–control and cohort designs | the literal strings "case-control" or "cohort" in title/abstract | Eligible studies often say "hospital-based", "population-based", "controls" or nothing at all. |

## The v2 query

```
(
  "Mouth Neoplasms"[Mesh] OR "Oral squamous cell carcinoma"[tiab] OR OSCC[tiab]
  OR "oral cancer"[tiab] OR "oral cavity cancer"[tiab] OR "mouth cancer"[tiab]
  OR "oral carcinoma"[tiab] OR "oral neoplasm"[tiab] OR "oral neoplasms"[tiab]
  OR "oral malignancy"[tiab] OR "tongue cancer"[tiab] OR "tongue carcinoma"[tiab]
  OR "buccal mucosa"[tiab] OR "floor of mouth"[tiab] OR "gingival carcinoma"[tiab]
)
AND
(
  "Smoking"[Mesh] OR "Tobacco Products"[Mesh] OR smoking[tiab] OR smoker[tiab]
  OR smokers[tiab] OR smoked[tiab] OR cigarette[tiab] OR cigarettes[tiab]
  OR tobacco[tiab] OR bidi[tiab] OR bidis[tiab] OR beedi[tiab] OR cigar[tiab]
  OR cigars[tiab] OR "pipe smoking"[tiab] OR kretek[tiab] OR "reverse smoking"[tiab]
)
AND
(
  "Epidemiologic Studies"[Mesh] OR "Risk Factors"[Mesh] OR "Odds Ratio"[Mesh]
  OR "risk factor"[tiab] OR "risk factors"[tiab] OR "odds ratio"[tiab]
  OR "odds ratios"[tiab] OR "relative risk"[tiab] OR "hazard ratio"[tiab]
  OR controls[tiab] OR "case control"[tiab] OR cohort[tiab]
  OR etiology[tiab] OR aetiology[tiab]
)
```

**Filters: none.** No language, species, date or publication-type filter is applied, per **D013**.
Language and species restrictions are applied at screening, where each exclusion is recorded.

## Block design and field tags

| Tag | Meaning |
|---|---|
| `[Mesh]` | MeSH heading; **auto-explodes** to narrower headings. Indexed records only. |
| `[tiab]` | Title and abstract words; reaches records that are not yet MeSH-indexed. |

Every block pairs controlled vocabulary with free text, because MeSH alone misses recent records
(42 of the 194 records in `pubmed_v1r` have no MeSH at all) and free text alone misses older
indexed records.

**Outcome block.** `"Mouth Neoplasms"[Mesh]` explodes over Gingival, Lip, Palatal, Tongue and
Salivary Gland Neoplasms, so the oral-cavity subsites need no separate MeSH terms. Free-text
synonyms cover the unindexed remainder.

Deliberately **not** used: `AND "Carcinoma, Squamous Cell"[Mesh]`. Requiring an explicit SCC term
would exclude studies that report "oral cancer" and confirm squamous histology only in the methods —
precisely the studies D008 is designed to include. Histology is therefore verified at screening and
extraction (`scc_proportion`, `histology_confirmed`), not at the search stage.

Deliberately **excluded**: oropharynx, larynx, pharynx and "head and neck" terms. D008 makes
estimates that pool those subsites with the oral cavity ineligible unless an oral-cavity-specific
estimate is reported. Eligible papers of that kind will still be retrieved through the oral-cavity
terms they also contain.

**Exposure block.** `"Smoking"[Mesh]` explodes over Cigarette Smoking, Tobacco Smoking and Water
Pipe Smoking; `"Tobacco Products"[Mesh]` covers product terms. Free text adds the inflections v1
missed (`smokers`, `smoked`) and the South Asian and Indonesian products D009 includes (`bidi`,
`beedi`, `kretek`, `reverse smoking`). Smokeless tobacco and betel quid are **not** exposure terms
(D009); they are extracted as confounders. Papers covering both will be retrieved via their
smoking terms.

**Design block.** `"Epidemiologic Studies"[Mesh]` explodes over Case-Control Studies, Cohort Studies
and Cross-Sectional Studies, so **no literal "case-control" or "cohort" label is required**.
`"Risk Factors"[Mesh]`, `"Odds Ratio"[Mesh]` and the effect-measure free-text terms catch
aetiological studies that describe their design only in the methods.

## Validated counts (syntax check, 2026-10-29, by automated tooling)

| Line | Query | Count |
|---|---|---|
| 1 | Outcome block alone | 105,270 |
| 2 | Exposure block alone | 493,884 |
| 3 | Design block alone | 6,442,249 |
| 4 | **1 AND 2 AND 3 — the v2 query** | **4,770** |
| 5 | 1 AND 2 (design block removed) | 7,875 |
| — | v1 query string, unfiltered, same date | 194 |

The syntax parses, every MeSH term resolves, and the returned records are on topic. The design
block removes about 39% of line 5 while requiring no design label, which is its intended behaviour.

## Volume: a feasibility problem for the researcher to decide (P013)

v2 retrieves roughly **25× as many records as v1r** — 4,770 against 194. Under **D010** a single
reviewer screens every one at title and abstract. At a sustained 15 seconds per record that is
around 20 hours of screening, before any full-text work.

This is reported rather than resolved. **The query is not narrowed to make the workload convenient**
— that would trade away sensitivity for comfort, which the protocol forbids. The options, with their
honest costs, are set out for the researcher in the open question **P013** in the decision log.

## Still outstanding

- **P007** — PubMed alone does not constitute a systematic search. Embase and Scopus or Web of
  Science, plus reference-list and citation checking, remain to be decided and will each need their
  own strategy document with platform-specific syntax. A PubMed query cannot be pasted into Embase.
- **PRESS peer review** of this strategy has not been performed.
- Once the researcher executes and exports v2, its registry entry records the execution date, the
  count PubMed reported, the filters actually applied, and the export's checksum.
