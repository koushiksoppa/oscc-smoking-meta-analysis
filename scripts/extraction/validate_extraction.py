"""Validate the extraction tables before anything is synthesised.

    python -m scripts.extraction.validate_extraction

Errors block synthesis. Warnings are reported for the reviewer to resolve or accept.

The arithmetic checks exist because a transcription slip in an extracted number is invisible
downstream: a pooled estimate computed from a mistyped CI looks exactly like a pooled estimate
computed from a correct one.
"""
from __future__ import annotations

import argparse
import math
import sys
from collections import Counter
from dataclasses import dataclass, field

from scripts.common.config import VALIDATION_DIR, PipelineError
from scripts.extraction import template
from scripts.extraction.schema import ESTIMATES, STUDIES, Schema, load_schema
from scripts.screening import worksheet


@dataclass
class Findings:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)


def _blank(value: str | None) -> bool:
    return not (value or "").strip()


def _number(row: dict, col: str) -> float | None:
    raw = (row.get(col) or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return math.nan


def check_enums(rows: list[dict], table_name: str, sch: Schema, f: Findings) -> None:
    spec = sch.table(table_name)
    for row in rows:
        rid = row.get("study_id") or row.get("estimate_id") or "?"
        for fld in spec.fields:
            if fld.type != "enum":
                continue
            value = (row.get(fld.name) or "").strip()
            if not value or value in sch.missing_codes:
                continue
            if value not in fld.values:
                message = (f"{rid}: {fld.name}={value!r} is not one of {list(fld.values)}")
                if fld.is_unresolved:
                    f.warnings.append(
                        f"{message}. This field depends on {fld.depends_on}, which is unresolved, "
                        "so the value is recorded but not yet protocol-conformant."
                    )
                else:
                    f.errors.append(message)
            elif fld.is_unresolved:
                f.info.append(
                    f"{rid}: {fld.name}={value!r} recorded, pending {fld.depends_on}")


def check_studies(rows: list[dict], sch: Schema, f: Findings) -> None:
    spec = sch.table(STUDIES)
    ids = [r.get("study_id", "") for r in rows]
    dupes = sorted({i for i in ids if i and ids.count(i) > 1})
    if dupes:
        f.errors.append(
            f"duplicate study_id: {', '.join(dupes)}. The study is the unit of analysis (D004)")

    threshold = sch.thresholds.get("min_scc_proportion", 90.0)
    for row in rows:
        sid = row.get("study_id") or "?"
        for col in spec.required:
            if _blank(row.get(col)):
                f.errors.append(f"{sid}: required field {col!r} is empty")

        counts = {c: _number(row, c) for c in ("n_total", "n_cases", "n_controls")}
        for col, value in counts.items():
            if value is None:
                continue
            if math.isnan(value):
                f.errors.append(f"{sid}: {col} is not a number ({row[col]!r})")
            elif value < 0:
                f.errors.append(f"{sid}: {col}={value:g} cannot be negative")
            elif value != int(value):
                f.errors.append(f"{sid}: {col}={value:g} must be a whole number of people")

        total, cases, controls = counts["n_total"], counts["n_cases"], counts["n_controls"]
        usable = lambda v: v is not None and not math.isnan(v)        # noqa: E731
        if usable(total) and usable(cases) and cases > total:
            f.errors.append(f"{sid}: n_cases ({cases:g}) exceeds n_total ({total:g})")
        if usable(total) and usable(controls) and controls > total:
            f.errors.append(f"{sid}: n_controls ({controls:g}) exceeds n_total ({total:g})")
        if usable(total) and usable(cases) and usable(controls) and cases + controls > total:
            f.errors.append(
                f"{sid}: n_cases + n_controls ({cases + controls:g}) exceeds n_total ({total:g})")

        scc = _number(row, "scc_proportion")
        if scc is not None and not math.isnan(scc):
            if not 0 <= scc <= 100:
                f.errors.append(f"{sid}: scc_proportion={scc:g} is not a percentage")
            elif scc < threshold and (row.get("histology_confirmed") or "").strip() != "all":
                f.errors.append(
                    f"{sid}: scc_proportion={scc:g}% is below the {threshold:g}% required by D008 "
                    "and histology_confirmed is not 'all' — this study does not meet the outcome "
                    "definition. Record the exclusion rather than extracting it."
                )

        if (row.get("site_separable") or "").strip() == "no":
            f.warnings.append(
                f"{sid}: site_separable='no' — D008 makes a pooled-site estimate ineligible "
                "unless an oral-cavity-specific estimate is reported")


def check_estimates(rows: list[dict], study_ids: set[str], sch: Schema, f: Findings) -> None:
    spec = sch.table(ESTIMATES)
    ci_tol = sch.thresholds.get("ci_asymmetry_warning", 0.10)
    or_tol = sch.thresholds.get("implied_or_warning", 0.20)

    ids = [r.get("estimate_id", "") for r in rows]
    dupes = sorted({i for i in ids if i and ids.count(i) > 1})
    if dupes:
        f.errors.append(f"duplicate estimate_id: {', '.join(dupes)}")

    for row in rows:
        eid = row.get("estimate_id") or "?"
        for col in spec.required:
            if _blank(row.get(col)):
                f.errors.append(f"{eid}: required field {col!r} is empty")

        sid = (row.get("study_id") or "").strip()
        if sid and study_ids and sid not in study_ids:
            f.errors.append(f"{eid}: study_id {sid!r} is not in the studies table")

        est, low, high = (_number(row, c) for c in ("estimate", "ci_low", "ci_high"))
        values = {"estimate": est, "ci_low": low, "ci_high": high}
        bad = [c for c, v in values.items() if v is not None and math.isnan(v)]
        if bad:
            f.errors.append(f"{eid}: not a number: {', '.join(bad)}")
        elif all(v is not None for v in values.values()):
            for col, v in values.items():
                if v <= 0:
                    f.errors.append(f"{eid}: {col}={v:g} — a ratio measure must be positive")
            if low > 0 and high > 0 and low >= high:
                f.errors.append(f"{eid}: ci_low ({low:g}) is not below ci_high ({high:g})")
            elif est > 0 and low > 0 and high > 0:
                if not low <= est <= high:
                    f.errors.append(
                        f"{eid}: the estimate {est:g} lies outside its own CI ({low:g}, {high:g})")
                else:
                    gap = abs(math.sqrt(low * high) / est - 1.0)
                    if gap > ci_tol:
                        f.warnings.append(
                            f"{eid}: the estimate {est:g} differs by {gap:.0%} from the geometric "
                            f"mean of its CI ({math.sqrt(low * high):.3g}); check the source")

        if (row.get("adjustment") or "").strip() == "adjusted" and _blank(row.get("adjusted_for")):
            f.errors.append(f"{eid}: adjustment='adjusted' but adjusted_for is empty")
        if (row.get("adjusted_alcohol") or "").strip() == "no":
            f.warnings.append(
                f"{eid}: not adjusted for alcohol — a major confounder for oral cancer; note it "
                "for the alcohol-adjusted subgroup analysis")

        cells = {c: _number(row, c) for c in
                 ("n_exposed_cases", "n_exposed_controls",
                  "n_unexposed_cases", "n_unexposed_controls")}
        present = {c: v for c, v in cells.items() if v is not None and not math.isnan(v)}
        if present:
            for c, v in present.items():
                if v < 0 or v != int(v):
                    f.errors.append(f"{eid}: {c}={v:g} must be a non-negative whole number")
            if len(present) == 4 and all(v > 0 for v in present.values()):
                implied = ((present["n_exposed_cases"] * present["n_unexposed_controls"])
                           / (present["n_exposed_controls"] * present["n_unexposed_cases"]))
                if est and est > 0 and abs(implied / est - 1.0) > or_tol:
                    f.warnings.append(
                        f"{eid}: the 2x2 counts imply OR {implied:.3g} but the reported estimate "
                        f"is {est:g}. Expected if the reported estimate is adjusted; confirm that "
                        "is the explanation"
                    )
            elif 0 < len(present) < 4:
                f.warnings.append(
                    f"{eid}: {len(present)} of 4 cell counts given; a 2x2 check needs all four")

        verified = (row.get("verified") or "").strip()
        selected = (row.get("selected_for_analysis") or "").strip()
        if selected == "yes":
            if verified != "yes":
                f.errors.append(
                    f"{eid}: selected for analysis but verified={verified or 'empty'!r}. An "
                    "unverified value must not enter a synthesis")
            if _blank(row.get("selection_rationale")):
                f.errors.append(
                    f"{eid}: selected for analysis with no selection_rationale. Choosing among a "
                    "study's estimates is a reviewer judgement and must be recorded")

    selected_by_study = Counter(
        (r.get("study_id") or "").strip() for r in rows
        if (r.get("selected_for_analysis") or "").strip() == "yes")
    for sid, n in sorted(selected_by_study.items()):
        if n > 1:
            f.errors.append(
                f"{sid}: {n} estimates selected for analysis. At most one per study per analysis "
                "(D004), or the study is counted twice")

    f.info.append(f"estimates: {len(rows)}")
    f.info.append(f"verified: {sum(1 for r in rows if (r.get('verified') or '').strip() == 'yes')}")
    f.info.append(f"selected for analysis: {sum(selected_by_study.values())}")
    if rows and not selected_by_study:
        f.warnings.append(
            "no estimate is selected for analysis, so no synthesis can run yet")


def check(studies: list[dict], estimates: list[dict], sch: Schema) -> Findings:
    f = Findings()
    check_studies(studies, sch, f)
    check_enums(studies, STUDIES, sch, f)
    study_ids = {(r.get("study_id") or "").strip() for r in studies}
    check_estimates(estimates, study_ids, sch, f)
    check_enums(estimates, ESTIMATES, sch, f)
    f.info.insert(0, f"studies: {len(studies)}")
    for fld in sch.unresolved_fields:
        f.info.append(f"field '{fld.name}' awaits {fld.depends_on} (unresolved)")
    return f


def write_report(f: Findings) -> str:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    path = VALIDATION_DIR / "extraction_validation.md"
    status = "FAIL" if f.errors else ("INCOMPLETE" if f.warnings else "PASS")
    lines = ["# Extraction validation", "", f"**Status: {status}**", "",
             "Errors block synthesis. Every extracted value remains the reviewer's; this report "
             "checks internal consistency and completeness only.", ""]
    for title, items in (("Errors", f.errors), ("Warnings", f.warnings), ("Counts", f.info)):
        lines += [f"## {title} ({len(items)})", ""] + [f"- {x}" for x in items] + [""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path.name


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args(argv)
    try:
        sch = load_schema()
        tables = {}
        for name in (STUDIES, ESTIMATES):
            path = template.table_path(name)
            if not path.exists():
                raise PipelineError(
                    f"{path.name} not found. Create the templates with "
                    "scripts.extraction.template")
            tables[name] = worksheet.read_csv(path)
        findings = check(tables[STUDIES], tables[ESTIMATES], sch)
    except PipelineError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    report = write_report(findings)
    verdict = "FAIL" if findings.errors else ("INCOMPLETE" if findings.warnings else "PASS")
    print(f"{verdict}: {len(findings.errors)} error(s), {len(findings.warnings)} warning(s) "
          f"-> results/validation/{report}")
    return 1 if findings.errors else 0


if __name__ == "__main__":
    sys.exit(main())
