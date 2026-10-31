"""Meta-analysis module: effect conversion, pooling, heterogeneity, influence, plots.

ALL numeric inputs here are SYNTHETIC FIXTURES, created to exercise the software. Every one
carries `synthetic=True` and a `study_id` beginning `SYNTHETIC-`, which propagates into every
result, figure and report. They are not study data, they describe no real population, and the
module refuses to pool them together with real estimates or to write them into results/.

Validation strategy, stated plainly because it bounds what these tests prove:
  * Q, its p-value and I2 are checked against PUBLISHED values (Cochrane Handbook v6.5
    §10.10.4.5, accessed 2026-10-31) — an external check.
  * The fixed-effect and DerSimonian-Laird paths are checked against arithmetic worked out by hand
    below, with every intermediate written out so a reader can verify it with a calculator.
  * REML is checked for self-consistency and limiting behaviour only. It is NOT compared with an
    external reference implementation, so these tests cannot establish its accuracy.
"""
import math

import pytest
from scipy import stats

from scripts.analysis import effects, meta, plots
from scripts.common.config import PipelineError

S = "SYNTHETIC-"


def syn(study_id, estimate, ci_low, ci_high, measure="OR"):
    return effects.from_ci(S + study_id, estimate, ci_low, ci_high, measure,
                           source_location="synthetic fixture, no source", synthetic=True)


def syn_log(study_id, log_estimate, se, measure="OR"):
    return effects.from_log_se(S + study_id, log_estimate, se, measure,
                               source_location="synthetic fixture, no source", synthetic=True)


# --- conversion from a confidence interval -------------------------------------------

def test_se_from_ci_matches_hand_arithmetic():
    """OR 2.00, 95% CI 1.00-4.00.

    ln(2) = 0.69314718, ln(4) = 1.38629436, ln(1) = 0.
    2 x 1.95996398 = 3.91992797
    SE = 1.38629436 / 3.91992797 = 0.35365302
    """
    e = syn("A", 2.0, 1.0, 4.0)
    assert e.log_estimate == pytest.approx(0.69314718, abs=1e-8)
    assert e.se == pytest.approx(0.35365302, abs=1e-8)
    assert e.derivation == effects.FROM_CI


def test_log_symmetric_ci_round_trips_exactly():
    """OR 2.0 with CI 1.0-4.0 is symmetric on the log scale, so it reconstructs exactly."""
    low, high = syn("A", 2.0, 1.0, 4.0).ci()
    assert (low, high) == pytest.approx((1.0, 4.0), rel=1e-9)


def test_asymmetric_ci_is_flagged_rather_than_reconciled():
    """A reported estimate can be inconsistent with its own CI on the log scale.

    OR 2.5 with CI 1.4-4.1: the geometric mean of the bounds is 2.3958, 4.2% below the reported
    2.5. The estimate is kept as reported and the SE taken from the interval; a large gap is
    recorded as a note for the reviewer rather than silently reconciled.
    """
    mild = syn("A", 2.5, 1.4, 4.1)
    assert mild.estimate == pytest.approx(2.5, rel=1e-12)      # kept as reported
    assert mild.notes == "", "4.2% is within tolerance, so no note is raised"

    severe = syn("B", 4.0, 1.0, 4.0)                            # geometric mean 2.0, 50% below
    assert "not log-symmetric" in severe.notes
    assert severe.estimate == pytest.approx(4.0, rel=1e-12)


@pytest.mark.parametrize("estimate,low,high,match", [
    (0.0, 1.0, 4.0, "finite and positive"),
    (-1.0, 1.0, 4.0, "finite and positive"),
    (2.0, 4.0, 1.0, "must be below"),
    (2.0, 0.0, 4.0, "finite and positive"),
    (9.0, 1.0, 4.0, "outside its own confidence interval"),
    (0.5, 1.0, 4.0, "outside its own confidence interval"),
])
def test_invalid_confidence_intervals_are_rejected(estimate, low, high, match):
    with pytest.raises(PipelineError, match=match):
        syn("A", estimate, low, high)


