"""Inspect and verify a raw export before any stage reads it.

Three modes, deliberately separate so that looking at a file can never change the project's
authoritative record of it:

    --report-only   READ-ONLY. Inspects a newly supplied file and writes a *proposed* intake
                    report to results/validation/. Never writes SHA256SUMS. Use this first.
    (no flag)       Strict gate used by the pipeline: requires an already-registered checksum
                    that still matches, and the expected record count.
    --register      Records the checksum in data/raw/SHA256SUMS (append-only), and only if the
                    record count matches. A registered checksum is never overwritten.

Registration is an authorized act: it declares a file to be the project's research input.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass, field

from scripts.acquisition import nbib
from scripts.common import config
from scripts.common.config import (CHECKSUM_FILE, REGISTERED, ROOT, VALIDATION_DIR, PipelineError,
                                   Source, get_source)

REQUIRED_TAGS = {"PMID": "PubMed ID", "TI": "title", "DP": "publication date"}


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def registered_checksums() -> dict[str, str]:
    """Parse SHA256SUMS ('<hex>  <relative/path>' per line, sha256sum-compatible)."""
    sums: dict[str, str] = {}
    if not CHECKSUM_FILE.exists():
        return sums
    for line in CHECKSUM_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        digest, path = line.split(maxsplit=1)
        path = path.strip().lstrip("*")
        if path in sums and sums[path] != digest:
            raise PipelineError(f"{CHECKSUM_FILE.name} lists conflicting checksums for {path}")
        sums[path] = digest
    return sums


@dataclass
class Intake:
    """Result of inspecting a raw file. Anomalies are reported, never repaired."""
    source_id: str
    rel_path: str
    size_bytes: int
    sha256: str
    expected_records: int | None
    n_pmid_tags: int | None = None     # counted by scanning for 'PMID-' at line start
    n_parsed: int | None = None        # counted by the record parser
    registered_sha256: str | None = None
    anomalies: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def count_confirmed(self) -> bool:
        """True only when both internal counts agree with an independently reported count."""
        return (self.n_parsed is not None
                and self.expected_records is not None
                and self.n_parsed == self.n_pmid_tags == self.expected_records)


def check_records(
    records: list[nbib.NbibRecord], expected: int | None
) -> tuple[list[str], list[str]]:
    """Record-level anomaly and note detection. Pure: no file access, no repair."""
    anomalies: list[str] = []
    notes: list[str] = []

    if expected is None:
        notes.append(
            f"No independently reported record count for this source, so the {len(records)} "
            "records in the file cannot be cross-checked. Registration is blocked until the count "
            "reported by the database at execution is recorded in config/sources.yaml."
        )
    elif len(records) != expected:
        anomalies.append(
            f"File contains {len(records)} records but {expected} were reported for this source. "
            "This may not be the export it is registered against."
        )
    pmids = [r.first("PMID") for r in records]
    duplicates = sorted({p for p in pmids if p and pmids.count(p) > 1})
    if duplicates:
        anomalies.append(f"Duplicate PMIDs within the file: {', '.join(duplicates)}")

    for tag, label in REQUIRED_TAGS.items():
        missing = [r.first("PMID") or f"line {r.line_start}" for r in records if not r.first(tag)]
        if missing:
            where = ", ".join(missing[:10]) + (" …" if len(missing) > 10 else "")
            anomalies.append(f"{len(missing)} record(s) with no {label} ({tag}): {where}")

    edats = [e for e in (r.first("EDAT") for r in records) if e]
    if edats:
        notes.append(
            f"Latest Entrez date in the file: {max(edats)}. This is a LOWER BOUND on the search "
            "date, not the search date itself (decision-log P009)."
        )
    years = sorted({y for y in (nbib.extract_year(r.first("DP")) for r in records) if y})
    if years:
        notes.append(f"Publication years span {years[0]}–{years[-1]}.")
    return anomalies, notes


def inspect(source: Source) -> Intake:
    """Read-only inspection. Raises only if the file is absent or of an unsupported format."""
    if source.export_missing:
        raise PipelineError(
            f"{source.source_id}: this entry records a search execution whose export is missing, "
            "so it has no file by design.\n"
            "  It is not recreated and not substituted: any new retrieval is a separate execution "
            "with its own entry, date, count and checksum (D005, D011).\n"
            "  If the original export is found, add it under this entry's raw_file and set status "
            "to 'awaiting_registration'."
        )
    path = source.raw_path
    if not path.exists():
        raise PipelineError(
            f"{source.source_id}: raw file missing: {source.raw_file}\n"
            "Place the export for THIS entry at that path. Do not substitute a different "
            "execution's file; that is a separate registry entry (D005, D011)."
        )
    if source.format != "nbib":
        raise PipelineError(f"{source.source_id}: no inspector for format '{source.format}'")

    raw = path.read_bytes()
    rel = path.relative_to(ROOT).as_posix()
    result = Intake(
        source_id=source.source_id,
        rel_path=rel,
        size_bytes=len(raw),
        sha256=sha256(path),
        expected_records=source.expected_records,
        registered_sha256=registered_checksums().get(rel),
    )
    if raw.startswith(b"\xef\xbb\xbf"):
        result.notes.append("File begins with a UTF-8 byte-order mark (tolerated).")

    try:
        text = nbib.decode(raw)
    except nbib.NbibFormatError as exc:
        result.anomalies.append(f"Encoding: {exc}")
        return result

    result.n_pmid_tags = nbib.count_records(text)
    try:
        records = nbib.parse(text)
    except nbib.NbibFormatError as exc:
        result.anomalies.append(f"Parse failure: {exc}")
        return result

    result.n_parsed = len(records)
    if result.n_parsed != result.n_pmid_tags:
        result.anomalies.append(
            f"Record count disagrees between methods: parser {result.n_parsed}, "
            f"PMID-tag scan {result.n_pmid_tags}."
        )
    anomalies, notes = check_records(records, source.expected_records)
    result.anomalies += anomalies
    result.notes += notes

    if result.registered_sha256 and result.registered_sha256 != result.sha256:
        result.anomalies.append(
            f"CHECKSUM MISMATCH against the registered value for {rel}:\n"
            f"      registered {result.registered_sha256}\n      current    {result.sha256}"
        )
    return result


def write_intake_report(result: Intake, source: Source) -> str:
    """Write the PROPOSED intake report. Does not touch SHA256SUMS."""
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    path = VALIDATION_DIR / f"{result.source_id}_intake_proposed.md"
    if result.anomalies:
        verdict = "ANOMALIES FOUND — do not register until these are explained"
    elif result.count_confirmed:
        verdict = "CONSISTENT — awaiting the reviewer's authorization to register"
    else:
        verdict = "INCOMPLETE — record count could not be confirmed"
    expected = (str(result.expected_records) if result.expected_records is not None
                else "*not recorded*")

    lines = [
        f"# Proposed intake report — {result.source_id}",
        "",
        "**This report is a proposal, not a registration.** Nothing in `data/` has been created or",
        "modified, and `data/raw/SHA256SUMS` has not been written. The checksum below becomes the",
        "project's authoritative value only when the reviewer authorizes",
        f"`verify_raw --source {result.source_id} --register`.",
        "",
        f"**Verdict: {verdict}**",
        "",
        "## File",
        "",
        "| Property | Value |",
        "|---|---|",
        f"| Path | `{result.rel_path}` |",
        f"| Size | {result.size_bytes:,} bytes |",
        f"| SHA-256 | `{result.sha256}` |",
        f"| Database | {source.database} |",
        f"| Search version | {source.search_version} |",
        f"| Execution type | {source.execution} |",
        f"| Filters applied at retrieval | {source.filters_label} |",
        f"| Strategy document | `{source.strategy_doc}` |",
        f"| Execution date | {source.search_date or '*not recorded*'} |",
        f"| Checksum already registered | {'yes' if result.registered_sha256 else 'no'} |",
        "",
        "## Record count",
        "",
        "Counted two independent ways; both must agree with the count reported for this source.",
        "",
        "| Method | Count |",
        "|---|---|",
        f"| Record parser | {result.n_parsed if result.n_parsed is not None else 'not determined'} |",
        f"| `PMID-` tag scan | {result.n_pmid_tags if result.n_pmid_tags is not None else 'not determined'} |",
        f"| Reported for this source | {expected} |",
        "",
        f"Provenance of the reported count: {source.count_source or '*not recorded*'}",
        "",
    ]
    for title, items, empty in (
        ("Anomalies", result.anomalies, "None."),
        ("Notes", result.notes, "None."),
    ):
        lines += [f"## {title}", ""] + ([f"- {x}" for x in items] or [empty]) + [""]
    lines += [
        "## Next step",
        "",
        ("Resolve the anomalies above before registering. If the file is not the export this entry "
         "describes, it must be recorded as its own search execution rather than registered here "
         "(decision-log D005, D011)."
         if result.anomalies else
         f"If you confirm this is the export produced by the {source.execution} search described in "
         f"`{source.strategy_doc}` (filters applied: {source.filters_label}), authorize:\n\n"
         f"```\npython -m scripts.acquisition.verify_raw --source {result.source_id} --register\n```"),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path.relative_to(ROOT).as_posix())


def verify(source: Source, register: bool = False) -> dict:
    """Strict gate. Every stage that reads a raw file calls this first."""
    result = inspect(source)
    blocking = [a for a in result.anomalies if not a.startswith("CHECKSUM MISMATCH")]
    if blocking:
        raise PipelineError(f"{source.source_id}: " + "\n  ".join(blocking))
    if not result.count_confirmed:
        raise PipelineError(f"{source.source_id}: record count could not be confirmed")

    if result.registered_sha256 is None:
        if not register:
            raise PipelineError(
                f"{source.source_id}: checksum not registered. Inspect the file first with "
                f"--report-only, then, once you have confirmed it is the export this entry "
                f"describes, authorize --register."
            )
        with open(CHECKSUM_FILE, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(f"{result.sha256}  {result.rel_path}\n")
        status = "registered"
    elif result.registered_sha256 != result.sha256:
        raise PipelineError(
            f"{source.source_id}: CHECKSUM MISMATCH for {result.rel_path}\n"
            f"  registered {result.registered_sha256}\n  current    {result.sha256}\n"
            "The raw file has changed since registration."
        )
    else:
        status = "verified"
    return {"source_id": source.source_id, "file": result.rel_path, "records": result.n_parsed,
            "sha256": result.sha256, "status": status}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--report-only", action="store_true",
                      help="read-only inspection; writes a proposed intake report, registers nothing")
    mode.add_argument("--register", action="store_true",
                      help="record the checksum on first verified import (authorized act)")
    args = ap.parse_args(argv)

    try:
        source = get_source(args.source)
        if args.report_only:
            result = inspect(source)
            report = write_intake_report(result, source)
            print(f"Proposed intake report written to {report}")
            print(f"  sha256   {result.sha256}")
            print(f"  size     {result.size_bytes:,} bytes")
            print(f"  records  parser={result.n_parsed} pmid_tags={result.n_pmid_tags} "
                  f"expected={result.expected_records}")
            if result.anomalies:
                print(f"ANOMALIES ({len(result.anomalies)}): nothing registered. Review the report.",
                      file=sys.stderr)
                return 1
            print("No anomalies. Checksum NOT registered — authorize --register to do that.")
            return 0
        outcome = verify(source, register=args.register)
    except (PipelineError, nbib.NbibFormatError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"{outcome['status'].upper()}: {outcome['file']}  records={outcome['records']}  "
          f"sha256={outcome['sha256']}")
    if outcome["status"] == "registered" and source.status != REGISTERED:
        print(registry_reminder(source))
    return 0


def registry_reminder(source: Source) -> str:
    """Tell the reviewer which registry line to update after a first registration.

    The registry is not rewritten automatically: it is hand-curated and its comments record why
    each entry exists, which a programmatic YAML rewrite would delete. So the status is updated by
    hand, and tests/test_source_registry.py fails until it matches the checksum manifest.
    """
    registry = config.SOURCES_FILE
    rel = (registry.relative_to(config.ROOT).as_posix()
           if registry.is_relative_to(config.ROOT) else registry)
    line = config.status_line(source.source_id)
    where = f"line {line}" if line else f"the `{source.source_id}` entry"
    return (
        f"\nReminder: {rel} still records status '{source.status}' for this source.\n"
        f"  Update {where}:  status: {REGISTERED}\n"
        "  The registry is not rewritten automatically so its comments survive. Until it is "
        "updated, tests/test_source_registry.py fails."
    )


if __name__ == "__main__":
    sys.exit(main())
