"""Run the meta-analysis over the extracted study data.

    python -m scripts.analysis.run_analysis

Reads `data/extraction/estimates.csv`. **No such file exists yet**, and until it does this command
refuses to run: there is nothing to pool, and producing a number from anything else would be
fabrication.

The gate is deliberate. The analysis functions in `meta.py` are tested and ready, but a pooled
estimate is a research finding, and a finding requires studies that a human reviewer has screened,
included and extracted with a source location for every value.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from scripts.analysis import effects, meta, plots
from scripts.common.config import ROOT, PipelineError

ESTIMATES_FILE = ROOT / "data" / "extraction" / "estimates.csv"
FIGURES_DIR = ROOT / "results" / "figures"
OUTPUT_DIR = ROOT / "results" / "statistical_outputs"

REQUIRED_COLUMNS = ("study_id", "measure", "estimate", "ci_low", "ci_high", "source_location")


def load_estimates(path: Path) -> list[effects.Estimate]:
    """Load extracted estimates. Every row needs a source location; nothing is defaulted."""
    if not path.exists():
        shown = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path
        raise PipelineError(
            f"{shown} does not exist, so there is nothing to pool.\n"
            "  A pooled estimate requires studies that have been screened, included at full text "
            "and extracted, with a page/table/figure location for every value.\n"
            "  Current state: see results/validation/prisma_counts.md. No study has been included "
            "yet, so no pooled estimate can legitimately be produced."
        )
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise PipelineError(f"{path.name} is empty")

    missing = [c for c in REQUIRED_COLUMNS if c not in rows[0]]
    if missing:
        raise PipelineError(f"{path.name} is missing required column(s): {', '.join(missing)}")

    out = []
    for n, row in enumerate(rows, start=2):
        if (row.get("synthetic") or "").strip().lower() in ("yes", "true", "1"):
            raise PipelineError(
                f"{path.name} line {n} is marked synthetic. Synthetic data may not enter an "
                "analysis that writes to results/; fixtures belong in the test suite only."
            )
        try:
            out.append(effects.from_ci(
                study_id=row["study_id"], estimate=float(row["estimate"]),
                ci_low=float(row["ci_low"]), ci_high=float(row["ci_high"]),
                measure=row["measure"], source_location=row["source_location"],
                notes=row.get("notes", "")))
        except (ValueError, KeyError) as exc:
            raise PipelineError(f"{path.name} line {n}: {exc}") from exc
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--estimator", default=meta.DL, choices=list(meta.ESTIMATORS))
    ap.add_argument("--no-plots", action="store_true")
    args = ap.parse_args(argv)

    try:
        estimates = load_estimates(ESTIMATES_FILE)
        random = meta.pool(estimates, model=meta.RANDOM, estimator=args.estimator)
        fixed = meta.pool(estimates, model=meta.FIXED)
    except PipelineError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [f"Random-effects:\n{random.summary()}", "", f"Fixed-effect:\n{fixed.summary()}", ""]
    for note in random.notes:
        lines.append(f"note: {note}")

    if len(estimates) >= 3:
        lines += ["", "Leave-one-out (random-effects):"]
        for loo in meta.leave_one_out(estimates, model=meta.RANDOM, estimator=args.estimator):
            lines.append(f"  omitting {loo.omitted}: {loo.result.estimate:.3f} "
                         f"({loo.result.ci_low:.3f}–{loo.result.ci_high:.3f})")
    if len(estimates) >= meta.MIN_STUDIES_EGGER:
        lines += ["", meta.eggers_test(estimates).summary()]
    else:
        lines += ["", f"Egger's test not run: k={len(estimates)} is below "
                      f"{meta.MIN_STUDIES_EGGER}; reported as a limitation."]

    report = OUTPUT_DIR / "meta_analysis.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

    if not args.no_plots:
        plots.forest_plot(estimates, random, FIGURES_DIR / "forest.png")
        plots.funnel_plot(estimates, random, FIGURES_DIR / "funnel.png")
        print(f"\nfigures -> {FIGURES_DIR.relative_to(ROOT).as_posix()}/")
    print(f"report  -> {report.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