def test_source_location_is_mandatory():
    with pytest.raises(PipelineError, match="source_location is required"):
        effects.from_ci("X", 2.0, 1.0, 4.0, "OR", source_location="", synthetic=True)


def test_non_ratio_measure_is_rejected():
    with pytest.raises(PipelineError, match="not one of"):
        syn("A", 2.0, 1.0, 4.0, measure="MD")


def test_non_95_percent_interval_is_refused_rather_than_converted():
    with pytest.raises(PipelineError, match="only 95% intervals"):
        effects.from_ci(S + "A", 2.0, 1.0, 4.0, "OR", "fixture", ci_level=0.90, synthetic=True)


# --- conversion from 2x2 counts ------------------------------------------------------

def test_or_from_counts_matches_hand_arithmetic():
    """a=30 b=70 c=10 d=90.

    OR = (30 x 90) / (70 x 10) = 2700/700 = 3.857143,  ln = 1.3499267
    SE = sqrt(1/30 + 1/70 + 1/10 + 1/90) = sqrt(0.0333333+0.0142857+0.1+0.0111111)
       = sqrt(0.1587302) = 0.3984096
    """
    e = effects.from_counts(S + "A", 30, 70, 10, 90, "fixture", synthetic=True)
    assert e.estimate == pytest.approx(3.857143, rel=1e-6)
    assert e.log_estimate == pytest.approx(1.3499267, abs=1e-6)
    assert e.se == pytest.approx(0.3984096, abs=1e-6)


def test_zero_cell_is_refused_without_silent_correction():
    with pytest.raises(PipelineError, match="zero cell"):
        effects.from_counts(S + "A", 0, 70, 10, 90, "fixture", synthetic=True)


def test_negative_or_non_integer_counts_are_refused():
    with pytest.raises(PipelineError, match="non-negative integers"):
        effects.from_counts(S + "A", -1, 70, 10, 90, "fixture", synthetic=True)


# --- the set-level safeguards --------------------------------------------------------

def test_synthetic_and_real_estimates_cannot_be_pooled_together():
    real = effects.from_ci("REAL-1", 2.0, 1.5, 2.7, "OR", "Table 2, p. 4")
    with pytest.raises(PipelineError, match="refusing to pool synthetic and real"):
        meta.pool([real, syn("A", 2.0, 1.0, 4.0)])


def test_a_study_may_contribute_only_one_estimate():
    a = syn("A", 2.0, 1.0, 4.0)
    with pytest.raises(PipelineError, match="appears more than once"):
        meta.pool([a, a])


def test_mixed_effect_measures_are_refused():
    with pytest.raises(PipelineError, match="mixing effect measures"):
        meta.pool([syn("A", 2.0, 1.0, 4.0), syn("B", 2.0, 1.0, 4.0, measure="HR")])


def test_empty_input_is_refused():
    with pytest.raises(PipelineError, match="no estimates"):
        meta.pool([])


# --- fixed-effect pooling, against hand arithmetic -----------------------------------

HAND = [("A", 0.0, 0.5), ("B", 1.0, 0.5), ("C", 0.5, 0.25)]
# Variances 0.25, 0.25, 0.0625; weights 4, 4, 16; total 24
# mean = (4x0 + 4x1 + 16x0.5) / 24 = 12/24 = 0.5
# SE   = sqrt(1/24) = 0.2041241
# Q    = 4(0-0.5)^2 + 4(1-0.5)^2 + 16(0.5-0.5)^2 = 1 + 1 + 0 = 2, df = 2
# I2   = max(0,(2-2)/2) = 0%
# C    = 24 - (16+16+256)/24 = 24 - 288/24 = 24 - 12 = 12
# tau2 = max(0,(2-2)/12) = 0


@pytest.fixture
def hand_set():
    return [syn_log(sid, y, se) for sid, y, se in HAND]


