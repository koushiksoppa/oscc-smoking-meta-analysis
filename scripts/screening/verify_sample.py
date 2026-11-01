"""Blinded verification of a random sample of recorded title/abstract decisions.

    python -m scripts.screening.verify_sample --draw     # write the blinded sheet
    python -m scripts.screening.verify_sample --score    # unblind and report agreement

The recorded decisions were entered by adopting a suggestion set generated from the titles and
abstracts. A check of those decisions by whoever produced the suggestions would be circular, so
this module hands the reviewer a sample of records **without** the recorded decision and compares
the reviewer's independent judgement afterwards.

Everything is fixed before the sample is drawn, so the exercise cannot be post-hoc:

* **Sample size** — 40 of 194 (20.6%), simple random without replacement.
* **Seed** — the first 8 hex digits of the SHA-256 of the committed worksheet. Nobody chooses it,
  and anyone can reproduce the draw from the file itself.
* **Acceptance rule** — >= 95% agreement adopts the unsampled remainder; 90-94.9% draws a second
  sample of the same size and re-applies the rule to the combined set; < 90% discards the
  suggestion set as a decision source and requires a full manual re-screen.
* **Asymmetry rule** — any record the reviewer would *include* that was recorded as *exclude*
  triggers a sweep of every record excluded under that same reason code, whatever the headline
  rate. Erroneous exclusion loses evidence irrecoverably; the opposite direction only costs
  retrieval effort, so it is recorded but triggers nothing.

The module never writes to `screening_ta.csv` and never changes a recorded decision.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import random
import sys
from collections import Counter

from scripts.common.config import VALIDATION_DIR, PipelineError
from scripts.screening import worksheet
from scripts.screening.show import load_languages
from scripts.screening.vocabulary import EXCLUDE, INCLUDE, TA, load_vocabulary

SAMPLE_SIZE = 40
ADOPT_AT = 0.95
EXTEND_AT = 0.90

SHOWN = ["report_id", "pmid", "doi", "pub_year", "first_author", "journal",
         "publication_types", "language", "title", "abstract"]
RESPONSE = ["your_decision", "your_reason_code", "your_notes"]
SHEET_FIELDS = SHOWN + RESPONSE


def sheet_path():
    return worksheet.SCREENING_DIR / "verification_sample.csv"


def digest(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seed_from(digest_hex: str) -> int:
    """The seed is derived from the data, so the draw is auditable and unchosen."""
    return int(digest_hex[:8], 16)


def draw(rows: list[dict], size: int, seed: int) -> list[dict]:
    """A reproducible simple random sample, returned in worksheet order for readability."""
    if size < 1:
        raise PipelineError(f"sample size must be 1 or greater, got {size}")
    if size > len(rows):
        raise PipelineError(f"cannot draw {size} records from {len(rows)}")
    picked = random.Random(seed).sample(range(len(rows)), size)
    return [rows[i] for i in sorted(picked)]


def build_sheet(sample: list[dict], languages: dict[str, str]) -> list[dict]:
    """The blinded instrument. Carries no decision, reason, reviewer or note from the worksheet."""
    out = []
    for row in sample:
        entry = {f: "" for f in SHEET_FIELDS}
        for f in SHOWN:
            if f == "language":
                entry[f] = languages.get(row.get("record_id", ""), "")
            else:
                entry[f] = row.get(f, "")
        out.append(entry)
    return out


def read_csv(path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa over however many categories appear. None when it is undefined.

    With no variation in either rater, expected agreement is 1 and kappa is 0/0. That is not a
    failure - raw agreement is still meaningful - so it is reported as undefined rather than
    raising or silently printing a misleading 0.
    """
    n = len(pairs)
    if not n:
        return None
    a = Counter(x for x, _ in pairs)
    b = Counter(y for _, y in pairs)
    po = sum(1 for x, y in pairs if x == y) / n
    pe = sum(a[k] * b[k] for k in set(a) | set(b)) / (n * n)
    if abs(1 - pe) < 1e-12:
        return None
    return (po - pe) / (1 - pe)


