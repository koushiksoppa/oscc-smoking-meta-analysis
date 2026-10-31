"""Stage 3: generate the screening worksheets the reviewer fills in.

    python -m scripts.screening.worksheet --stage ta             # create (refuses to overwrite)
    python -m scripts.screening.worksheet --stage ta --refresh    # add new records, keep decisions
    python -m scripts.screening.worksheet --stage ft              # built from title/abstract includes

The worksheet contains **no decisions**. Every decision column is written empty and is the human
reviewer's to complete (D010). Nothing here suggests, pre-sorts or ranks records: an automated
suggestion could not satisfy a `decision` field even if one existed, and none is produced.

Existing work is never destroyed. Plain creation refuses to touch an existing file; `--refresh`
merges on `report_id`, carrying every recorded decision across and adding only records that are
new. A row that holds a decision is never dropped, even if it has left the source set — that
would silently discard the reviewer's work, so it is reported as an error instead.
"""
from __future__ import annotations

import argparse
import csv
import sys

from scripts.common.config import PROCESSED_DIR, ROOT, PipelineError
from scripts.dedup.deduplicate import verify_provenance
from scripts.screening import vocabulary
from scripts.screening.vocabulary import FT, INCLUDE, STAGE_LABEL, TA

# NOT under data/processed/, which is gitignored as regenerable. Screening decisions are human
# research work that cannot be regenerated from anything, so they must be version-controlled.
SCREENING_DIR = ROOT / "data" / "screening"

# Columns the reviewer fills in. Everything else is derived and must not be edited.
DECISION_FIELDS = ["decision", "reason_code", "reviewer", "screened_date", "notes"]
TA_DERIVED = ["report_id", "record_id", "source_id", "pmid", "doi", "pub_year", "first_author",
              "journal", "publication_types", "title", "abstract"]
FT_DERIVED = ["report_id", "record_id", "pmid", "doi", "pub_year", "first_author", "title"]
FT_RETRIEVAL = ["full_text_status", "full_text_source"]

FIELDS = {
    TA: TA_DERIVED + DECISION_FIELDS,
    FT: FT_DERIVED + FT_RETRIEVAL + DECISION_FIELDS,
}
EDITABLE = {TA: DECISION_FIELDS, FT: FT_RETRIEVAL + DECISION_FIELDS}


def worksheet_path(stage: str):
    return SCREENING_DIR / f"screening_{stage}.csv"


def read_csv(path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def has_content(row: dict[str, str], stage: str) -> bool:
    """Whether a reviewer has recorded anything in this row."""
    return any((row.get(f) or "").strip() for f in EDITABLE[stage])


def source_rows(stage: str) -> list[dict[str, str]]:
    """Build the derived part of the worksheet from upstream data, verifying provenance first."""
    index_path = PROCESSED_DIR / "dedup" / "report_index.csv"
    if not index_path.exists():
        raise PipelineError(
            f"{index_path.name} not found. Run scripts.dedup.deduplicate first; screening is "
            "built from unique reports, not raw records."
        )
    index = read_csv(index_path)
    for source_id in sorted({r["source_id"] for r in index}):
        verify_provenance(source_id)        # raw checksum + raw-to-derived consistency

    citations = {}
    for source_id in sorted({r["source_id"] for r in index}):
        path = PROCESSED_DIR / "citations" / f"{source_id}_citations.csv"
        if not path.exists():
            raise PipelineError(
                f"{path.name} not found, though {source_id} appears in report_index.csv. "
                "Re-run parse_citations and deduplicate for this source."
            )
        for row in read_csv(path):
            citations[row["record_id"]] = row

    # One row per unique report: the primary record represents the group (D004).
    primaries = [r for r in index if r["is_primary"] == "yes"]
    if stage == TA:
        rows = []
        for r in sorted(primaries, key=lambda r: r["report_id"]):
            cit = citations.get(r["record_id"], {})
            rows.append({
                "report_id": r["report_id"], "record_id": r["record_id"],
                "source_id": r["source_id"], "pmid": r["pmid"], "doi": r["doi"],
                "pub_year": r["pub_year"], "first_author": r["first_author"],
                "journal": cit.get("journal", ""),
                "publication_types": cit.get("publication_types", ""),
                "title": r["title"], "abstract": cit.get("abstract", ""),
            })
        return rows

    # Full-text stage: only reports included at title/abstract reach it.
    ta_path = worksheet_path(TA)
    if not ta_path.exists():
        raise PipelineError(
            "the title/abstract worksheet does not exist, so there are no includes to carry "
            f"forward. Create it first: --stage {TA}"
        )
    included = {r["report_id"] for r in read_csv(ta_path)
                if (r.get("decision") or "").strip() == INCLUDE}
    by_id = {r["report_id"]: r for r in primaries}
    rows = []
    for report_id in sorted(included):
        r = by_id.get(report_id, {})
        rows.append({
            "report_id": report_id, "record_id": r.get("record_id", ""), "pmid": r.get("pmid", ""),
            "doi": r.get("doi", ""), "pub_year": r.get("pub_year", ""),
            "first_author": r.get("first_author", ""), "title": r.get("title", ""),
            "full_text_status": "", "full_text_source": "",
        })
    return rows


def build(stage: str, refresh: bool = False) -> dict:
    rows = source_rows(stage)
    path = worksheet_path(stage)
    fields = FIELDS[stage]

    if path.exists() and not refresh:
        raise PipelineError(
            f"{path.name} already exists and may hold screening decisions, so it is not "
            f"overwritten. Use --refresh to add any new records while keeping every decision."
        )

    existing: dict[str, dict[str, str]] = {}
    if path.exists():
        for row in read_csv(path):
            existing[row["report_id"]] = row

    # A recorded decision must never be silently dropped.
    incoming_ids = {r["report_id"] for r in rows}
    orphaned = sorted(rid for rid, row in existing.items()
                      if rid not in incoming_ids and has_content(row, stage))
    if orphaned:
        raise PipelineError(
            f"{path.name}: these reports hold screening decisions but are no longer in the "
            f"source set: {', '.join(orphaned)}\n"
            "  Refusing to proceed: regenerating would discard recorded work. Investigate why "
            "they left the source set before refreshing."
        )

    added, carried = 0, 0
    out: list[dict[str, str]] = []
    for row in rows:
        merged = {f: "" for f in fields}
        merged.update({k: v for k, v in row.items() if k in fields})
        prior = existing.get(row["report_id"])
        if prior is None:
            added += 1
        else:
            for f in EDITABLE[stage]:
                merged[f] = prior.get(f, "")
            if has_content(prior, stage):
                carried += 1
        out.append(merged)

    SCREENING_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out)

    return {"stage": stage, "path": path, "rows": len(out), "added": added,
            "decisions_carried": carried}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", required=True, choices=[TA, FT])
    ap.add_argument("--refresh", action="store_true",
                    help="add new records while preserving every recorded decision")
    args = ap.parse_args(argv)
    try:
        vocabulary.load_vocabulary()          # fail early if the vocabulary is malformed
        result = build(args.stage, refresh=args.refresh)
    except PipelineError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"{STAGE_LABEL[result['stage']]} worksheet: {result['rows']} rows "
          f"({result['added']} new, {result['decisions_carried']} with decisions preserved)")
    print(f"  -> {result['path'].relative_to(PROCESSED_DIR.parent.parent).as_posix()}")
    print("  Decision columns are empty by design; they are the reviewer's to complete (D010).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