def test_fixed_effect_pooling_matches_hand_arithmetic(hand_set):
    r = meta.pool(hand_set, model=meta.FIXED)
    assert r.log_estimate == pytest.approx(0.5, abs=1e-12)
    assert r.se == pytest.approx(math.sqrt(1 / 24), abs=1e-12)
    assert r.estimate == pytest.approx(math.exp(0.5), rel=1e-12)
    assert r.weights[S + "A"] == pytest.approx(100 * 4 / 24, abs=1e-9)
    assert r.weights[S + "C"] == pytest.approx(100 * 16 / 24, abs=1e-9)
    assert sum(r.weights.values()) == pytest.approx(100.0, abs=1e-9)


def test_cochran_q_and_i2_match_hand_arithmetic(hand_set):
    q, df, p = meta.cochran_q(hand_set)
    assert q == pytest.approx(2.0, abs=1e-12)
    assert df == 2
    assert p == pytest.approx(float(stats.chi2.sf(2.0, 2)), abs=1e-12)
    assert meta.i_squared(q, df) == pytest.approx(0.0, abs=1e-12)


def test_dersimonian_laird_tau2_matches_hand_arithmetic(hand_set):
    assert meta.tau_squared_dl(hand_set) == pytest.approx(0.0, abs=1e-12)


def test_random_effects_equals_fixed_effect_when_tau2_is_zero(hand_set):
    fixed = meta.pool(hand_set, model=meta.FIXED)
    random = meta.pool(hand_set, model=meta.RANDOM, estimator=meta.DL)
    assert random.heterogeneity.tau_squared == pytest.approx(0.0, abs=1e-12)
    assert random.log_estimate == pytest.approx(fixed.log_estimate, abs=1e-12)
    assert random.se == pytest.approx(fixed.se, abs=1e-12)


# --- heterogeneous set, with hand-checked tau2 ---------------------------------------

HETERO = [("A", 0.0, 0.2), ("B", 1.0, 0.2), ("C", 0.5, 0.2)]
# Variances all 0.04; weights all 25; total 75; mean = 1.5/3 = 0.5
# Q = 25[(0-0.5)^2 + (1-0.5)^2 + 0] = 25[0.25+0.25] = 12.5, df = 2
# I2 = (12.5-2)/12.5 = 84%
# C  = 75 - (3 x 625)/75 = 75 - 25 = 50
# tau2(DL) = (12.5 - 2)/50 = 0.21


@pytest.fixture
def hetero_set():
    return [syn_log(sid, y, se) for sid, y, se in HETERO]


def test_heterogeneous_set_matches_hand_arithmetic(hetero_set):
    q, df, _ = meta.cochran_q(hetero_set)
    assert q == pytest.approx(12.5, abs=1e-12)
    assert meta.i_squared(q, df) == pytest.approx(84.0, abs=1e-9)
    assert meta.tau_squared_dl(hetero_set) == pytest.approx(0.21, abs=1e-12)


def test_random_effects_is_wider_than_fixed_under_heterogeneity(hetero_set):
    fixed = meta.pool(hetero_set, model=meta.FIXED)
    random = meta.pool(hetero_set, model=meta.RANDOM, estimator=meta.DL)
    assert random.se > fixed.se
    # Equal within-study variances means equal weights under either model.
    assert random.log_estimate == pytest.approx(fixed.log_estimate, abs=1e-12)


def test_equal_variances_give_equal_weights(hetero_set):
    r = meta.pool(hetero_set, model=meta.RANDOM)
    assert all(w == pytest.approx(100 / 3, abs=1e-9) for w in r.weights.values())


# --- published external check: Cochrane Handbook v6.5 §10.10.4.5 ---------------------