def score(sheet: list[dict], ta_rows: list[dict]) -> dict:
    """Compare the reviewer's blinded judgements with what is recorded."""
    vocab = load_vocabulary()
    recorded = {r["report_id"]: r for r in ta_rows}
    permitted = set(vocab.codes(TA))

    blank = [r["report_id"] for r in sheet if not (r.get("your_decision") or "").strip()]
    if blank:
        raise PipelineError(
            f"{len(blank)} row(s) have no your_decision: {', '.join(blank)}\n"
            "  Every sampled record needs an independent judgement before scoring."
        )

    pairs, discrepancies, reason_pairs, problems = [], [], [], []
    for r in sheet:
        rid = r["report_id"]
        if rid not in recorded:
            raise PipelineError(f"{rid} is not in the title/abstract worksheet")
        mine = (r["your_decision"] or "").strip()
        my_reason = (r.get("your_reason_code") or "").strip()
        theirs = (recorded[rid].get("decision") or "").strip()
        their_reason = (recorded[rid].get("reason_code") or "").strip()

        if mine not in vocab.decisions:
            problems.append(f"{rid}: {mine!r} is not a decision value")
            continue
        if mine == EXCLUDE and not my_reason:
            problems.append(f"{rid}: excluded with no reason code")
        elif mine == EXCLUDE and my_reason not in permitted:
            problems.append(f"{rid}: reason {my_reason!r} is not permitted at title/abstract")
        elif mine != EXCLUDE and my_reason:
            problems.append(f"{rid}: reason code recorded on a non-exclusion")

        pairs.append((theirs, mine))
        if theirs != mine:
            discrepancies.append({"report_id": rid, "recorded": theirs, "recorded_reason":
                                  their_reason, "reviewer": mine, "reviewer_reason": my_reason,
                                  "notes": (r.get("your_notes") or "").strip()})
        elif mine == EXCLUDE:
            reason_pairs.append((their_reason, my_reason, rid))

    if problems:
        raise PipelineError("the completed sheet is not internally valid:\n  "
                            + "\n  ".join(problems))

    n = len(pairs)
    agreed = sum(1 for x, y in pairs if x == y)
    rate = agreed / n if n else 0.0

    # Erroneous exclusion is the asymmetric risk: it removes evidence that no later stage can
    # recover, so one instance warrants sweeping every record excluded for the same reason.
    sweeps = sorted({d["recorded_reason"] for d in discrepancies
                     if d["recorded"] == EXCLUDE and d["reviewer"] == INCLUDE})
    sweep_sizes = {code: sum(1 for r in ta_rows
                             if (r.get("reason_code") or "").strip() == code) for code in sweeps}

    return {
        "n": n, "agreed": agreed, "rate": rate, "kappa": kappa(pairs),
        "discrepancies": discrepancies,
        "reason_agreed": sum(1 for a, b, _ in reason_pairs if a == b),
        "reason_total": len(reason_pairs),
        "reason_discrepancies": [(rid, a, b) for a, b, rid in reason_pairs if a != b],
        "verdict": verdict(rate),
        "sweeps": sweeps, "sweep_sizes": sweep_sizes,
        "population": len(ta_rows),
    }


def verdict(rate: float) -> str:
    if rate >= ADOPT_AT:
        return "ADOPT"
    if rate >= EXTEND_AT:
        return "EXTEND"
    return "RE-SCREEN"


VERDICT_TEXT = {
    "ADOPT": ("Agreement meets the pre-specified threshold. The decisions outside the sample are "
              "adopted as recorded, and this verification is reported in the methods."),
    "EXTEND": ("Agreement falls in the pre-specified middle band. A second sample of the same size "
               "is drawn and the rule re-applied to the combined set."),
    "RE-SCREEN": ("Agreement is below the pre-specified floor. The suggestion set is discarded as "
                  "a decision source and all records are re-screened manually."),
}


