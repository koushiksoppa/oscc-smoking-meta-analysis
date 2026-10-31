# Data extraction — how to run it

## What this module is, and what it is not

**It is infrastructure for recording extraction. It is not extraction.**

It generates blank tables from the studies you have included, checks that whatever you enter is
internally consistent and arithmetically possible, and hands a verified subset to the analysis
module. It produces **no values**. Not one number is pre-filled, inferred, copied from the citation
metadata or carried over from an abstract, because an extracted value must come from the full text
with a source location (provenance rule 4).

So "the extraction module works" and "the extraction is done" are different claims. The second is
currently false: nothing has been extracted, because nothing has been screened.

## Prerequisites

Extraction is the fifth stage and sits behind three gates:

1. **Title/abstract screening** — `data/screening/screening_ta.csv`
2. **Full-text screening** — `data/screening/screening_ft.csv`, with reports marked `include`
3. **The eligibility decisions** that full-text screening depends on: **P003**, and the anatomical
   and histological decisions **P014–P022**

Running the template generator before those gates fails deliberately:

```
FAIL: the full-text worksheet does not exist, so no study has been included yet.
```

## Where the files live, and why

| Path | Tracked in Git? | Why |
|---|---|---|
| `data/extraction/studies.csv` | **yes** | Extracted values are human research work and cannot be regenerated |
| `data/extraction/estimates.csv` | **yes** | same |
| `data/processed/**` | no — gitignored | Regenerable by re-running the pipeline |

Same reasoning as the screening worksheets. `data/processed/` is ignored because anything in it can
be rebuilt from the raw export; extraction cannot be rebuilt from anything.

## 1. Generate the templates

```bash
.venv/Scripts/python -m scripts.extraction.template
```

Creates both tables. One `studies` row per full-text include; the `estimates` table is created
**empty**, because how many estimates a study reports is only knowable once you read it.

Running it again **refuses to overwrite**. To pick up studies included after a later screening pass:

```bash
.venv/Scripts/python -m scripts.extraction.template --refresh
```

`--refresh` keeps every value already entered and adds only new rows. If a row holding extracted
values is no longer among the full-text includes, the command **fails** rather than dropping it —
if a study was excluded after extraction, record that decision rather than deleting the data.

## 2. A study is not a report

`study_id` is seeded from `report_id`, which is a convenience, not a claim. **Several reports can
describe one study population** (D004), and only you can tell — typically from overlapping
recruitment periods, centres and sample sizes.

When you find two reports of one population:

- keep **one** `studies` row, choose its `primary_report_id`, and list all of them in `report_ids`;
- record the other report's exclusion as `duplicate_publication` in the full-text worksheet,
  pointing at the retained `report_id`.

This is the step that makes the PRISMA flow's "reports" and "studies" counts differ, and the
difference is reported rather than hidden.

## 3. Enter study-level values

Required for every row: `study_id`, `primary_report_id`, `first_author`, `pub_year`, `country`,
`design`.

**Missing is a value.** Use `NR` (not reported), `NA` (not applicable) or `UNCLEAR`. Never leave a
field blank to mean "not reported", and never enter zero for an unknown count — the validator
cannot distinguish a real zero from a guess.

Fields that carry the D008 outcome definition:

| Field | Notes |
|---|---|
| `anatomical_sites` | **Verbatim**, as the paper words it. Do not translate into codes |
| `site_separable` | `yes` if an oral-cavity-specific estimate is reported; `no` triggers a warning, because D008 makes a pooled-site estimate ineligible without one |
| `histology_confirmed` | `all` / `partial` / `NR` |
| `scc_proportion` | Per cent SCC. **Below 90 with `histology_confirmed` other than `all` is an error**, not a warning — the study does not meet D008, so record the exclusion instead of extracting it |

## 4. Add estimate rows

One row per **reported** estimate. **Keep them all** — crude and adjusted, ever and current,
different models (provenance rule 8). Preserving them costs nothing and is the only way a later
sensitivity analysis is possible.

Required: `estimate_id`, `study_id`, `source_location`, `measure`, `estimate`, `ci_low`, `ci_high`,
`adjustment`, `adjusted_alcohol`, `verified`.