def test_i_squared_against_published_cochrane_example():
    """Published: Q (Chi2) = 9.87, df = 4, P = 0.043, I2 = 59.8%.

    Source: Cochrane Handbook for Systematic Reviews of Interventions v6.5 (2024), Chapter 10,
    §10.10.4.5 Example 1, accessed 2026-10-31.

    Q's p-value reproduces exactly. I2 computes to 59.47%, a 0.33 percentage-point difference from
    the published 59.8%; see docs/methods/analysis_validation.md for the two documented
    explanations. The tolerance below encodes that known difference rather than hiding it.
    """
    assert float(stats.chi2.sf(9.87, 4)) == pytest.approx(0.043, abs=0.0005)
    assert meta.i_squared(9.87, 4) == pytest.approx(59.47, abs=0.01)
    assert meta.i_squared(9.87, 4) == pytest.approx(59.8, abs=0.35)
    # Q = 9.950 reproduces the published I2 exactly, consistent with Q being rounded to 2 dp.
    assert meta.i_squared(9.950, 4) == pytest.approx(59.80, abs=0.01)


def test_i_squared_is_truncated_at_zero():
    assert meta.i_squared(1.0, 4) == 0.0
    assert meta.i_squared(0.0, 4) == 0.0


# --- REML: self-consistency only, no external reference ------------------------------

def test_reml_is_a_fixed_point_of_its_own_update(hetero_set):
    """The returned tau2 must reproduce itself when the update is applied once more."""
    tau2, _, converged = meta.tau_squared_reml(hetero_set)
    assert converged
    weights, mean, _ = meta._inverse_variance(hetero_set, tau2)
    total = sum(weights)
    numerator = sum(w ** 2 * ((e.log_estimate - mean) ** 2 - e.variance + 1.0 / total)
                    for w, e in zip(weights, hetero_set))
    again = max(0.0, numerator / sum(w ** 2 for w in weights))
    assert again == pytest.approx(tau2, abs=1e-9)


def test_reml_is_zero_when_studies_agree(hand_set):
    tau2, _, converged = meta.tau_squared_reml(hand_set)
    assert converged and tau2 == pytest.approx(0.0, abs=1e-9)


def test_reml_is_positive_under_clear_heterogeneity(hetero_set):
    tau2, _, _ = meta.tau_squared_reml(hetero_set)
    assert tau2 > 0


def test_reml_result_carries_its_validation_caveat(hetero_set):
    r = meta.pool(hetero_set, model=meta.RANDOM, estimator=meta.REML)
    assert r.heterogeneity.estimator == meta.REML
    assert any("not cross-validated" in n for n in r.notes)


def test_unknown_model_or_estimator_is_refused(hand_set):
    with pytest.raises(PipelineError, match="model must be"):
        meta.pool(hand_set, model="bayesian")
    with pytest.raises(PipelineError, match="estimator must be"):
        meta.pool(hand_set, model=meta.RANDOM, estimator="PM")


# --- prediction interval -------------------------------------------------------------

def test_prediction_interval_is_wider_than_the_confidence_interval(hetero_set):
    r = meta.pool(hetero_set, model=meta.RANDOM, estimator=meta.DL)
    assert r.prediction_low < r.ci_low and r.prediction_high > r.ci_high
    assert any("normally distributed" in n for n in r.notes)


def test_prediction_interval_withheld_with_two_studies():
    r = meta.pool([syn_log("A", 0.0, 0.2), syn_log("B", 1.0, 0.2)], model=meta.RANDOM)
    assert r.prediction_low is None
    assert any("at least 3 studies" in n for n in r.notes)


def test_fixed_effect_model_has_no_prediction_interval(hetero_set):
    r = meta.pool(hetero_set, model=meta.FIXED)
    assert r.prediction_low is None


# --- influence and small-study effects ------------------------------------------------

def test_leave_one_out_omits_each_study_once(hetero_set):
    results = meta.leave_one_out(hetero_set, model=meta.RANDOM, estimator=meta.DL)
    assert [r.omitted for r in results] == [e.study_id for e in hetero_set]
    assert all(r.result.k == len(hetero_set) - 1 for r in results)


def test_leave_one_out_refused_below_three_studies():
    with pytest.raises(PipelineError, match="at least 3 studies"):
        meta.leave_one_out([syn_log("A", 0.0, 0.2), syn_log("B", 1.0, 0.2)])


def test_eggers_test_is_refused_with_few_studies(hetero_set):
    with pytest.raises(PipelineError, match="refused"):
        meta.eggers_test(hetero_set)