def render(result: dict, seed: int, worksheet_sha: str) -> str:
    k = result["kappa"]
    lines = [
        "# Title/abstract screening — blinded verification of a random sample", "",
        f"**Verdict: {result['verdict']}**", "",
        VERDICT_TEXT[result["verdict"]], "",
        "## Pre-specified before the sample was drawn", "",
        "| Parameter | Value |", "|---|---|",
        f"| Sample size | {result['n']} of {result['population']} "
        f"({result['n'] / result['population']:.1%}) |",
        "| Sampling | simple random, without replacement |",
        f"| Seed | `{seed}`, the first 8 hex digits of the worksheet SHA-256 |",
        f"| Worksheet SHA-256 | `{worksheet_sha}` |",
        "| Blinding | the recorded decision and reason were hidden from the reviewer |",
        f"| Adopt at | >= {ADOPT_AT:.0%} agreement |",
        f"| Extend at | >= {EXTEND_AT:.0%} and < {ADOPT_AT:.0%} |",
        f"| Re-screen below | {EXTEND_AT:.0%} |", "",
        "## Result", "", "| Metric | Value |", "|---|---|",
        f"| Agreement on include/exclude | **{result['agreed']} / {result['n']} "
        f"({result['rate']:.1%})** |",
        f"| Cohen's kappa | {'undefined (no variation in one or both raters)' if k is None else f'{k:.3f}'} |",
        f"| Reason-code agreement among concordant exclusions | "
        f"{result['reason_agreed']} / {result['reason_total']} |", "",
    ]

    if result["discrepancies"]:
        lines += ["## Decision discrepancies", "",
                  "| Report | Recorded | Reviewer | Direction |", "|---|---|---|---|"]
        for d in result["discrepancies"]:
            direction = ("**evidence lost if recorded stands**"
                         if d["recorded"] == EXCLUDE and d["reviewer"] == INCLUDE
                         else "retrieval effort only")
            rec = f"{d['recorded']}" + (f" (`{d['recorded_reason']}`)" if d["recorded_reason"] else "")
            rev = f"{d['reviewer']}" + (f" (`{d['reviewer_reason']}`)" if d["reviewer_reason"] else "")
            lines.append(f"| {d['report_id']} | {rec} | {rev} | {direction} |")
        lines.append("")
        for d in result["discrepancies"]:
            if d["notes"]:
                lines.append(f"- **{d['report_id']}** — {d['notes']}")
        lines.append("")
    else:
        lines += ["## Decision discrepancies", "", "None.", ""]

    if result["reason_discrepancies"]:
        lines += ["## Reason-code discrepancies among agreed exclusions", "",
                  "The decision matched; the recorded reason did not.", "",
                  "| Report | Recorded | Reviewer |", "|---|---|---|"]
        lines += [f"| {rid} | `{a}` | `{b}` |" for rid, a, b in result["reason_discrepancies"]]
        lines.append("")

    if result["sweeps"]:
        lines += ["## Asymmetry rule triggered", "",
                  "The reviewer would include a record that was excluded, so every record "
                  "excluded under the same reason is re-checked, independently of the headline "
                  "rate.", "", "| Reason code | Records to sweep |", "|---|---|"]
        lines += [f"| `{c}` | {result['sweep_sizes'][c]} |" for c in result["sweeps"]]
        lines.append("")
    else:
        lines += ["## Asymmetry rule", "",
                  "Not triggered: no record the reviewer would include was recorded as excluded.",
                  ""]

    lines += [
        "## What this measures, and what it does not", "",
        "Four things are deliberately distinguished:", "",
        "| Term | Meaning |", "|---|---|",
        "| **Automated suggestion** | A decision proposed by tooling from the title and "
        "abstract, recorded in `data/screening/ta_suggestions_<date>.csv`. Not a decision, and "
        "**not a reference standard**. |",
        "| **Human reviewer decision** | The value in `decision` in the title/abstract "
        "worksheet, entered by the reviewer. For this pass the reviewer adopted the suggestion "
        "set, so the two are identical. |",
        "| **Blinded verification sample** | A random subset re-judged by the reviewer without "
        "sight of the recorded decision. |",
        "| **Agreement** | The rate at which the reviewer's blinded judgement matched the "
        "recorded decision. |", "",
        "Because the recorded decisions are identical to the automated suggestions, the "
        "agreement reported here is **between one reviewer's blinded judgement and an "
        "automated suggestion set**. It is **not** inter-reviewer agreement, **not** "
        "independent duplicate screening by a second reviewer, and it does **not** treat the "
        "suggestions as ground truth: a discrepancy shows the two differ, not that either is "
        "correct. Report it as single-reviewer screening with an automation-assisted "
        "suggestion step and an internal blinded consistency check (D010, PRISMA 2020 item "
        "8).", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--draw", action="store_true", help="write the blinded verification sheet")
    g.add_argument("--score", action="store_true", help="unblind and report agreement")
    ap.add_argument("--size", type=int, default=SAMPLE_SIZE)
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        ta_path = worksheet.worksheet_path(TA)
        if not ta_path.exists():
            raise PipelineError(f"{ta_path.name} not found")
        ta_rows = read_csv(ta_path)
        sha = digest(ta_path)
        seed = seed_from(sha)
        path = sheet_path()

        if args.draw:
            if path.exists():
                raise PipelineError(
                    f"{path.name} already exists and may hold the reviewer's judgements, so it "
                    "is not overwritten. Move it aside first if you really mean to redraw."
                )
            sample = draw(ta_rows, args.size, seed)
            sheet = build_sheet(sample, load_languages())
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=SHEET_FIELDS)
                w.writeheader()
                w.writerows(sheet)
            print(f"drew {len(sheet)} of {len(ta_rows)} records "
                  f"({len(sheet) / len(ta_rows):.1%}) with seed {seed}")
            print(f"  worksheet SHA-256: {sha}")
            print(f"  -> {path.as_posix()}")
            print("  The recorded decision is NOT in this file. Fill your_decision, "
                  "your_reason_code and your_notes, then run --score.")
            return 0

        if not path.exists():
            raise PipelineError(f"{path.name} not found. Run --draw first.")
        result = score(read_csv(path), ta_rows)
    except PipelineError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    out = VALIDATION_DIR / "screening_verification.md"
    out.write_text(render(result, seed, sha), encoding="utf-8")
    print(f"agreement {result['agreed']}/{result['n']} ({result['rate']:.1%})  "
          f"verdict={result['verdict']}")
    if result["sweeps"]:
        print(f"  asymmetry rule triggered for: {', '.join(result['sweeps'])}", file=sys.stderr)
    print(f"  -> results/validation/{out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
