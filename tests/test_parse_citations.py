"""Citation parsing: no record is lost, no raw tag is dropped, no value is invented.

Fixtures are MEDLINE format fragments (structural stubs, D007) in pytest's temp directory.
"""
import csv
import json

import pytest

from scripts.acquisition import nbib, parse_citations, verify_raw
from scripts.common import config
from scripts.common.config import Source

RECORD = (
    "PMID- 1\n"
    "TI  - t one\n"
    "      continued\n"
    "DP  - 2001 Mar\n"
    "FAU - Last, First\n"
    "FAU - Other, Second\n"
    "TA  - Abbrev\n"
    "JT  - Journal Title\n"
    "AB  - abstract text\n"
    "PT  - Journal Article\n"
    "LA  - eng\n"
    "MH  - Term A\n"
    "OT  - kw\n"
    "EDAT- 2024/01/02\n"
    "AID - 10.1000/182 [doi]\n"
    "AID - S000 [pii]\n"
)
MINIMAL = "PMID- 2\nTI  - t two\nDP  - 1999\n"


@pytest.fixture
def parsed(tmp_path, monkeypatch):
    """Register a two-record fragment and parse it; yields (rows, jsonl_lines)."""
    checksums = tmp_path / "data" / "raw" / "SHA256SUMS"
    (tmp_path / "data" / "raw" / "pubmed").mkdir(parents=True)
    for module in (config, verify_raw):
        monkeypatch.setattr(module, "ROOT", tmp_path)
        monkeypatch.setattr(module, "CHECKSUM_FILE", checksums)
    monkeypatch.setattr(parse_citations, "PROCESSED_DIR", tmp_path / "data" / "processed")

    path = tmp_path / "data" / "raw" / "pubmed" / "export.nbib"
    path.write_text(RECORD + "\n" + MINIMAL, encoding="utf-8")
    source = Source(
        source_id="test_src", database="PubMed", search_version="vX", execution="re_execution",
        strategy_doc="docs/search/x.md", format="nbib", status="awaiting_registration",
        raw_file="data/raw/pubmed/export.nbib", expected_records=2, count_source="test fixture",
    )
    verify_raw.verify(source, register=True)

    result = parse_citations.run(source)
    with open(result["csv"], encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    lines = [json.loads(x) for x in result["jsonl"].read_text(encoding="utf-8").splitlines() if x.strip()]
    return rows, lines


def test_no_record_is_lost(parsed):
    rows, lines = parsed
    assert len(rows) == len(lines) == 2


def test_jsonl_preserves_every_raw_tag_in_order(parsed):
    _, lines = parsed
    original = nbib.parse(RECORD)[0].fields
    assert [tuple(f) for f in lines[0]["fields"]] == original


def test_jsonl_records_the_raw_checksum_and_line_number(parsed):
    _, lines = parsed
    assert len(lines[0]["raw_sha256"]) == 64
    assert lines[0]["raw_line_start"] == 1


def test_csv_has_exactly_the_documented_fields(parsed):
    rows, _ = parsed
    assert list(rows[0]) == parse_citations.CITATION_FIELDS


def test_values_are_copied_not_reformatted(parsed):
    rows, _ = parsed
    row = rows[0]
    assert row["title"] == "t one continued"          # continuation joined, text unchanged
    assert row["pub_date_raw"] == "2001 Mar"          # raw date preserved
    assert row["pub_year"] == "2001"                  # year taken, not reformatted
    assert row["authors"] == "Last, First; Other, Second"
    assert row["first_author"] == "Last, First"
    assert row["author_count"] == "2"
    assert row["doi"] == "10.1000/182"
    assert row["record_id"] == "test_src:1"


def test_absent_fields_are_empty_never_guessed(parsed):
    rows, _ = parsed
    minimal = rows[1]
    for empty in ("doi", "doi_all", "abstract", "journal", "journal_abbrev", "keywords", "mesh_terms"):
        assert minimal[empty] == "", f"{empty} should be empty, not inferred"
    assert minimal["author_count"] == "0"


def test_parsing_is_deterministic(parsed, tmp_path):
    rows, _ = parsed
    second = (tmp_path / "data" / "processed" / "citations" / "test_src_citations.csv").read_text(encoding="utf-8")
    assert second.count("\n") == len(rows) + 1
