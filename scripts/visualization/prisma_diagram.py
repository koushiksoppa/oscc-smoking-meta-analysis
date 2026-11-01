"""Draw the PRISMA 2020 flow diagram from the counts the pipeline has computed.

    python -m scripts.visualization.prisma_diagram

Every number comes from `scripts.screening.prisma.gather()`, so the diagram and
`results/validation/prisma_counts.md` cannot disagree — a figure that contradicts its own
underlying table is worse than no figure.

Two refusals are deliberate:

  * If the flow does not reconcile, **no diagram is drawn**. A published flow diagram asserts that
    its numbers add up; rendering one that does not would launder an inconsistency into an
    authoritative-looking graphic.
  * A stage that has not been done shows **"n = pending"**, never "n = 0". Zero screened and
    not-yet-screened are different claims, and only one of them is a finding.

The box contents are built by `build_boxes()`, which takes the flow dict and returns text. That
function is pure, so the diagram's wording is tested directly rather than inferred from a PNG.
"""
from __future__ import annotations

import argparse
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch     # noqa: E402

from scripts.common.config import ROOT, PipelineError              # noqa: E402
from scripts.screening import prisma                               # noqa: E402
from scripts.screening.prisma import PENDING                       # noqa: E402
from scripts.screening.vocabulary import FT, load_vocabulary       # noqa: E402

DEFAULT_PATH = ROOT / "results" / "figures" / "prisma_flow.png"

MAIN = "main"            # the central column of the flow
SIDE = "side"            # exclusion boxes, to the right


@dataclass
class Box:
    lines: list[str]
    column: str = MAIN
    section: str = ""

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@dataclass
class Diagram:
    boxes: list[Box] = field(default_factory=list)
    banner: str = ""
    reconciles: bool = True


def count(value) -> str:
    """Format a count, keeping 'not yet done' visibly distinct from zero."""
    return f"n = {value}" if isinstance(value, int) else "n = pending"


def build_boxes(flow: dict) -> Diagram:
    """Build the diagram's text from the flow counts. Pure: no drawing, no file access."""
    vocab = load_vocabulary()
    boxes: list[Box] = []

    identified = ["Records identified from:"]
    for source_id, n in flow.get("per_source", {}).items():
        shown = n if isinstance(n, int) else "pending"
        identified.append(f"  {source_id} (n = {shown})")
    identified.append(f"Total ({count(flow.get('identified'))})")
    boxes.append(Box(identified, MAIN, "Identification"))

    boxes.append(Box(["Records removed before screening:",
                      f"  Duplicate records removed ({count(flow.get('duplicates_removed'))})"],
                     SIDE, "Identification"))

    total, screened = flow.get("ta_total"), flow.get("ta_screened")
    if isinstance(total, int) and isinstance(screened, int) and screened < total:
        # Showing only one of these would misrepresent the stage's progress.
        screened_line = f"Records screened (n = {screened} of {total})"
    else:
        screened_line = f"Records screened ({count(screened)})"
    boxes.append(Box([screened_line], MAIN, "Screening"))
    boxes.append(Box([f"Records excluded ({count(flow.get('ta_excluded'))})"], SIDE, "Screening"))

    boxes.append(Box([f"Reports sought for retrieval ({count(flow.get('ta_included'))})"],
                     MAIN, "Screening"))
    boxes.append(Box([f"Reports not retrieved ({count(flow.get('ft_not_retrieved'))})"],
                     SIDE, "Screening"))

    boxes.append(Box([f"Reports assessed for eligibility ({count(flow.get('ft_assessed'))})"],
                     MAIN, "Screening"))

    excluded = [f"Reports excluded ({count(flow.get('ft_excluded'))}):"]
    reasons = flow.get("ft_reasons") or {}
    if flow.get("ft_decided", flow.get("ft_exists")):
        shown = [(code, reasons.get(code, 0)) for code in vocab.codes(FT)]
        shown = [(c, n) for c, n in shown if n] or [("none recorded", 0)]
        excluded += [f"  {code} (n = {n})" for code, n in shown]
    else:
        excluded.append("  reasons pending")
    boxes.append(Box(excluded, SIDE, "Screening"))

    boxes.append(Box([f"Studies included in review ({count(flow.get('included_studies'))})",
                      f"Reports of included studies ({count(flow.get('ft_included'))})"],
                     MAIN, "Included"))

    return Diagram(boxes=boxes, banner=prisma.screening_banner(flow).lstrip("> "))


