"""Stage 3 validation: the screening record must be internally consistent and complete.

    python -m scripts.screening.validate_screening --stage ta
    python -m scripts.screening.validate_screening --stage ft

ERROR (exit 1): unknown decision; an exclusion with no reason; a reason not permitted at this
                stage; a reason on an include; a decision with no reviewer; `other` with no
                justification; duplicate report_id; the record set altered since generation; a
                derived column edited; a retrieval status used as an exclusion reason.
WARNING:        records still unscreened; records left `unresolved`; full texts retrieved but
                not yet screened.

The record set and derived columns are re-checked against the upstream data because these files
are intended to be opened in a spreadsheet, where a mis-set import can silently truncate
abstracts, drop rows or reformat identifiers.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass, field

from scripts.common.config import VALIDATION_DIR, PipelineError
from scripts.screening import vocabulary, worksheet
from scripts.screening.vocabulary import (EXCLUDE, FT, INCLUDE, STAGE_LABEL, TA, UNRESOLVED,
                                          load_vocabulary)


@dataclass
class Findings:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)


def check(rows: list[dict[str, str]], source: list[dict[str, str]], stage: str) -> Findings:
    f = Findings()
    vocab = load_vocabulary()
    permitted = set(vocab.codes(stage))

    ids = [r.get("report_id", "") for r in rows]
    dupes = [i for i, n in Counter(ids).items() if n > 1]
    if dupes:
        f.errors.append(f"duplicate report_id in the worksheet: {', '.join(sorted(dupes))}")

    # The worksheet must still describe the same reports as the upstream data.
    expected = {r["report_id"] for r in source}
    present = set(ids)
    if present != expected:
        missing, extra = sorted(expected - present), sorted(present - expected)
        if missing:
            f.errors.append(
                f"{len(missing)} report(s) missing from the worksheet: {', '.join(missing[:10])}"
                f"{' …' if len(missing) > 10 else ''}. Rows must not be deleted"
            )
        if extra:
            f.errors.append(
                f"{len(extra)} report(s) in the worksheet are not in the source set: "
                f"{', '.join(extra[:10])}{' …' if len(extra) > 10 else ''}"
            )

    # Derived columns are not the reviewer's to edit; a mismatch usually means spreadsheet damage.
    by_id = {r["report_id"]: r for r in source}
    for r in rows:
        ref = by_id.get(r.get("report_id", ""))
        if not ref:
            continue
        for col in ("pmid", "title"):
            if col in r and col in ref and (r[col] or "").strip() != (ref[col] or "").strip():
                f.errors.append(
                    f"{r['report_id']}: derived column '{col}' differs from the source data — "
                    "the worksheet may have been altered or re-imported incorrectly"
                )

    for r in rows:
        rid = r.get("report_id", "?")
        decision = (r.get("decision") or "").strip()
        reason = (r.get("reason_code") or "").strip()
        reviewer = (r.get("reviewer") or "").strip()
        notes = (r.get("notes") or "").strip()

        if decision and decision not in vocab.decisions:
            f.errors.append(f"{rid}: unknown decision {decision!r}; allowed: {list(vocab.decisions)}")
            continue
        if decision and not reviewer:
            f.errors.append(f"{rid}: decision {decision!r} recorded with no reviewer")

        if decision == EXCLUDE:
            if not reason:
                f.errors.append(f"{rid}: excluded with no reason_code — every exclusion needs one")
            elif reason in vocab.retrieval_statuses or reason == "full_text_unavailable":
                f.errors.append(
                    f"{rid}: {reason!r} is a retrieval status, not an exclusion reason; record it "
                    "in full_text_status so the PRISMA flow reports it as 'not retrieved'"
                )
            elif vocab.reason(reason) is None:
                f.errors.append(f"{rid}: unknown reason_code {reason!r}")
            elif reason not in permitted:
                f.errors.append(
                    f"{rid}: reason {reason!r} is not permitted at {STAGE_LABEL[stage]} — it "
                    "cannot be judged from the information available at this stage. Record "
                    "'unresolved' and decide at full text"
                )
            else:
                spec = vocab.reason(reason)
                if spec.requires_note and not notes:
                    f.errors.append(f"{rid}: reason {reason!r} requires a written justification in notes")
        elif reason:
            f.errors.append(
                f"{rid}: reason_code {reason!r} recorded but decision is "
                f"{decision or 'empty'!r}; reasons belong only to exclusions"
            )

        if stage == FT:
            status = (r.get("full_text_status") or "").strip()
            if status and status not in vocab.retrieval_statuses:
                f.errors.append(
                    f"{rid}: unknown full_text_status {status!r}; allowed: "
                    f"{list(vocab.retrieval_statuses)}"
                )
            if status == "unavailable" and decision:
                f.errors.append(
                    f"{rid}: full text unavailable, so no eligibility decision can be made; it is "
                    "reported as 'not retrieved', not as an exclusion"
                )
            if status == "retrieved" and not decision:
                f.warnings.append(f"{rid}: full text retrieved but not yet screened")

    counts = Counter((r.get("decision") or "").strip() or "unscreened" for r in rows)
    if counts.get("unscreened"):
        f.warnings.append(f"{counts['unscreened']} of {len(rows)} report(s) not yet screened")
    if counts.get(UNRESOLVED):
        f.warnings.append(
            f"{counts[UNRESOLVED]} report(s) left 'unresolved' — these are not decisions and must "
            "be settled before the PRISMA flow is final"
        )

    f.info.append(f"reports in worksheet: {len(rows)}")
    for key in (INCLUDE, EXCLUDE, UNRESOLVED, "unscreened"):
        f.info.append(f"{key}: {counts.get(key, 0)}")
    reasons = Counter((r.get("reason_code") or "").strip() for r in rows
                      if (r.get("decision") or "").strip() == EXCLUDE)
    for code, n in sorted(reasons.items()):
        f.info.append(f"  excluded — {code}: {n}")
    if stage == FT:
        statuses = Counter((r.get("full_text_status") or "").strip() or "not recorded" for r in rows)
        for status, n in sorted(statuses.items()):
            f.info.append(f"  full text {status}: {n}")
    return f


def write_report(f: Findings, stage: str) -> str:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    path = VALIDATION_DIR / f"screening_{stage}_validation.md"
    status = "FAIL" if f.errors else ("INCOMPLETE" if f.warnings else "PASS")
    lines = [f"# Screening validation — {STAGE_LABEL[stage]}", "", f"**Status: {status}**", "",
             "Decisions are the human reviewer's; this report checks their internal consistency "
             "and completeness only (D010).", ""]
    for title, items in (("Errors", f.errors), ("Warnings", f.warnings), ("Counts", f.info)):
        lines += [f"## {title} ({len(items)})", ""] + [f"- {x}" for x in items] + [""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path.name


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", required=True, choices=[TA, FT])
    args = ap.parse_args(argv)
    try:
        path = worksheet.worksheet_path(args.stage)
        if not path.exists():
            raise PipelineError(
                f"{path.name} not found. Create it with "
                f"scripts.screening.worksheet --stage {args.stage}"
            )
        rows = worksheet.read_csv(path)
        source = worksheet.source_rows(args.stage)
        findings = check(rows, source, args.stage)
    except PipelineError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    report = write_report(findings, args.stage)
    verdict = "FAIL" if findings.errors else ("INCOMPLETE" if findings.warnings else "PASS")
    print(f"{verdict}: {len(findings.errors)} error(s), {len(findings.warnings)} warning(s) "
          f"-> results/validation/{report}")
    return 1 if findings.errors else 0


if __name__ == "__main__":
    sys.exit(main())
