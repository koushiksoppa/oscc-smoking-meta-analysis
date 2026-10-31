"""PRISMA 2020 flow counts, computed from the datasets that exist.

    python -m scripts.screening.prisma

Every number is derived from real data or printed as `<pending>`. Nothing is estimated, and a
stage that has not been done produces `<pending>` rather than a zero — zero and "not yet done"
are different claims, and conflating them would misreport the review's progress.

Consistency identities are checked and reported; a violation is an error, because the flow
diagram must reconcile.
"""
from __future__ import annotations

import csv
import sys
from collections import Counter

from scripts.common.config import PROCESSED_DIR, VALIDATION_DIR, PipelineError, load_sources
from scripts.screening import worksheet
from scripts.screening.vocabulary import EXCLUDE, FT, INCLUDE, TA, UNRESOLVED, load_vocabulary

PENDING = "<pending>"


def read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def gather() -> dict:
    """Collect every count the flow needs, marking absent stages as pending."""
    flow: dict = {"per_source": {}, "notes": []}

    cit_dir = PROCESSED_DIR / "citations"
    identified = 0
    for source in load_sources():
        if source.export_missing:
            flow["per_source"][source.source_id] = (
                f"{PENDING} — export missing; contributes no records unless recovered (D005)")
            continue
        path = cit_dir / f"{source.source_id}_citations.csv"
        if not path.exists():
            flow["per_source"][source.source_id] = f"{PENDING} — not yet parsed"
            continue
        n = len(read(path))
        flow["per_source"][source.source_id] = n
        identified += n
    flow["identified"] = identified if identified else PENDING

    index_path = PROCESSED_DIR / "dedup" / "report_index.csv"
    if index_path.exists():
        index = read(index_path)
        unique = len({r["report_id"] for r in index})
        flow["duplicates_removed"] = len(index) - unique
        flow["unique_reports"] = unique
    else:
        flow["duplicates_removed"] = flow["unique_reports"] = PENDING

    ta_path = worksheet.worksheet_path(TA)
    if ta_path.exists():
        ta = read(ta_path)
        counts = Counter((r.get("decision") or "").strip() or "unscreened" for r in ta)
        flow["ta_total"] = len(ta)
        flow["ta_screened"] = len(ta) - counts.get("unscreened", 0)
        flow["ta_excluded"] = counts.get(EXCLUDE, 0)
        flow["ta_included"] = counts.get(INCLUDE, 0)
        flow["ta_unresolved"] = counts.get(UNRESOLVED, 0)
        flow["ta_unscreened"] = counts.get("unscreened", 0)
        flow["ta_reasons"] = Counter(
            (r.get("reason_code") or "").strip() for r in ta
            if (r.get("decision") or "").strip() == EXCLUDE)
    else:
        for k in ("ta_total", "ta_screened", "ta_excluded", "ta_included", "ta_unresolved",
                  "ta_unscreened"):
            flow[k] = PENDING
        flow["ta_reasons"] = {}

    ft_path = worksheet.worksheet_path(FT)
    flow["ft_exists"] = ft_path.exists()
    if ft_path.exists():
        ft = read(ft_path)
        statuses = Counter((r.get("full_text_status") or "").strip() for r in ft)
        counts = Counter((r.get("decision") or "").strip() or "unscreened" for r in ft)
        flow["ft_sought"] = len(ft)
        flow["ft_not_retrieved"] = statuses.get("unavailable", 0)
        flow["ft_assessed"] = len(ft) - statuses.get("unavailable", 0)
        flow["ft_excluded"] = counts.get(EXCLUDE, 0)
        flow["ft_included"] = counts.get(INCLUDE, 0)
        flow["ft_unresolved"] = counts.get(UNRESOLVED, 0)
        flow["ft_reasons"] = Counter(
            (r.get("reason_code") or "").strip() for r in ft
            if (r.get("decision") or "").strip() == EXCLUDE)
    else:
        for k in ("ft_sought", "ft_not_retrieved", "ft_assessed", "ft_excluded", "ft_included",
                  "ft_unresolved"):
            flow[k] = PENDING
        flow["ft_reasons"] = {}

    # study_id is assigned by the reviewer at full text (D004); the pipeline cannot infer it.
    flow["included_studies"] = PENDING
    flow["studies_in_synthesis"] = PENDING
    flow["notes"].append(
        "Included *studies* and studies in synthesis stay pending until the reviewer assigns "
        "study_id, since several reports can describe one population (D004).")
    return flow


def consistency(flow: dict) -> list[str]:
    """Identities the flow must satisfy. Only checked where both sides are known."""
    problems = []

    def known(*keys):
        return all(isinstance(flow.get(k), int) for k in keys)

    if known("identified", "duplicates_removed", "unique_reports"):
        if flow["identified"] - flow["duplicates_removed"] != flow["unique_reports"]:
            problems.append(
                f"identified ({flow['identified']}) − duplicates removed "
                f"({flow['duplicates_removed']}) ≠ unique reports ({flow['unique_reports']})")
    if known("unique_reports", "ta_total") and flow["unique_reports"] != flow["ta_total"]:
        problems.append(
            f"unique reports ({flow['unique_reports']}) ≠ reports in the title/abstract "
            f"worksheet ({flow['ta_total']})")
    if known("ta_screened", "ta_excluded", "ta_included", "ta_unresolved"):
        if flow["ta_excluded"] + flow["ta_included"] + flow["ta_unresolved"] != flow["ta_screened"]:
            problems.append("title/abstract decisions do not sum to the number screened")
    if known("ta_included", "ft_sought") and flow["ft_sought"] > flow["ta_included"]:
        problems.append(
            f"reports sought ({flow['ft_sought']}) exceeds title/abstract includes "
            f"({flow['ta_included']})")
    if known("ft_assessed", "ft_excluded", "ft_included", "ft_unresolved"):
        if flow["ft_excluded"] + flow["ft_included"] + flow["ft_unresolved"] > flow["ft_assessed"]:
            problems.append("full-text decisions exceed the number assessed")
    if isinstance(flow.get("ft_excluded"), int) and flow["ft_excluded"] != sum(
            flow["ft_reasons"].values()):
        problems.append(
            f"full-text exclusions ({flow['ft_excluded']}) ≠ sum of reason counts "
            f"({sum(flow['ft_reasons'].values())}) — every exclusion needs exactly one reason")
    return problems


