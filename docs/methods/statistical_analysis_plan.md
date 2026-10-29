# Statistical analysis plan — skeleton

**Status: NOT A PLAN YET.** This file records what the SAP must specify and which input each
specification waits on. It must be completed and approved **before** any pooled estimate is
computed (provenance rule 13–14). Nothing in it may be chosen to produce a more favourable result
(rule 15); every choice is justified from the study designs and the available data.

Two kinds of dependency are distinguished:

- **(decision)** — needs the reviewer's ruling; can be settled now.
- **(evidence)** — genuinely cannot be settled until the included studies are known, because it
  depends on which designs and measures actually appear. Settling it now would be guesswork.

## 1. Effect measure

| To specify | Depends on |
|---|---|
| Primary measure (OR / RR / HR) | **(evidence)** which designs are included |
| Whether case–control and cohort estimates may be pooled at all, or are analysed separately | **(evidence)** |
| Treatment of HRs if cohort studies report them | **(evidence)** |
| Log transformation and standard-error derivation from the reported CI | fixed method, documented below |

Constraints already fixed: fundamentally different measures are not combined without a documented
justification (rule 11); no transformation is applied merely to make pooling easier. For a rare
outcome such as oral cancer, OR and RR approximate each other, but that argument must be made
explicitly with reference to the observed baseline risks, not assumed.

Standard errors are derived as `SE = (ln(upper) − ln(lower)) / (2 × 1.96)` where a 95% CI is
reported, and from raw cell counts where only a 2×2 table is given. Which route was used is recorded
per estimate, and reported and calculated values are kept in separate fields.

## 2. Primary analysis

| To specify | Depends on |
|---|---|
| Exposure contrast | **P004** |
| Reference group handling | **P003** |
| Adjusted vs unadjusted estimate preference, and the rule for choosing among several adjusted models in one paper | **(decision)** — recommendation: the maximally adjusted estimate that includes alcohol, with the choice recorded per study |
| Model: random effects, with estimator (REML / DerSimonian–Laird) and small-sample adjustment (Knapp–Hartung) | **P008** + **(evidence)** on k |
| One estimate per `study_id` per analysis | fixed (D004) |

A random-effects model is anticipated because clinical and methodological heterogeneity is expected
across countries, exposure definitions and adjustment sets — but the estimator and the small-sample
adjustment are stated only once k is known, since Knapp–Hartung matters most when k is small.

## 3. Heterogeneity

Report τ², I², Cochran's Q with its p-value, and a prediction interval. I² is **not** interpreted
mechanically or against fixed thresholds; it is read alongside τ², the prediction interval, k, and the
clinical and methodological differences between studies (population, exposure definition, comparator
definition, adjustment set, design).

## 4. Subgroup analyses

Candidates, each to be run **only** if enough studies report it — the minimum k per subgroup is
specified in advance **(decision)**, with a recommendation of at least 4 studies per group:

design (case–control vs cohort) · adjusted vs unadjusted · product type, cigarette-only vs mixed
(D009) · exposure contrast (current / former / ever) · dose–response tier where categories are
comparable · geographic region · anatomical subsite · risk-of-bias level · alcohol-adjusted vs not.

Subgroups are prespecified here; anything added later is reported as post-hoc. Interaction is assessed
formally rather than by comparing whether each subgroup estimate crosses 1.

## 5. Sensitivity analyses

Each requires a stated methodological reason. Candidates: leave-one-out; excluding high-risk-of-bias
studies; adjusted estimates only; alcohol-adjusted estimates only; one design only; alternative
heterogeneity estimator; alternative SE derivation where a CI was asymmetric.

## 6. Small-study effects and publication bias

Funnel plot and a formal test (Egger-type regression, or Peters' test if OR-based) **only if k ≥ 10**
**(evidence)**. Below that threshold the tests are uninformative and will not be run or interpreted;
the limitation is stated instead.

## 7. Criteria for not pooling

Pooling is **inappropriate**, and a structured narrative synthesis is reported instead, if any of:

- fewer than 3 studies contribute to a contrast;
- the only available estimates mix non-comparable exposure categories that cannot be used without
  harmonisation (rule 9);
- the only available estimates mix adjusted and unadjusted without a defensible basis (rule 6);
- comparator definitions are irreconcilable across studies;
- heterogeneity is so extreme that a summary estimate would misrepresent the evidence.

Deciding not to pool is a legitimate result and is reported as such.

## 8. Software and verification

Language per **P008**. Before touching study data, the analysis code reproduces at least one
published worked example with known pooled estimate, CI, τ² and I². Any discrepancy blocks the
analysis. All outputs are generated by script; no number is typed into a table or figure by hand.

## 9. Interpretation rules

Report the estimate with its CI and the prediction interval. "Significant" is not used as a verdict
on the basis of p < 0.05 alone. Residual confounding — above all by alcohol, and by betel quid in
South Asian populations — is discussed explicitly. No causal claim is made from observational
association (rule 19).
