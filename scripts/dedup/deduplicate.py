"""Stage 2: deduplicate citation records across sources and assign report_id.

    python -m scripts.dedup.deduplicate                 # all sources with a parsed citation table
    python -m scripts.dedup.deduplicate --source pubmed_v1

Outputs:
  data/processed/dedup/report_index.csv   record_id -> report_id, primary flag, merge criterion
  data/processed/dedup/dedup_audit.csv    every candidate pair, its criterion and resolution
  results/validation/dedup_summary.md     counts before and after, for the PRISMA flow

No record is deleted (provenance rule: duplicates are mapped, not removed). Records linked only by
title similarity are reported as `needs_review` and left unmerged; the stage then exits non-zero,
because a PRISMA identification count cannot be stated while duplicate status is unresolved.
"""
from __future__ import annotations

import argparse
import csv
import sys

import json

from scripts.acquisition.verify_raw import verify
from scripts.common.config import (PROCESSED_DIR, VALIDATION_DIR, PipelineError, get_source,
                                   load_sources)
from scripts.dedup import match

INDEX_FIELDS = ["record_id", "source_id", "search_version", "pmid", "doi", "pub_year",
                "first_author", "title", "report_id", "is_primary", "duplicate_of",
                "merged_with", "merge_criterion"]
AUDIT_FIELDS = ["pair_id", "record_a", "record_b", "criterion", "matched_value", "resolution"]


def citations_path(source_id: str):
    return PROCESSED_DIR / "citations" / f"{source_id}_citations.csv"


def records_path(source_id: str):
    return PROCESSED_DIR / "citations" / f"{source_id}_records.jsonl"


def verify_provenance(source_id: str) -> str:
    """Confirm this source's parsed data still derives from its verified raw export.

    Two separate things are checked, because neither implies the other:
      1. the raw export matches its registered checksum (verify_raw's gate);
      2. the parsed data records that SAME checksum as the file it was produced from.

    Without (2), an export could be re-registered or re-parsed and the citation table left
    stale, silently feeding outdated records into the PRISMA count. Fails closed: absent or
    unreadable provenance is an error, never a reason to skip the check.
    """
    source = get_source(source_id)
    if source.export_missing:
        raise PipelineError(
            f"{source_id}: the export for this search execution is missing, so it has no records "
            "to deduplicate and cannot be parsed.\n"
            f"  It is recorded in config/sources.yaml as status 'export_missing' with its own "
            f"record count ({source.expected_records}), which stays as the documented claim for "
            "that search (D005, D011). It is not recreated and not substituted.\n"
            "  Deduplicate the executions that do have registered exports instead."
        )
    raw_sha = verify(source)["sha256"]

    path = records_path(source_id)
    if not path.exists():
        raise PipelineError(
            f"{source_id}: {path.name} not found, so the citation table's provenance cannot be "
            "checked against the raw export. Re-run parse_citations for this source."
        )
    seen: set[str] = set()
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            recorded = json.loads(line).get("raw_sha256")
        except json.JSONDecodeError as exc:
            raise PipelineError(f"{source_id}: {path.name} line {n} is not valid JSON: {exc}") from exc
        if not recorded:
            raise PipelineError(
                f"{source_id}: {path.name} line {n} records no raw_sha256, so the parsed data "
                "cannot be tied to the raw export. Missing provenance is not a pass: re-run "
                "parse_citations for this source."
            )
        seen.add(recorded)
    if not seen:
        raise PipelineError(f"{source_id}: {path.name} contains no records")
    if seen != {raw_sha}:
        raise PipelineError(
            f"{source_id}: the parsed citation data does not derive from the verified raw export.\n"
            f"  raw export (verified) {raw_sha}\n"
            f"  recorded in {path.name}  {', '.join(sorted(seen))}\n"
            "  The export has changed or been re-registered since parsing. Re-run "
            "parse_citations and validate_citations before deduplicating."
        )
    return raw_sha


