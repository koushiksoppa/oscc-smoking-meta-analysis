"""Lossless parser for PubMed/MEDLINE (.nbib) exports.

Format: each field starts with a tag of up to four characters padded to four, then "- ".
Continuation lines start with six spaces. Records are separated by blank lines.
Repeated tags (FAU, PT, AID, ...) are kept in order. Nothing is dropped or repaired.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TAG_LINE = re.compile(r"^([A-Z0-9]{2,4}) {0,2}- ?(.*)$")
CONTINUATION = "      "
YEAR = re.compile(r"^(\d{4})")
DOI_SUFFIX = " [doi]"


class NbibFormatError(ValueError):
    pass


@dataclass
class NbibRecord:
    line_start: int                      # 1-based line number in the raw file
    fields: list[tuple[str, str]] = field(default_factory=list)

    def all(self, tag: str) -> list[str]:
        return [v for t, v in self.fields if t == tag]

    def first(self, tag: str) -> str | None:
        values = self.all(tag)
        return values[0] if values else None


def decode(raw: bytes) -> str:
    """Strict UTF-8 decode (BOM tolerated). Undecodable bytes are an error, not replaced."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise NbibFormatError(f"File is not valid UTF-8: {exc}") from exc


def parse(text: str) -> list[NbibRecord]:
    records: list[NbibRecord] = []
    current: NbibRecord | None = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            if current is not None:
                records.append(current)
                current = None
            continue
        if line.startswith(CONTINUATION):
            if current is None or not current.fields:
                raise NbibFormatError(f"line {lineno}: continuation line with no preceding field")
            tag, value = current.fields[-1]
            current.fields[-1] = (tag, f"{value} {line.strip()}")
            continue
        m = TAG_LINE.match(line)
        if not m:
            raise NbibFormatError(f"line {lineno}: unrecognised line: {line[:60]!r}")
        if current is None:
            current = NbibRecord(line_start=lineno)
        current.fields.append((m.group(1), m.group(2).strip()))
    if current is not None:
        records.append(current)
    for rec in records:
        if rec.fields[0][0] != "PMID":
            raise NbibFormatError(f"line {rec.line_start}: record does not start with PMID")
    return records


def count_records(text: str) -> int:
    """Independent count (PMID tags at line start), used to cross-check the parser."""
    return sum(1 for line in text.splitlines() if line.startswith("PMID-"))


def extract_dois(record: NbibRecord) -> list[str]:
    """DOIs tagged '[doi]' in AID, then LID; de-duplicated, order preserved, not normalised."""
    found: list[str] = []
    for tag in ("AID", "LID"):
        for value in record.all(tag):
            if value.endswith(DOI_SUFFIX):
                doi = value[: -len(DOI_SUFFIX)].strip()
                if doi not in found:
                    found.append(doi)
    return found


def extract_year(dp: str | None) -> str | None:
    if not dp:
        return None
    m = YEAR.match(dp.strip())
    return m.group(1) if m else None
