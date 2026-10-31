# Validation record — statistical analysis module

What has and has not been verified about `scripts/analysis/`. The distinction matters: a tested
module is not an accurate one unless the tests compare it with something external, and only part of
this module has such a comparison.

**No real pooled estimate exists.** `run_analysis.py` reads `data/extraction/estimates.csv`, which
does not exist, and refuses to run. Every number below comes from a published source or from
synthetic fixtures.

## 1. External check against published values

**Source:** Deeks JJ, Higgins JP, Altman DG, McKenzie JE, Veroniki AA (eds). *Chapter 10:
Analysing data and undertaking meta-analyses* (last updated November 2024). In: Higgins JP et al.
(eds), **Cochrane Handbook for Systematic Reviews of Interventions, version 6.5**. Cochrane, 2024.
Section **§10.10.4.5, Example 1** (Figure 10.10.a, Panel A).
URL: `https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-10`
**Accessed 2026-10-31.** Original source read directly (not a reproduction).

Published verbatim: *"There is some evidence of between-study heterogeneity (Tau2 = 0.0963; Chi2 =
9.87, df = 4, P = 0.043) and inconsistency I2 = 59.8%."*

| Quantity | Published | Computed here | Agreement |
|---|---|---|---|
| p-value of Q, from Q = 9.87, df = 4 | 0.043 | **0.0427** | **Reproduced** (rounds to 0.043) |
| I² from Q = 9.87, df = 4 | 59.8% | **59.47%** | **Differs by 0.33 pp** — see below |
| Pooled estimate, its CI, τ² | given | **not checkable** | per-study data is in a figure, not the text |

### The 0.33 pp difference in I², and why it is not hidden

Two explanations, both consistent with the source, and I cannot distinguish them:

1. **Q is published rounded to two decimals.** I² = (Q − df)/Q is sensitive to that: **Q = 9.950
   reproduces the published 59.80% exactly**, and 9.950 rounds to 9.95, close to the printed 9.87
   but not equal to it — so rounding alone does not fully explain it either.
2. **A different I² formula.** The same section states that RevMan computes I² from τ² and the
   "typical" within-study variance rather than from Q, and that the two coincide *only when τ² is
   estimated by DerSimonian–Laird*. If the published example used REML, the τ²-based I² would
   legitimately differ from the Q-based value computed here.

This module computes I² from Q and df (Higgins & Thompson 2002) and says so. The difference is
encoded in `tests/test_analysis.py::test_i_squared_against_published_cochrane_example` with an
explicit tolerance, so it is asserted rather than glossed over.

### What this external check does and does not establish

It confirms Cochran's Q p-value and the I² formula. It says **nothing** about the pooled estimate,
the weights, τ², the prediction interval, leave-one-out or Egger's test, because the example's
per-study inputs are only in a figure. I searched the chapter text for study-level data (point
estimates with intervals) and found none.

## 2. Internal check against arithmetic worked by hand

For the paths with no external reference, the tests assert against arithmetic written out in full
in the test file, so a reader can verify it with a calculator. Two fixture sets:

**Homogeneous** — log estimates 0.0, 1.0, 0.5 with SEs 0.5, 0.5, 0.25:
variances 0.25, 0.25, 0.0625 · weights 4, 4, 16 · total 24 · mean 12/24 = **0.5** ·
SE = √(1/24) = **0.2041241** · Q = 4(0.5)² + 4(0.5)² + 0 = **2.0**, df 2 ·
I² = (2−2)/2 = **0%** · C = 24 − 288/24 = **12** · τ²(DL) = (2−2)/12 = **0**

**Heterogeneous** — log estimates 0.0, 1.0, 0.5 with SE 0.2 each:
weights 25 each · total 75 · mean **0.5** · Q = 25(0.25 + 0.25) = **12.5**, df 2 ·
I² = (12.5−2)/12.5 = **84%** · C = 75 − 1875/75 = **50** · τ²(DL) = (12.5−2)/50 = **0.21**