def banner_for_figure(banner: str, width: int = 112) -> list[str]:
    """Strip Markdown emphasis and wrap, so the banner reads as figure text rather than source."""
    return textwrap.wrap(banner.replace("**", "").strip(), width=width) or [""]


def draw(diagram: Diagram, path: Path | str = DEFAULT_PATH) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    main = [b for b in diagram.boxes if b.column == MAIN]
    side = [b for b in diagram.boxes if b.column == SIDE]
    banner_lines = banner_for_figure(diagram.banner)

    # Each row is tall enough for its busiest box, so a one-line box is not given five lines of
    # whitespace and a reason list is never clipped.
    def height(i: int) -> float:
        lines = max(len(main[i].lines), len(side[i].lines) if i < len(side) else 1)
        return 0.42 + 0.26 * lines

    heights = [height(i) for i in range(len(main))]
    gap = 0.55
    headroom = 0.75 + 0.30 * len(banner_lines)        # title + banner, clear of the first box
    total = sum(heights) + gap * (len(main) - 1) + headroom + 0.4

    fig, ax = plt.subplots(figsize=(11.0, 1.1 * total))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, total)
    ax.axis("off")

    main_x, main_w = 1.4, 4.4
    side_x, side_w = 6.2, 3.4

    def place(box: Box, x: float, w: float, y: float, h: float, fill: str, edge: str):
        ax.add_patch(FancyBboxPatch((x, y - h / 2), w, h, boxstyle="round,pad=0.04",
                                    linewidth=1.1, facecolor=fill, edgecolor=edge, zorder=3))
        ax.text(x + 0.16, y, box.text, va="center", ha="left", fontsize=8.8, zorder=4)

    centres: list[float] = []
    cursor = total - headroom
    for i, box in enumerate(main):
        y = cursor - heights[i] / 2
        centres.append(y)
        place(box, main_x, main_w, y, heights[i], "#eef2f7", "#20406a")
        cursor -= heights[i] + gap

    # Exclusion boxes sit beside the main box of the same section, in order.
    for i, box in enumerate(side):
        j = min(i, len(centres) - 1)
        place(box, side_x, side_w, centres[j], heights[j], "#f7f0ee", "#8a4a3a")
        ax.add_patch(FancyArrowPatch((main_x + main_w, centres[j]), (side_x, centres[j]),
                                     arrowstyle="-|>", mutation_scale=11,
                                     linewidth=1.0, color="#8a4a3a", zorder=2))

    for i, (upper, lower) in enumerate(zip(centres, centres[1:])):
        ax.add_patch(FancyArrowPatch((main_x + main_w / 2, upper - heights[i] / 2),
                                     (main_x + main_w / 2, lower + heights[i + 1] / 2),
                                     arrowstyle="-|>", mutation_scale=13,
                                     linewidth=1.2, color="#20406a", zorder=2))

    # Section labels down the left edge.
    seen: dict[str, list[float]] = {}
    for box, y in zip(main, centres):
        seen.setdefault(box.section, []).append(y)
    for section, ys in seen.items():
        ax.text(0.5, sum(ys) / len(ys), section, rotation=90, va="center", ha="center",
                fontsize=10, fontweight="bold", color="#20406a")

    ax.text(5.0, total - 0.30, "PRISMA 2020 flow diagram", ha="center", va="center",
            fontsize=13, fontweight="bold", color="#20406a")
    for n, line in enumerate(banner_lines):
        ax.text(5.0, total - 0.70 - 0.28 * n, line, ha="center", va="center",
                fontsize=8.4, color="crimson", style="italic")
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_PATH))
    args = ap.parse_args(argv)

    try:
        flow = prisma.gather()
    except PipelineError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    problems = prisma.consistency(flow)
    if problems:
        print("REFUSED: the flow does not reconcile, so no diagram is drawn. A flow diagram "
              "asserts that its numbers add up.", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    path = draw(build_boxes(flow), args.out)
    shown = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path
    print(f"PRISMA flow diagram -> {shown}")
    print(f"  {prisma.screening_banner(flow).lstrip('> ')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
