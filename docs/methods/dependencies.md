# Dependencies — present and anticipated

**Nothing listed under "anticipated" has been installed.** Installation requires the reviewer's
authorisation. Each package is added to `requirements.txt`, pinned, only when the stage that needs
it is built.

## Installed

| Package | Version | Used by |
|---|---|---|
| Python | 3.14.7 (`.venv`) | all |
| `pyyaml` | 6.0.3 | `scripts/common/config.py` (source registry) |
| `pytest` | 9.1.1 | test suite |

Stage 1 otherwise uses only the standard library (`csv`, `json`, `hashlib`, `re`, `dataclasses`),
which keeps the acquisition path free of third-party parsing behaviour.

## Anticipated, by stage

| Stage | Likely need | Why | Decision |
|---|---|---|---|
| ~~2 Deduplication~~ | **none — built on the standard library** (`csv`, `re`, `unicodedata`, `difflib`) | Deterministic matching does not need a dataframe library | settled |
| 3 Screening | stdlib `csv`; optionally `openpyxl` | A spreadsheet export may be easier for a human reviewer to work in than CSV | ask before adding |
| 5 Extraction | `openpyxl` | Same reason | ask before adding |
| 7 Synthesis | **R + `metafor`**, or a Python stack | See below | **P008** |
| 8 Reporting | `matplotlib` | Forest, funnel and risk-of-bias figures | with Stage 7 |

## The statistics decision (P008)

**R + `metafor`** is the reference implementation for meta-analysis: random-effects models with REML,
the Knapp–Hartung adjustment, `leave1out()` for leave-one-out analysis, and `regtest()`/`ranktest()`
for small-study effects — all standard and peer-reviewed. **R is not installed on this machine.**

A Python route (`statsmodels`, `scipy`) can compute an inverse-variance random-effects model, but
does not provide Knapp–Hartung or the standard funnel diagnostics out of the box; they would have to
be implemented and then verified independently — most naturally against `metafor`, which argues for
installing R regardless.

Either way, before any analysis code touches study data it is verified against published worked
examples with known results (provenance rule: methods are not chosen for convenience, and results
must be reproducible).

## Reproducing the environment

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
```

`requirements.txt` is pinned exactly so a fresh checkout reproduces this environment.
