"""Generate the blank extraction tables the reviewer fills in.

    python -m scripts.extraction.template                 # create (refuses to overwrite)
    python -m scripts.extraction.template --refresh        # add new studies, keep extracted values

Rows are seeded from the reports **included at full text**, so a study cannot be extracted before
it has been judged eligible. Every data column is written empty: no value is pre-filled, inferred
or carried over from the citation metadata, because an extracted value must come from the full
text with a source location (provenance rule 4), not from a database record.

As with screening, existing work is never destroyed. Plain creation refuses to touch an existing
file, `--refresh` merges on the row key, and a row holding extracted values is never dropped.
"""
from __future__ import annotations

import argparse
import csv
import sys

from scripts.common.config import ROOT, PipelineError
from scripts.extraction import schema
from scripts.extraction.schema import ESTIMATES, STUDIES, load_schema
from scripts.screening import worksheet
from scripts.screening.vocabulary import FT, INCLUDE

# Not under data/processed/, which is gitignored as regenerable. Extracted values are human
# research work and cannot be reconstructed from anything.
EXTRACTION_DIR = ROOT / "data" / "extraction"
KEY = {STUDIES: "study_id", ESTIMATES: "estimate_id"}


def table_path(table: str):
    return EXTRACTION_DIR / f"{table}.csv"


def included_reports() -> list[dict[str, str]]:
    """Reports marked `include` at full text. Empty until the reviewer has screened."""
    path = worksheet.worksheet_path(FT)
    if not path.exists():
        raise PipelineError(
            "the full-text worksheet does not exist, so no study has been included yet.\n"
            "  Extraction is seeded from full-text includes: screen title/abstract, then full "
            "text, before extracting."
        )
    return [r for r in worksheet.read_csv(path)
            if (r.get("decision") or "").strip() == INCLUDE]


def seed_rows(table: str, reports: list[dict[str, str]]) -> list[dict[str, str]]:
    """One studies row per included report, as a starting point only.

    A report is not a study: several reports can describe one population, and only the reviewer
    can tell (D004). So `study_id` is seeded from `report_id` and the reviewer merges rows that
    turn out to share a population, recording the merge in `report_ids`.
    """
    if table == ESTIMATES:
        # Estimates cannot be seeded: how many a study reports is only known from its full text.
        return []
    return [
        {"study_id": r["report_id"], "primary_report_id": r["report_id"],
         "report_ids": r["report_id"], "pmid": r.get("pmid", ""), "doi": r.get("doi", ""),
         "first_author": r.get("first_author", ""), "pub_year": r.get("pub_year", "")}
        for r in sorted(reports, key=lambda r: r["report_id"])
    ]


def build(table: str, refresh: bool = False) -> dict:
    sch = load_schema()
    spec = sch.table(table)
    path = table_path(table)
    key = KEY[table]

    if path.exists() and not refresh:
        raise PipelineError(
            f"{path.name} already exists and may hold extracted values, so it is not overwritten. "
            "Use --refresh to add new rows while keeping everything already entered."
        )

    seeded = seed_rows(table, included_reports())
    seed_keys = {r[key] for r in seeded}

    existing: dict[str, dict[str, str]] = {}
    if path.exists():
        for row in worksheet.read_csv(path):
            existing[row.get(key, "")] = row

    # A row holding extracted values must never be silently dropped. Estimates rows are always
    # reviewer-created, so they are all carried; studies rows are matched against the seed.
    def has_content(row: dict[str, str]) -> bool:
        return any((v or "").strip() for k, v in row.items() if k != key)

    orphaned = sorted(k for k, row in existing.items()
                      if table == STUDIES and k not in seed_keys and has_content(row))
    if orphaned:
        raise PipelineError(
            f"{path.name}: these rows hold extracted values but are no longer among the full-text "
            f"includes: {', '.join(orphaned)}\n"
            "  Refusing to proceed: regenerating would discard recorded work. If a study was "
            "excluded after extraction, record that decision rather than deleting the data."
        )

    out: list[dict[str, str]] = []
    carried = added = 0
    for row in seeded:
        merged = {c: "" for c in spec.columns}
        prior = existing.get(row[key])
        if prior is None:
            merged.update({k: v for k, v in row.items() if k in merged})
            added += 1
        else:
            merged.update({k: v for k, v in prior.items() if k in merged})
            if has_content(prior):
                carried += 1
        out.append(merged)

    # Reviewer-created rows that were never seeded (all estimates rows, and any study the reviewer
    # added by hand) are preserved as they are.
    for k, prior in sorted(existing.items()):
        if k not in seed_keys:
            out.append({c: prior.get(c, "") for c in spec.columns})
            if has_content(prior):
                carried += 1

    EXTRACTION_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(spec.columns))
        writer.writeheader()
        writer.writerows(out)
    return {"table": table, "path": path, "rows": len(out), "added": added, "carried": carried}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--table", choices=list(schema.TABLES), default=None,
                    help="default: both tables")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args(argv)

    tables = [args.table] if args.table else list(schema.TABLES)
    try:
        sch = load_schema()
        results = [build(t, refresh=args.refresh) for t in tables]
    except PipelineError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    for r in results:
        print(f"{r['table']}: {r['rows']} rows ({r['added']} new, {r['carried']} with data kept)"
              f"  -> {r['path'].relative_to(ROOT).as_posix()}")
    print("  All data columns are empty by design; every value is the reviewer's to enter from the "
          "full text, with a source location.")
    for f in sch.unresolved_fields:
        print(f"  NOTE: '{f.name}' depends on {f.depends_on}, which is unresolved — record what "
              f"the study reports; the protocol meaning is still pending.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
