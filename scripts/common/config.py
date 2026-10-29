"""Project paths and source-registry loading shared by all pipeline stages."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SOURCES_FILE = ROOT / "config" / "sources.yaml"
CHECKSUM_FILE = ROOT / "data" / "raw" / "SHA256SUMS"
PROCESSED_DIR = ROOT / "data" / "processed"
VALIDATION_DIR = ROOT / "results" / "validation"

# What kind of search run a registry entry records.
HISTORICAL = "historical"        # executed in the past; this entry is the documented claim
RE_EXECUTION = "re_execution"    # the same query string run again, later
NEW = "new"                      # a different strategy version
EXECUTIONS = frozenset({HISTORICAL, RE_EXECUTION, NEW})

# Whether an export exists for the entry, and whether it has been accepted as research input.
EXPORT_MISSING = "export_missing"
AWAITING_REGISTRATION = "awaiting_registration"
REGISTERED = "registered"
STATUSES = frozenset({EXPORT_MISSING, AWAITING_REGISTRATION, REGISTERED})


class PipelineError(RuntimeError):
    """Raised when a provenance or validation rule is violated. Never caught silently."""


@dataclass(frozen=True)
class Source:
    """One database × search execution.

    An entry is never repurposed. A re-run of the same query is a separate entry with its own
    execution date, record count and checksum (D005, D011), because the database's content
    changes over time and because the filters actually applied may differ.
    """
    source_id: str
    database: str
    search_version: str
    execution: str
    strategy_doc: str
    format: str
    status: str
    raw_file: str | None = None
    expected_records: int | None = None
    count_source: str | None = None
    search_date: str | None = None
    filters_applied: list[str] = field(default_factory=list)
    notes: str | None = None

    @property
    def raw_path(self) -> Path | None:
        """Absolute path to the export, or None when no export exists for this entry."""
        return ROOT / self.raw_file if self.raw_file else None

    @property
    def export_missing(self) -> bool:
        return self.status == EXPORT_MISSING

    @property
    def filters_label(self) -> str:
        return ", ".join(self.filters_applied) if self.filters_applied else "none"


def _validate(source: Source) -> None:
    if source.execution not in EXECUTIONS:
        raise PipelineError(
            f"{source.source_id}: execution must be one of {sorted(EXECUTIONS)}, "
            f"got {source.execution!r}"
        )
    if source.status not in STATUSES:
        raise PipelineError(
            f"{source.source_id}: status must be one of {sorted(STATUSES)}, got {source.status!r}"
        )
    # An entry either has an export or records that the export is missing. Never both, never neither.
    if source.export_missing and source.raw_file:
        raise PipelineError(
            f"{source.source_id}: status is '{EXPORT_MISSING}' but raw_file is set "
            f"({source.raw_file}). An entry whose export is missing must not point at a file; a "
            "different file is a different search execution (D005)."
        )
    if not source.export_missing and not source.raw_file:
        raise PipelineError(
            f"{source.source_id}: no raw_file, so status must be '{EXPORT_MISSING}'"
        )
    if source.raw_file and not source.raw_file.startswith("data/raw/"):
        raise PipelineError(f"{source.source_id}: raw_file must live under data/raw/")
    if source.expected_records is not None and source.expected_records <= 0:
        raise PipelineError(
            f"{source.source_id}: expected_records must be positive, got {source.expected_records}"
        )
    if source.expected_records is not None and not source.count_source:
        raise PipelineError(
            f"{source.source_id}: expected_records is set but count_source is empty. Record where "
            "the count came from, so a documented claim is never mistaken for a verified figure."
        )


def load_sources() -> list[Source]:
    with open(SOURCES_FILE, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    sources = [Source(**entry) for entry in data["sources"]]

    ids = [s.source_id for s in sources]
    if len(ids) != len(set(ids)):
        raise PipelineError(f"Duplicate source_id in {SOURCES_FILE.name}: {ids}")
    files = [s.raw_file for s in sources if s.raw_file]
    if len(files) != len(set(files)):
        raise PipelineError(
            f"Two registry entries point at the same raw_file in {SOURCES_FILE.name}: {files}"
        )
    for source in sources:
        _validate(source)
    return sources


def status_line(source_id: str) -> int | None:
    """1-based line number of this entry's `status:` key in the registry, for messages.

    Indentation-aware: entries are the shallowest `- ` items, so nested sequences such as
    `filters_applied:` are not mistaken for new entries, and `status:` is matched only at the
    entry's own key indent — never inside a folded block such as `notes:`.
    Returns None if the entry or its key cannot be located; callers must degrade gracefully.
    """
    lines = SOURCES_FILE.read_text(encoding="utf-8").splitlines()
    marks = [(n, len(line) - len(line.lstrip()))
             for n, line in enumerate(lines, start=1) if line.lstrip().startswith("- ")]
    if not marks:
        return None
    entry_indent = min(indent for _, indent in marks)
    key_indent = entry_indent + 2
    starts = [n for n, indent in marks if indent == entry_indent]

    for start, end in zip(starts, starts[1:] + [len(lines) + 1]):
        found_id: str | None = None
        found_line: int | None = None
        for offset, line in enumerate(lines[start - 1:end - 1]):
            indent = len(line) - len(line.lstrip())
            text = line.strip()
            if offset == 0:                      # the entry marker may carry the first key inline
                text = text[2:].strip()
            elif indent != key_indent:
                continue
            if text.startswith("source_id:"):
                found_id = text.split(":", 1)[1].strip()
            elif text.startswith("status:") and found_line is None:
                found_line = start + offset
        if found_id == source_id:
            return found_line
    return None


def get_source(source_id: str) -> Source:
    for s in load_sources():
        if s.source_id == source_id:
            return s
    known = ", ".join(s.source_id for s in load_sources())
    raise PipelineError(
        f"Unknown source_id '{source_id}' (not in {SOURCES_FILE.name}). Known: {known}"
    )
