"""Forest and funnel plots, generated from a MetaResult.

Figures are never drawn by hand and never edited after generation: a plot that disagrees with the
analysis it came from is worse than no plot.

A figure built from synthetic estimates is watermarked across its face. The watermark is not
cosmetic — a stray test figure in a results folder is exactly how fabricated data reaches a
manuscript, and it must be impossible to mistake one for a finding.
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                      # headless; no display required
import matplotlib.pyplot as plt            # noqa: E402

from scripts.analysis.effects import Z_95, Estimate   # noqa: E402
from scripts.analysis.meta import MetaResult          # noqa: E402

SYNTHETIC_WATERMARK = "SYNTHETIC TEST DATA\nNOT A RESEARCH RESULT"


def _watermark(ax, result: MetaResult) -> None:
    if not result.synthetic:
        return
    ax.text(0.5, 0.5, SYNTHETIC_WATERMARK, transform=ax.transAxes,
            fontsize=20, color="crimson", alpha=0.30, ha="center", va="center",
            rotation=20, fontweight="bold", zorder=10)


def forest_plot(estimates: list[Estimate], result: MetaResult, path: Path | str, *,
                title: str | None = None) -> Path:
    """Standard forest plot: per-study estimates with CIs, weights, and the pooled diamond."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = len(estimates)
    fig, ax = plt.subplots(figsize=(8.5, 1.1 + 0.42 * n))

    rows = list(range(n, 0, -1))
    for row, e in zip(rows, estimates):
        low, high = e.ci()
        ax.plot([low, high], [row, row], color="black", linewidth=1.1, zorder=3)
        # Marker area in proportion to the study's weight, as convention expects.
        size = 20 + 180 * (result.weights.get(e.study_id, 0.0) / 100.0)
        ax.scatter([e.estimate], [row], s=size, color="#20406a", zorder=4)

    pooled_row = 0
    ax.plot([result.ci_low, result.ci_high], [pooled_row, pooled_row],
            color="crimson", linewidth=2.0, zorder=3)
    ax.scatter([result.estimate], [pooled_row], marker="D", s=90, color="crimson", zorder=4)

    ax.axvline(1.0, color="grey", linestyle="--", linewidth=0.9, zorder=1)
    ax.set_xscale("log")
    ax.set_yticks(rows + [pooled_row])
    labels = [f"{e.study_id}  ({result.weights.get(e.study_id, 0.0):.1f}%)" for e in estimates]
    ax.set_yticklabels(labels + [f"Pooled ({result.model}, k={result.k})"])
    ax.set_ylim(-0.9, n + 0.7)
    ax.set_xlabel(f"{result.measure} (log scale)")
    h = result.heterogeneity
    ax.set_title(title or (
        f"{result.measure} {result.estimate:.2f} (95% CI {result.ci_low:.2f}–{result.ci_high:.2f})"
        f"   I²={h.i_squared:.0f}%, τ²={h.tau_squared:.3f} [{h.estimator}]"
    ), fontsize=10)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    _watermark(ax, result)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def funnel_plot(estimates: list[Estimate], result: MetaResult, path: Path | str, *,
                title: str | None = None) -> Path:
    """Funnel plot of effect against precision, with pseudo-95% confidence limits.

    Asymmetry has several possible causes besides publication bias — true heterogeneity, poorer
    methods in smaller studies, chance — so the axis label and caption avoid calling it a
    publication-bias plot.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6.4, 5.6))

    ax.scatter([e.estimate for e in estimates], [e.se for e in estimates],
               s=34, color="#20406a", zorder=4)
    ax.axvline(result.estimate, color="crimson", linestyle="-", linewidth=1.2, zorder=2,
               label=f"pooled {result.measure}")

    se_max = max(e.se for e in estimates) * 1.12
    steps = [se_max * i / 60 for i in range(61)]
    ax.plot([math.exp(result.log_estimate - Z_95 * s) for s in steps], steps,
            color="grey", linestyle="--", linewidth=0.9, zorder=2)
    ax.plot([math.exp(result.log_estimate + Z_95 * s) for s in steps], steps,
            color="grey", linestyle="--", linewidth=0.9, zorder=2,
            label="pseudo-95% limits")

    ax.set_xscale("log")
    ax.set_ylim(se_max, 0)                 # most precise studies at the top, by convention
    ax.set_xlabel(f"{result.measure} (log scale)")
    ax.set_ylabel("Standard error of ln(effect)")
    ax.set_title(title or f"Funnel plot (k={result.k})", fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    _watermark(ax, result)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path