**A correction this process caught.** My first hand value for the SE of OR 2.00 (95% CI 1.00–4.00)
was 0.3537552. The correct value is **0.35365302** — 1.38629436 / 3.91992797. The code was right
and my arithmetic was wrong. The test now carries the corrected value with each step shown.

Also asserted analytically: weights sum to 100% · random effects reduces to fixed effect when
τ² = 0 · random-effects SE exceeds fixed-effect SE under heterogeneity · equal variances give
equal weights · I² is truncated at zero.

## 3. REML — self-consistency only

**REML is not cross-validated against any external reference implementation.** No comparison with
`metafor` or any other package has been made, and none is claimed. What is tested:

- the returned τ² is a **fixed point of its own update** — applying the iteration once more returns
  the same value, confirming the iteration has actually converged to the solution of the equation
  as implemented;
- τ² = 0 when the studies agree;
- τ² > 0 under clear heterogeneity;
- non-convergence is reported in `MetaResult.notes` and must not be read as a final estimate.

This establishes that the implementation solves the equation it encodes. It does **not** establish
that the equation is the correct REML estimating equation. Every REML result carries that caveat in
its own notes. **Before any REML estimate is reported in a manuscript it should be checked against
`metafor::rma(method="REML")`** — a step that is not yet possible here and is recorded as an
outstanding limitation.

## 4. Deliberate refusals

The module declines to compute rather than producing a number of no value:

| Situation | Behaviour |
|---|---|
| Egger's test with k < 10 | **Refused** — low power makes a null result uninformative; state it as a limitation |
| Egger's regression with an exact fit | **Refused** — zero residual variance leaves t undefined; reported rather than returned as `nan` |
| Prediction interval with k < 3 | Withheld; the t multiplier needs k−2 df |
| Leave-one-out with k < 3 | Refused; each re-analysis would be a single study |
| Zero cell in a 2×2 table | Refused; no continuity correction is applied silently |
| A CI level other than 95% | Refused rather than converted |
| Mixing OR, RR and HR | Refused; they estimate different quantities |
| One study contributing twice | Refused (D004: the study is the unit of analysis) |
| A point estimate outside its own CI | Refused as an extraction error |
| Estimate inconsistent with its CI by > 10% | Recorded as a note; estimate kept as reported, SE from the interval |

## 5. Synthetic data containment

Fixtures cannot become findings:

- every fixture sets `synthetic=True` and a `study_id` prefixed `SYNTHETIC-`;
- `validate_set` **refuses outright** to pool synthetic and real estimates together;
- `synthetic` propagates into `MetaResult`, `EggerResult`, every summary string and every figure;
- synthetic figures are **watermarked** "SYNTHETIC TEST DATA — NOT A RESEARCH RESULT" across the face;
- `run_analysis.py` refuses any input row marked synthetic, so nothing synthetic can be written to
  `results/`.

## 6. Outstanding limitations

1. **REML has no external validation.** See §3.
2. **The pooled estimate, weights and τ² have no external validation** — only hand arithmetic, for
   want of a published example with per-study data.
3. **No Hartung–Knapp–Sidik–Jonkman adjustment.** The Cochrane Handbook §10.10.4 notes HKSJ has
   better properties than the Wald-type interval when k > 2 and τ² > 0 — the situation this review
   is likely to be in. Not implemented; a decision for the reviewer.
4. **No Mantel–Haenszel or Peto methods**, so rare-event and zero-cell data have no route.
5. **No dose–response (one-stage or two-stage trend) model.** Deferred until it is known whether
   comparable exposure categories exist.
6. **No meta-regression or formal subgroup interaction test.** Subgroups would currently be
   separate pooled analyses, which is weaker than testing interaction directly.
7. **Python/SciPy only** (D015). No R cross-check, as instructed.
