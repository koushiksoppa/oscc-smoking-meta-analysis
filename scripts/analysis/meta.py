"""Inverse-variance meta-analysis of log ratio measures.

Implements the fixed-effect and random-effects models, Cochran's Q, I2, tau-squared by
DerSimonian-Laird and by REML, a prediction interval, leave-one-out influence analysis and
Egger's test.

Validation status is recorded honestly in docs/methods/analysis_validation.md:
  * Q, its p-value and I2 are checked against published values (Cochrane Handbook v6.5 §10.10.4.5).
  * The fixed-effect and DerSimonian-Laird paths are checked against arithmetic worked by hand in
    the tests, where every intermediate value is written out.
  * REML is checked for self-consistency (its solution is a fixed point of its own update) and for
    the limiting behaviour it must show. It is **not** cross-validated against an external
    reference implementation, so its estimates carry that caveat.

`synthetic` propagates from the inputs into every result, so a figure or report derived from test
fixtures is always identifiable as such.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from scipy import stats

from scripts.analysis.effects import Z_95, Estimate, validate_set
from scripts.common.config import PipelineError

FIXED = "fixed-effect"
RANDOM = "random-effects"
DL = "DerSimonian-Laird"
REML = "REML"
ESTIMATORS = (DL, REML)

# Egger's test is uninformative with few studies and is widely advised against below ten.
MIN_STUDIES_EGGER = 10
# A prediction interval needs at least three studies for its t multiplier (k - 2 df) to exist.
MIN_STUDIES_PREDICTION = 3
REML_MAX_ITER = 200
REML_TOL = 1e-10


@dataclass(frozen=True)
class Heterogeneity:
    q: float
    df: int
    p_value: float
    i_squared: float          # per cent
    tau_squared: float
    estimator: str

    @property
    def tau(self) -> float:
        return math.sqrt(self.tau_squared)


@dataclass(frozen=True)
class MetaResult:
    model: str
    k: int
    log_estimate: float
    se: float
    ci_low: float             # ratio scale
    ci_high: float
    z: float
    p_value: float
    weights: dict[str, float]          # study_id -> per-cent weight
    heterogeneity: Heterogeneity
    measure: str
    synthetic: bool
    prediction_low: float | None = None
    prediction_high: float | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def estimate(self) -> float:
        return math.exp(self.log_estimate)

    def summary(self) -> str:
        tag = "  [SYNTHETIC TEST DATA — NOT A RESEARCH RESULT]" if self.synthetic else ""
        h = self.heterogeneity
        line = (f"{self.measure} {self.estimate:.3f} "
                f"(95% CI {self.ci_low:.3f}–{self.ci_high:.3f}), k={self.k}, "
                f"p={self.p_value:.4f}{tag}")
        hetero = (f"  Q={h.q:.3f} (df={h.df}, p={h.p_value:.4f}), I2={h.i_squared:.1f}%, "
                  f"tau2={h.tau_squared:.4f} [{h.estimator}]")
        if self.prediction_low is not None:
            hetero += f"\n  95% prediction interval {self.prediction_low:.3f}–{self.prediction_high:.3f}"
        return f"{line}\n{hetero}"


def _inverse_variance(estimates: list[Estimate], tau_squared: float = 0.0):
    """Weights, weighted mean and its SE on the log scale."""
    weights = [1.0 / (e.variance + tau_squared) for e in estimates]
    total = sum(weights)
    if total <= 0:
        raise PipelineError("total weight is not positive; check the standard errors")
    mean = sum(w * e.log_estimate for w, e in zip(weights, estimates)) / total
    return weights, mean, math.sqrt(1.0 / total)


def cochran_q(estimates: list[Estimate]) -> tuple[float, int, float]:
    """Cochran's Q about the fixed-effect mean, its degrees of freedom and p-value."""
    weights, mean, _ = _inverse_variance(estimates)
    q = sum(w * (e.log_estimate - mean) ** 2 for w, e in zip(weights, estimates))
    df = len(estimates) - 1
    p = float(stats.chi2.sf(q, df)) if df > 0 else float("nan")
    return q, df, p


def i_squared(q: float, df: int) -> float:
    """I2 as a percentage, from Q and its degrees of freedom (Higgins & Thompson 2002).

    Truncated at zero: a Q below its degrees of freedom implies no more variation than chance,
    and a negative I2 has no interpretation.
    """
    if df <= 0 or q <= 0:
        return 0.0
    return max(0.0, (q - df) / q) * 100.0


def tau_squared_dl(estimates: list[Estimate]) -> float:
    """DerSimonian-Laird between-study variance. Truncated at zero."""
    weights, _, _ = _inverse_variance(estimates)
    q, df, _ = cochran_q(estimates)
    total = sum(weights)
    c = total - sum(w ** 2 for w in weights) / total
    if c <= 0:
        return 0.0
    return max(0.0, (q - df) / c)


def tau_squared_reml(estimates: list[Estimate]) -> tuple[float, int, bool]:
    """REML between-study variance by fixed-point iteration.

    Returns (tau_squared, iterations, converged). Starting from the DerSimonian-Laird estimate,
    the update is iterated to a fixed point; `converged` is False if the iteration limit is hit,
    and callers should report that rather than treat the value as final.
    """
    tau2 = tau_squared_dl(estimates)
    converged = False
    iterations = 0
    for iterations in range(1, REML_MAX_ITER + 1):
        weights, mean, _ = _inverse_variance(estimates, tau2)
        total = sum(weights)
        numerator = sum(
            w ** 2 * ((e.log_estimate - mean) ** 2 - e.variance + 1.0 / total)
            for w, e in zip(weights, estimates)
        )
        denominator = sum(w ** 2 for w in weights)
        updated = max(0.0, numerator / denominator)
        if abs(updated - tau2) < REML_TOL:
            tau2 = updated
            converged = True
            break
        tau2 = updated
    return tau2, iterations, converged


