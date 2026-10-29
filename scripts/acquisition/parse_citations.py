"""Stage 1: verified raw export -> machine-readable citation records.

    python -m scripts.acquisition.parse_citations --source pubmed_v1

Outputs (data/processed/citations/):
  <source_id>_records.jsonl    every tag of every record, lossless, with raw line number
  <source_id>_citations.csv    flat citation table (fields: docs/data_dictionary/citations.md)

Refuses to run unless verify_raw passes (record count + registered checksum).
Values are copied as reported; missing values are left empty, never inferred.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys

from scripts.acquisition import nbib
from scripts.acquisition.verify_raw import verify
from scripts.common.config import PROCESSED_DIR, PipelineError, Source, get_source

CITATION_FIELDS = [
    "record_id", "source_id", "database", "search_version", "raw_line_start",
    "pmid", "doi", "doi_all", "title", "title_tag", "first_author", "authors", "author_count",
    "journal", "journal_abbrev", "pub_year", "pub_date_raw", "abstract",
    "publication_types", "languages", "mesh_terms", "keywords", "entrez_date",
]
LIST_SEP = "; "


def to_citation(rec: nbib.NbibRecord, source: Source) -> dict[str, str]:
    pmid = rec.first("PMID") or ""
    dois = nbib.extract_dois(rec)
    title_tag = "TI" if rec.first("TI") else ("BTI" if rec.first("BTI") else "")
    authors = rec.all("FAU") or rec.all("AU")
    return {
        "record_id": f"{source.source_id}:{pmid}",
        "source_id": source.source_id,
        "database": source.database,
        "search_version": source.search_version,
        "raw_line_start": str(rec.line_start),
        "pmid": pmid,
        "doi": dois[0] if dois else "",
        "doi_all": LIST_SEP.join(dois),
        "title": (rec.first(title_tag) or "") if title_tag else "",
        "title_tag": title_tag,
        "first_author": authors[0] if authors else "",
        "authors": LIST_SEP.join(authors),
        "author_count": str(len(authors)),
        "journal": rec.first("JT") or "",
        "journal_abbrev": rec.first("TA") or "",
        "pub_year": nbib.extract_year(rec.first("DP")) or "",
        "pub_date_raw": rec.first("DP") or "",
        "abstract": rec.first("AB") or "",
        "publication_types": LIST_SEP.join(rec.all("PT")),
        "languages": LIST_SEP.join(rec.all("LA")),
        "mesh_terms": LIST_SEP.join(rec.all("MH")),
        "keywords": LIST_SEP.join(rec.all("OT")),
        "entrez_date": rec.first("EDAT") or "",
    }


def run(source: Source) -> dict:
    verification = verify(source, register=False)
    records = nbib.parse(nbib.decode(source.raw_path.read_bytes()))

    out_dir = PROCESSED_DIR / "citations"
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / f"{source.source_id}_records.jsonl"
    csv_path = out_dir / f"{source.source_id}_citations.csv"

    with open(jsonl_path, "w", encoding="utf-8", newline="\n") as fh:
        for rec in records:
            fh.write(json.dumps({
                "source_id": source.source_id,
                "raw_sha256": verification["sha256"],
                "raw_line_start": rec.line_start,
                "fields": rec.fields,
            }, ensure_ascii=False) + "\n")

    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CITATION_FIELDS)
        writer.writeheader()
        for rec in records:
            writer.writerow(to_citation(rec, source))

    # No record may disappear between the raw file and either output.
    with open(csv_path, encoding="utf-8", newline="") as fh:
        n_csv = sum(1 for _ in csv.DictReader(fh))
    n_jsonl = sum(1 for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip())
    if not (len(records) == n_csv == n_jsonl == verification["records"]):
        raise PipelineError(
            f"{source.source_id}: record count not conserved — raw {verification['records']}, "
            f"parsed {len(records)}, csv {n_csv}, jsonl {n_jsonl}"
        )

    return {"records": len(records), "csv": csv_path, "jsonl": jsonl_path}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True)
    args = ap.parse_args(argv)
    try:
        result = run(get_source(args.source))
    except (PipelineError, nbib.NbibFormatError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"Parsed {result['records']} records -> {result['csv'].name}, {result['jsonl'].name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