def load_rows(source_ids: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source_id in source_ids:
        verify_provenance(source_id)
        path = citations_path(source_id)
        if not path.exists():
            raise PipelineError(
                f"{source_id}: {path.relative_to(PROCESSED_DIR.parent.parent).as_posix()} not found. "
                "Run parse_citations for this source first."
            )
        with open(path, encoding="utf-8", newline="") as fh:
            loaded = list(csv.DictReader(fh))
        if not loaded:
            raise PipelineError(f"{source_id}: citation table is empty")
        rows += loaded
    if not rows:
        raise PipelineError("no citation records loaded")
    return rows


def run(source_ids: list[str], source_order: list[str]) -> dict:
    rows = load_rows(source_ids)
    result = match.resolve(rows, source_order)
    assignment, pairs = result.assignment, result.pairs

    # Every input record must appear exactly once in the output. No silent loss, no duplication.
    if set(assignment) != {r["record_id"] for r in rows} or len(assignment) != len(rows):
        raise PipelineError(
            f"record count not conserved: {len(rows)} records in, {len(assignment)} assigned"
        )

    out_dir = PROCESSED_DIR / "dedup"
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path, audit_path = out_dir / "report_index.csv", out_dir / "dedup_audit.csv"

    with open(index_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=INDEX_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(rows, key=lambda r: (assignment[r["record_id"]]["report_id"],
                                               r["record_id"])):
            writer.writerow({**row, **assignment[row["record_id"]]})

    with open(audit_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=AUDIT_FIELDS)
        writer.writeheader()
        for n, pair in enumerate(pairs, start=1):
            writer.writerow({"pair_id": f"P{n:04d}", "record_a": pair.record_a,
                             "record_b": pair.record_b, "criterion": pair.criterion,
                             "matched_value": pair.matched_value, "resolution": pair.resolution})

    n_reports = len(result.report_ids)
    summary = {
        "records_in": len(rows),
        "per_source": {s: sum(1 for r in rows if r["source_id"] == s) for s in source_ids},
        "unique_reports": n_reports,
        "duplicates_removed": len(rows) - n_reports,
        "merged_pairs": len(result.merged_pairs),
        "duplicate_groups": result.duplicate_groups,
        "unresolved_pairs": result.unresolved_pairs,
        "index_path": index_path,
        "audit_path": audit_path,
    }
    summary["report_path"] = write_summary(summary, source_ids)
    return summary


def write_summary(summary: dict, source_ids: list[str]) -> str:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    path = VALIDATION_DIR / "dedup_summary.md"
    unresolved = summary["unresolved_pairs"]
    status = ("UNRESOLVED CANDIDATES — the counts below are provisional"
              if unresolved else "RESOLVED — counts are final for these sources")

    lines = [
        "# Deduplication summary", "",
        f"**Status: {status}**", "",
        f"Sources included: {', '.join(source_ids)}", "",
        "## Counts for the PRISMA flow", "",
        "| Item | Count |", "|---|---|",
        f"| Records identified (all sources) | {summary['records_in']} |",
    ]
    lines += [f"| … from `{s}` | {n} |" for s, n in summary["per_source"].items()]
    lines += [
        f"| Duplicate records removed | {summary['duplicates_removed']} |",
        f"| Unique reports (`report_id`) | {summary['unique_reports']} |",
        "",
        "Records are mapped to a `report_id`, never deleted; `data/processed/dedup/report_index.csv`",
        "retains every input record. A `report_id` is a unique *publication*; the unique *study*",
        "(`study_id`) is established later, at full text, by the reviewer (D004).",
        "",
        "## Matching", "",
        f"- Pairs merged on a shared identifier or exact fingerprint: {summary['merged_pairs']}",
        f"- **Duplicate groups** (canonical reports backed by more than one record): "
        f"{len(summary['duplicate_groups'])}",
        f"- Candidate pairs needing the reviewer's decision: {len(unresolved)}",
        "",
        "Pairs and groups count different things: a group of three records is three merged pairs "
        "but one canonical report. Pairs awaiting review form no group, because they are not "
        "merged.",
        "",
    ]
    if summary["duplicate_groups"]:
        lines += [
            "### Duplicate groups", "",
            "| Canonical `report_id` | Primary record | Duplicate record(s) | Matched on |",
            "|---|---|---|---|",
        ]
        lines += [
            f"| `{g.report_id}` | `{g.primary}` | "
            f"{', '.join(f'`{d}`' for d in g.duplicates)} | {'; '.join(g.criteria) or '—'} |"
            for g in summary["duplicate_groups"]
        ]
        lines += [
            "",
            "Every member record is retained in `report_index.csv`; grouping assigns a shared "
            "`report_id` and never deletes a record.",
            "",
        ]
    else:
        lines += [
            "No record was merged with another: every record is its own canonical report.", "",
        ]
    if unresolved:
        lines += [
            "### Pairs requiring review", "",
            "These titles are similar but not identical and share no DOI, PMID or exact",
            "title+author+year fingerprint. They have **not** been merged. A near-identical title",
            "may be a conference abstract, an erratum, a reanalysis or a different paper; only the",
            "reviewer can decide (D010).", "",
            "| Record A | Record B | Similarity |", "|---|---|---|",
        ]
        lines += [f"| `{p.record_a}` | `{p.record_b}` | {p.matched_value} |" for p in unresolved]
        lines += ["", "Record the decision for each pair in the decision log, then re-run this stage.", ""]
    else:
        lines += ["No pair required manual review.", ""]

    # Generated from match.EXACT_KEYS so the documented order cannot drift from the code.
    tiers = [f"{n}. {criterion}" for n, (_, criterion) in enumerate(match.EXACT_KEYS, start=1)]
    lines += [
        "## Method", "",
        "Matching is deterministic and applied in order of decreasing authority (D014):", "",
    ] + tiers + [
        f"{len(tiers) + 1}. similar title in the same year (similarity "
        f"≥ {match.TITLE_SIMILARITY_THRESHOLD}) — **flagged for review, never merged**",
        "",
        "DOIs are normalised (lowercased, URL and `doi:` prefixes stripped, trailing punctuation "
        "removed) and the fingerprint folds accents and reduces the title to alphanumeric words. "
        "Normalised values are used only for matching and never overwrite the values extracted "
        "from the export. Empty keys never match. Grouping is the transitive closure of the exact "
        "tiers, so group membership does not depend on their order; the order determines only "
        "which criterion is reported as the reason for a merge.", "",
        "The representative record of each group is chosen deterministically: earliest source in "
        "`config/sources.yaml`, then lowest numeric PMID, then lowest `record_id`. Field "
        "definitions and how to read these counts: `docs/data_dictionary/dedup.md`.", "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path.relative_to(VALIDATION_DIR.parent.parent).as_posix()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", action="append", dest="sources",
                    help="repeatable; default is every source with a parsed citation table")
    args = ap.parse_args(argv)
    try:
        all_sources = load_sources()
        source_order = [s.source_id for s in all_sources]
        # Default to executions that actually have a parsed export. Entries recording a missing
        # export are skipped here and left untouched in the registry (D011).
        selected = args.sources or [
            s.source_id for s in all_sources
            if not s.export_missing and citations_path(s.source_id).exists()
        ]
        if not selected:
            skipped = [s.source_id for s in all_sources if s.export_missing]
            detail = (f" Executions with no export, skipped: {', '.join(skipped)}."
                      if skipped else "")
            raise PipelineError(
                "no parsed citation tables found, so there is nothing to deduplicate. Run "
                "parse_citations for at least one source; its raw export must be registered "
                f"first.{detail}"
            )
        unknown = [s for s in selected if s not in source_order]
        if unknown:
            raise PipelineError(f"unknown source_id(s): {', '.join(unknown)}")
        summary = run(selected, source_order)
    except (PipelineError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"Records in: {summary['records_in']}  unique reports: {summary['unique_reports']}  "
          f"duplicates: {summary['duplicates_removed']}")
    print(f"Summary -> {summary['report_path']}")
    if summary["unresolved_pairs"]:
        print(f"{len(summary['unresolved_pairs'])} candidate pair(s) need the reviewer's decision; "
              "counts are provisional.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
