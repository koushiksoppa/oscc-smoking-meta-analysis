"""Display screening records in batches, for the reviewer to read.

    python -m scripts.screening.show --start 1 --size 20
    python -m scripts.screening.show --start 21 --size 20
    python -m scripts.screening.show --unscreened-only --size 20
    python -m scripts.screening.show --start 1 --size 20 --format json

**Read-only.** This module opens the worksheet for reading and never writes to it, and it never
produces, suggests or infers a screening decision. It shows what a record says and what decision
(if any) the reviewer has already recorded. Decisions are the reviewer's alone (D010).

Record order is the worksheet's order, preserved exactly, so batch N shows the same records on
every run.

`languages` is not a column of the screening worksheet, so it is joined read-only from the parsed
citation dataset. That file lives under `data/processed/`, which is gitignored as regenerable, so
on a fresh clone it may be absent; the language line then says so rather than guessing.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import textwrap

from scripts.common.config import PROCESSED_DIR, PipelineError
from scripts.screening import worksheet
from scripts.screening.vocabulary import TA

WIDTH = 96
NOT_RECORDED = "(not yet screened)"
LANGUAGE_UNAVAILABLE = "(unavailable — run parse_citations to regenerate the citation dataset)"

# Fields whose absence is worth warning about when reading a batch.
EXPECTED = ("pmid", "title", "abstract", "pub_year", "first_author", "journal")


def load_languages(directory=None) -> dict[str, str]:
    """record_id -> language tags, from the citation dataset. Empty if it is not present."""
    languages: dict[str, str] = {}
    directory = directory if directory is not None else PROCESSED_DIR / "citations"
    if not directory.is_dir():
        return languages
    for path in sorted(directory.glob("*_citations.csv")):
        with open(path, encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("record_id"):
                    languages[row["record_id"]] = (row.get("languages") or "").strip()
    return languages


def select(rows: list[dict[str, str]], start: int, size: int,
           unscreened_only: bool = False) -> tuple[list[dict[str, str]], dict]:
    """Pick a batch without reordering anything. Returns (batch, metadata)."""
    if start < 1:
        raise PipelineError(f"--start must be 1 or greater, got {start}")
    if size < 1:
        raise PipelineError(f"--size must be 1 or greater, got {size}")

    total = len(rows)
    screened = sum(1 for r in rows if (r.get("decision") or "").strip())
    pool = [r for r in rows if not (r.get("decision") or "").strip()] if unscreened_only else rows

    if pool and start > len(pool):
        raise PipelineError(
            f"--start {start} is beyond the {len(pool)} record(s) available"
            f"{' that are unscreened' if unscreened_only else ''}"
        )

    batch = pool[start - 1:start - 1 + size]
    meta = {
        "batch_number": (start - 1) // size + 1,
        "range_start": start,
        "range_end": start + len(batch) - 1 if batch else start - 1,
        "batch_size": len(batch),
        "pool_size": len(pool),
        "total_records": total,
        "screened": screened,
        "remaining": total - screened,
        "unscreened_only": unscreened_only,
    }
    return batch, meta


def warnings_for(batch: list[dict[str, str]], languages: dict[str, str]) -> list[str]:
    found = []
    for field in EXPECTED:
        missing = [r.get("report_id", "?") for r in batch if not (r.get(field) or "").strip()]
        if missing:
            found.append(f"{len(missing)} record(s) with no {field}: {', '.join(missing)}")
    if not languages:
        found.append(f"language not shown: {LANGUAGE_UNAVAILABLE}")
    else:
        absent = [r.get("report_id", "?") for r in batch
                  if not languages.get(r.get("record_id", ""), "").strip()]
        if absent:
            found.append(f"{len(absent)} record(s) with no language tag: {', '.join(absent)}")
    return found


def decision_line(row: dict[str, str]) -> str:
    decision = (row.get("decision") or "").strip()
    if not decision:
        return NOT_RECORDED
    parts = [decision]
    for field, label in (("reason_code", "reason"), ("reviewer", "by"), ("screened_date", "on")):
        value = (row.get(field) or "").strip()
        if value:
            parts.append(f"{label}: {value}")
    notes = (row.get("notes") or "").strip()
    if notes:
        parts.append(f"notes: {notes}")
    return "  |  ".join(parts)


def render_text(batch: list[dict[str, str]], meta: dict, languages: dict[str, str],
                warnings: list[str]) -> str:
    out: list[str] = []
    scope = " (unscreened only)" if meta["unscreened_only"] else ""
    out.append("=" * WIDTH)
    out.append(f"BATCH {meta['batch_number']}{scope}  |  "
               f"records {meta['range_start']}-{meta['range_end']} of {meta['pool_size']}")
    out.append(f"Dataset: {meta['total_records']} reports  |  "
               f"screened {meta['screened']}  |  remaining {meta['remaining']}")
    if warnings:
        out.append("")
        out.append("Metadata warnings:")
        out += [f"  - {w}" for w in warnings]
    out.append("=" * WIDTH)

    for row in batch:
        language = languages.get(row.get("record_id", ""), "")
        out.append("")
        out.append("-" * WIDTH)
        out.append(f"{row.get('report_id', '?')}  |  PMID {row.get('pmid') or '(none)'}  |  "
                   f"{row.get('pub_year') or '(no year)'}")
        out.append(f"  AUTHOR   : {row.get('first_author') or '(none)'}")
        out.append(f"  JOURNAL  : {row.get('journal') or '(none)'}")
        out.append(f"  TYPES    : {row.get('publication_types') or '(none)'}")
        out.append(f"  LANGUAGE : {language or (LANGUAGE_UNAVAILABLE if not languages else '(none)')}")
        if (row.get("doi") or "").strip():
            out.append(f"  DOI      : {row['doi']}")
        out.append(f"  DECISION : {decision_line(row)}")
        out.append("")
        title = (row.get("title") or "").strip() or "(no title)"
        out += ["  " + line for line in textwrap.wrap(title, WIDTH - 2)]
        out.append("")
        abstract = (row.get("abstract") or "").strip()
        if abstract:
            out += ["  " + line for line in textwrap.wrap(abstract, WIDTH - 2)]
        else:
            out.append("  (no abstract — retrieval or full text needed to screen this record)")
    out.append("")
    return "\n".join(out)


def render_json(batch: list[dict[str, str]], meta: dict, languages: dict[str, str],
                warnings: list[str]) -> str:
    payload = {
        "batch": meta,
        "warnings": warnings,
        "records": [
            {
                "report_id": row.get("report_id", ""),
                "record_id": row.get("record_id", ""),
                "pmid": row.get("pmid", ""),
                "doi": row.get("doi", ""),
                "title": row.get("title", ""),
                "first_author": row.get("first_author", ""),
                "pub_year": row.get("pub_year", ""),
                "journal": row.get("journal", ""),
                "publication_types": row.get("publication_types", ""),
                "language": languages.get(row.get("record_id", ""), ""),
                "abstract": row.get("abstract", ""),
                "decision": (row.get("decision") or "").strip(),
                "reason_code": (row.get("reason_code") or "").strip(),
                "reviewer": (row.get("reviewer") or "").strip(),
                "screened_date": (row.get("screened_date") or "").strip(),
                "notes": (row.get("notes") or "").strip(),
            }
            for row in batch
        ],
    }
    # ensure_ascii=False keeps accented author names readable; the key order is fixed above, so
    # the same input always produces byte-identical output.
    return json.dumps(payload, indent=2, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", type=int, default=1, help="1-based position in the batch pool")
    ap.add_argument("--size", type=int, default=20, help="records per batch")
    ap.add_argument("--unscreened-only", action="store_true",
                    help="show only records with no decision recorded")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args(argv)

    # Windows consoles default to a legacy code page; abstracts contain accented names and
    # mathematical symbols that would otherwise raise UnicodeEncodeError mid-batch.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        path = worksheet.worksheet_path(TA)
        if not path.exists():
            raise PipelineError(
                f"{path.name} not found. Create it with "
                "scripts.screening.worksheet --stage ta"
            )
        rows = worksheet.read_csv(path)
        if not rows:
            raise PipelineError(f"{path.name} contains no records")
        batch, meta = select(rows, args.start, args.size, args.unscreened_only)
        if not batch:
            raise PipelineError(
                "no records to show"
                + (" — every record already has a decision recorded"
                   if args.unscreened_only else "")
            )
    except PipelineError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    languages = load_languages()
    warns = warnings_for(batch, languages)
    render = render_json if args.format == "json" else render_text
    print(render(batch, meta, languages, warns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