def pool(estimates: list[Estimate], model: str = RANDOM, estimator: str = DL,
         prediction_interval: bool = True) -> MetaResult:
    """Pool estimates under the fixed-effect or random-effects model."""
    validate_set(estimates)
    if model not in (FIXED, RANDOM):
        raise PipelineError(f"model must be {FIXED!r} or {RANDOM!r}, got {model!r}")
    if estimator not in ESTIMATORS:
        raise PipelineError(f"estimator must be one of {ESTIMATORS}, got {estimator!r}")

    notes: list[str] = []
    q, df, q_p = cochran_q(estimates)

    if model == FIXED:
        tau2, used = 0.0, "not estimated (fixed-effect model assumes none)"
        notes.append(
            "Fixed-effect model: assumes one common true effect. With real observational studies "
            "that assumption is rarely defensible; reported here for comparison only."
        )
    elif estimator == DL:
        tau2, used = tau_squared_dl(estimates), DL
    else:
        tau2, iterations, converged = tau_squared_reml(estimates)
        used = REML
        if not converged:
            notes.append(
                f"REML did not converge within {REML_MAX_ITER} iterations; tau-squared is the last "
                "iterate and must not be reported as a final estimate."
            )
        else:
            notes.append(f"REML converged in {iterations} iterations.")
        notes.append(
            "REML is self-consistency tested but not cross-validated against an external "
            "reference implementation (see docs/methods/analysis_validation.md)."
        )

    weights, mean, se = _inverse_variance(estimates, tau2)
    total = sum(weights)
    z = mean / se
    p = float(2 * stats.norm.sf(abs(z)))

    pred_low = pred_high = None
    if model == RANDOM and prediction_interval:
        if len(estimates) >= MIN_STUDIES_PREDICTION:
            t = float(stats.t.ppf(0.975, df=len(estimates) - 2))
            spread = t * math.sqrt(tau2 + se ** 2)
            pred_low, pred_high = math.exp(mean - spread), math.exp(mean + spread)
            notes.append(
                "Prediction interval assumes the true effects are normally distributed on the log "
                "scale, and uses a t multiplier with k-2 degrees of freedom; it is wide and "
                "imprecise when k is small."
            )
        else:
            notes.append(
                f"No prediction interval: it needs at least {MIN_STUDIES_PREDICTION} studies."
            )

    return MetaResult(
        model=model, k=len(estimates), log_estimate=mean, se=se,
        ci_low=math.exp(mean - Z_95 * se), ci_high=math.exp(mean + Z_95 * se),
        z=z, p_value=p,
        weights={e.study_id: 100.0 * w / total for e, w in zip(estimates, weights)},
        heterogeneity=Heterogeneity(q, df, q_p, i_squared(q, df), tau2, used),
        measure=estimates[0].measure,
        synthetic=any(e.synthetic for e in estimates),
        prediction_low=pred_low, prediction_high=pred_high, notes=notes,
    )


@dataclass(frozen=True)
class LeaveOneOut:
    omitted: str
    result: MetaResult


def leave_one_out(estimates: list[Estimate], **kwargs) -> list[LeaveOneOut]:
    """Re-pool with each study omitted in turn, to show how far any one study drives the result."""
    if len(estimates) < 3:
        raise PipelineError(
            "leave-one-out needs at least 3 studies; with 2 each re-analysis is a single study."
        )
    return [LeaveOneOut(e.study_id, pool([x for x in estimates if x is not e], **kwargs))
            for e in estimates]


@dataclass(frozen=True)
class EggerResult:
    intercept: float
    se: float
    t: float
    p_value: float
    df: int
    k: int
    synthetic: bool

    def summary(self) -> str:
        tag = "  [SYNTHETIC TEST DATA]" if self.synthetic else ""
        return (f"Egger intercept {self.intercept:.3f} (SE {self.se:.3f}), "
                f"t={self.t:.3f}, df={self.df}, p={self.p_value:.4f}, k={self.k}{tag}")


def eggers_test(estimates: list[Estimate], *, force: bool = False) -> EggerResult:
    """Egger's regression test for small-study effects.

    Refuses below ten studies unless explicitly forced, because the test has very low power there
    and a non-significant result would be uninformative rather than reassuring. `force` exists for
    testing, and a forced result should not be reported.
    """
    validate_set(estimates)
    k = len(estimates)
    if k < MIN_STUDIES_EGGER and not force:
        raise PipelineError(
            f"Egger's test with k={k}: refused. Below {MIN_STUDIES_EGGER} studies the test has "
            "very low power and its result is uninformative; state this as a limitation instead "
            "of running it."
        )
    # Standard normal deviate regressed on precision; the intercept tests for asymmetry.
    snd = [e.log_estimate / e.se for e in estimates]
    precision = [1.0 / e.se for e in estimates]
    fit = stats.linregress(precision, snd)
    df = k - 2
    if not math.isfinite(fit.intercept_stderr) or fit.intercept_stderr == 0:
        raise PipelineError(
            "Egger's regression is degenerate: the points lie exactly on a line, so there is no "
            "residual variance and the test statistic is undefined. This happens when every "
            "estimate is identical; report the absence of asymmetry descriptively instead."
        )
    t = fit.intercept / fit.intercept_stderr
    return EggerResult(
        intercept=float(fit.intercept), se=float(fit.intercept_stderr), t=float(t),
        p_value=float(2 * stats.t.sf(abs(t), df)), df=df, k=k,
        synthetic=any(e.synthetic for e in estimates),
    )