| Field | Notes |
|---|---|
| `source_location` | **Required.** "Table 3, row 2, p. 1145". A number with no location cannot be checked by anyone, including you in six months |
| `ci_low`, `ci_high` | As reported. Named to match `scripts/analysis/`; an earlier draft of the data dictionary said `ci_lower`/`ci_upper` |
| `adjusted_for` | The **full covariate list, verbatim**. Required when `adjustment` is `adjusted` |
| `adjusted_alcohol` | Its own field, because alcohol is the dominant confounder for oral cancer (D009). `no` raises a warning for the alcohol-adjusted subgroup analysis |
| `exposure_category` | **Verbatim.** Never map a study's categories onto anyone else's — provenance rule 9 forbids silent harmonisation |
| `product_types` | cigarette / bidi / cigar / pipe / mixed / NR (D009) |
| `log_estimate_calc`, `se_calc` | **Derived — never type these.** The analysis module computes them and records the formula in `derivation` |
| 2×2 cells | Enter all four or none. With all four, the validator compares the implied OR against the reported estimate |

**Two fields are deliberately unresolved.** `comparator_type` depends on **P003**, and
`exposure_contrast` depends on **P004**. Record what the study reports; the validator notes the
value as *pending* and treats an unexpected one as a warning rather than an error, because the
enum is not yet protocol. Once P003 and P004 are decided, the config is updated and those values
become enforced.

## 5. Verify, then select

**`verified`** means a second pass over the number against its source. An estimate with
`verified = no` **cannot** enter a synthesis; the validator refuses it.

**`selected_for_analysis`** marks the one estimate per study that enters an analysis. At most one
per `study_id`, or the study is counted twice (D004). It requires a written
**`selection_rationale`**, because choosing among a study's estimates is a methodological judgement
— it depends on the adjusted-versus-unadjusted rule, on P003 and P004, and on which models the
paper reports. No code makes that choice, and nothing is deleted: unselected estimates stay in the
table.

A rationale worth writing looks like *"maximally adjusted model including alcohol; ever vs never
contrast per P004"*, not *"the main one"*.

## 6. Validate

```bash
.venv/Scripts/python -m scripts.extraction.validate_extraction
```

Writes `results/validation/extraction_validation.md`. Exit 1 on any error.

**Errors** — impossible sample sizes (`n_cases > n_total`, `n_cases + n_controls > n_total`),
negative or fractional counts, percentages outside 0–100, an SCC proportion below the D008
threshold without confirmed histology, a non-positive estimate or CI bound, `ci_low ≥ ci_high`, a
point estimate outside its own interval, an adjusted estimate with no covariate list, a duplicate
`study_id` or `estimate_id`, an estimate referencing an unknown study, a selection that is
unverified or has no rationale, more than one selection per study, a missing required field.

**Warnings** — an estimate more than 10% from the geometric mean of its interval, 2×2 counts
implying an OR more than 20% from the reported estimate (expected when the reported figure is
adjusted — confirm that is the explanation), no alcohol adjustment, `site_separable = no`, a
partial 2×2 table, no estimate selected yet.

### A spreadsheet caveat

Opening these in Excel is fine, but import as **UTF-8** and save back as CSV, not XLSX. A mis-set
import can reformat numbers, drop rows or mangle long verbatim text. The validator catches
impossible values but cannot detect a plausible-looking number that was silently reformatted.

## 7. Hand off to the analysis

```bash
.venv/Scripts/python -m scripts.analysis.run_analysis
```

Reads `data/extraction/estimates.csv` and **refuses while it does not exist**. It also refuses any
row marked synthetic, so a test fixture cannot reach `results/`.

Before trusting any output, read **`docs/methods/analysis_validation.md`**: it records what the
analysis module's validation establishes and, more importantly, what it does not — REML has no
external reference check, and the pooled estimate is verified only against hand arithmetic.

## Still unresolved, and what each blocks

| Decision | Blocks |
|---|---|
| **P003** comparator | Full-text eligibility; the `comparator_type` enum |
| **P004** contrast | The `exposure_contrast` enum; the primary analysis |
| **P014–P020** subsites, lip, soft palate, straddling codes, registry groups, site purity, separability | Full-text eligibility; `anatomical_sites` interpretation |
| **P021, P022** SCC variants; adenosquamous, sarcomatoid, minor salivary SCC | `histology_confirmed` and `scc_proportion` interpretation. **Both need the WHO Blue Book, which was inaccessible** |

Recommendations, with options and trade-offs:
`docs/methods/protocol_decisions_for_researcher.md`.
Evidence for the anatomical and histological decisions, with sources and access dates:
`docs/protocol/anatomical_histological_scope.md`.