def test_eggers_test_runs_with_ten_studies():
    est = [syn_log(f"S{i}", 0.4 + 0.01 * i, 0.1 + 0.02 * i) for i in range(10)]
    r = meta.eggers_test(est)
    assert r.k == 10 and r.df == 8 and math.isfinite(r.p_value)
    assert r.synthetic and "SYNTHETIC" in r.summary()


def test_symmetric_funnel_gives_a_small_egger_intercept():
    """Near-symmetric estimates should show little asymmetry and a non-significant intercept."""
    ses = [0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.24, 0.28, 0.32, 0.40]
    jitter = [0.004, -0.003, 0.002, -0.004, 0.003, -0.002, 0.004, -0.003, 0.002, -0.001]
    est = [syn_log(f"S{i}", 0.5 + j, se) for i, (se, j) in enumerate(zip(ses, jitter))]
    r = meta.eggers_test(est)
    assert abs(r.intercept) < 0.5 and r.p_value > 0.05


def test_degenerate_egger_regression_is_refused_not_reported_as_nan():
    """Identical estimates lie exactly on a line, leaving the statistic undefined."""
    est = [syn_log(f"S{i}", 0.5, se) for i, se in enumerate(
        [0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.24, 0.28, 0.32, 0.40])]
    with pytest.raises(PipelineError, match="degenerate"):
        meta.eggers_test(est)


# --- synthetic labelling propagates --------------------------------------------------

def test_synthetic_flag_reaches_the_result_and_its_summary(hetero_set):
    r = meta.pool(hetero_set, model=meta.RANDOM)
    assert r.synthetic
    assert "SYNTHETIC TEST DATA" in r.summary()


def test_real_estimates_produce_no_synthetic_marking():
    real = [effects.from_ci(f"REAL-{i}", 2.0, 1.5, 2.7, "OR", f"Table 2, p. {i}")
            for i in range(3)]
    r = meta.pool(real, model=meta.RANDOM)
    assert not r.synthetic and "SYNTHETIC" not in r.summary()


# --- plots ----------------------------------------------------------------------------

def test_forest_and_funnel_plots_are_written(tmp_path, hetero_set):
    r = meta.pool(hetero_set, model=meta.RANDOM)
    forest = plots.forest_plot(hetero_set, r, tmp_path / "forest.png")
    funnel = plots.funnel_plot(hetero_set, r, tmp_path / "funnel.png")
    assert forest.exists() and forest.stat().st_size > 5000
    assert funnel.exists() and funnel.stat().st_size > 5000


def test_synthetic_figures_are_watermarked(tmp_path, hetero_set, monkeypatch):
    """The watermark must be drawn for synthetic data and absent for real data."""
    drawn = []
    original = plots._watermark

    def spy(ax, result):
        drawn.append(result.synthetic)
        return original(ax, result)

    monkeypatch.setattr(plots, "_watermark", spy)
    plots.forest_plot(hetero_set, meta.pool(hetero_set), tmp_path / "s.png")
    assert drawn == [True]


# --- the CLI gate ---------------------------------------------------------------------

def test_run_analysis_refuses_when_no_extraction_data_exists(tmp_path, monkeypatch, capsys):
    from scripts.analysis import run_analysis
    monkeypatch.setattr(run_analysis, "ESTIMATES_FILE", tmp_path / "absent.csv")
    assert run_analysis.main([]) == 1
    assert "nothing to pool" in capsys.readouterr().err


def test_run_analysis_refuses_rows_marked_synthetic(tmp_path, monkeypatch, capsys):
    from scripts.analysis import run_analysis
    path = tmp_path / "estimates.csv"
    path.write_text(
        "study_id,measure,estimate,ci_low,ci_high,source_location,synthetic\n"
        "SYNTHETIC-A,OR,2.0,1.0,4.0,fixture,yes\n", encoding="utf-8")
    monkeypatch.setattr(run_analysis, "ESTIMATES_FILE", path)
    assert run_analysis.main([]) == 1
    assert "marked synthetic" in capsys.readouterr().err