def screening_banner(flow: dict) -> str:
    """State screening progress unambiguously.

    Without this, a reader can mistake "0 reports taken forward" for a finding — that nothing was
    eligible — when it means no record has been looked at yet. The two must never be confusable.
    """
    total, screened = flow.get("ta_total"), flow.get("ta_screened")
    if not isinstance(total, int) or not isinstance(screened, int):
        return ("> **SCREENING STATUS: NOT STARTED.** No title/abstract worksheet exists. "
                "Counts below describe the search only.")
    if screened == 0:
        return (f"> **SCREENING STATUS: NOT SCREENED.** 0 of {total} reports have been screened. "
                "Every screening count below is therefore 0 because the work has not been done — "
                "**not** because nothing was eligible. No study has been judged eligible or "
                "ineligible, and no result may be inferred from this table.")
    if screened < total:
        return (f"> **SCREENING STATUS: IN PROGRESS.** {screened} of {total} reports screened, "
                f"{total - screened} awaiting. Counts below are provisional and will change.")
    return (f"> **SCREENING STATUS: TITLE/ABSTRACT COMPLETE.** All {total} reports screened. "
            "Full-text and synthesis stages may still be pending.")


def render(flow: dict, problems: list[str]) -> str:
    vocab = load_vocabulary()
    v = lambda k: flow.get(k, PENDING)  # noqa: E731
    lines = [
        "# PRISMA 2020 flow — generated counts", "",
        "Generated by `scripts/screening/prisma.py` from the datasets present. `<pending>` means "
        "**the stage has not been done**, which is not the same as zero.", "",
        f"**Reconciles: {'no — see Problems' if problems else 'yes'}**", "",
        screening_banner(flow), "",
        "## Identification", "", "| Item | Count |", "|---|---|",
    ]
    for source_id, n in flow["per_source"].items():
        lines.append(f"| Records identified — `{source_id}` | {n} |")
    lines += [
        f"| **Records identified, total** | **{v('identified')}** |",
        f"| Duplicate records removed | {v('duplicates_removed')} |",
        f"| **Unique reports** | **{v('unique_reports')}** |",
        "", "## Title/abstract screening", "", "| Item | Count |", "|---|---|",
        f"| Reports screened | {v('ta_screened')} |",
        f"| … not yet screened | {v('ta_unscreened')} |",
        f"| Reports excluded | {v('ta_excluded')} |",
        f"| Reports left unresolved | {v('ta_unresolved')} |",
        f"| **Reports taken forward** | **{v('ta_included')}** |", "",
    ]
    if flow["ta_reasons"]:
        lines += ["### Title/abstract exclusions by reason", "", "| Reason | Count |", "|---|---|"]
        lines += [f"| `{c}` | {n} |" for c, n in sorted(flow["ta_reasons"].items())]
        lines.append("")
    lines += [
        "## Full-text screening", "", "| Item | Count |", "|---|---|",
        f"| Reports sought for retrieval | {v('ft_sought')} |",
        f"| Reports not retrieved | {v('ft_not_retrieved')} |",
        f"| Reports assessed for eligibility | {v('ft_assessed')} |",
        f"| Reports excluded | {v('ft_excluded')} |",
        f"| Reports left unresolved | {v('ft_unresolved')} |",
        f"| **Reports included** | **{v('ft_included')}** |", "",
        "### Full-text exclusions by reason", "",
        "Every reason in the controlled vocabulary is listed so that a zero is visible as a zero.",
        "", "| Reason | Count |", "|---|---|",
    ]
    for code in vocab.codes(FT):
        # A stage that exists but recorded no exclusions of this kind is a real zero; a stage
        # that has not run is pending. Printing 0 for the latter would misreport progress.
        n = flow["ft_reasons"].get(code, 0) if flow["ft_exists"] else PENDING
        lines.append(f"| `{code}` | {n} |")
    lines += [
        "", "## Included", "", "| Item | Count |", "|---|---|",
        f"| Reports of included studies | {v('ft_included')} |",
        f"| **Studies included in the review** (`study_id`) | {v('included_studies')} |",
        f"| Studies included in quantitative synthesis | {v('studies_in_synthesis')} |", "",
    ]
    if problems:
        lines += ["## Problems", ""] + [f"- {p}" for p in problems] + [""]
    lines += ["## Notes", ""] + [f"- {n}" for n in flow["notes"]] + [""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    try:
        flow = gather()
    except PipelineError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    problems = consistency(flow)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    path = VALIDATION_DIR / "prisma_counts.md"
    path.write_text(render(flow, problems), encoding="utf-8")

    print(f"identified={flow['identified']}  duplicates={flow['duplicates_removed']}  "
          f"unique_reports={flow['unique_reports']}")
    print(f"ta_screened={flow['ta_screened']}  ta_included={flow['ta_included']}  "
          f"ft_included={flow['ft_included']}  studies={flow['included_studies']}")
    print(f"-> results/validation/{path.name}")
    if problems:
        print(f"RECONCILIATION FAILED ({len(problems)}):", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
