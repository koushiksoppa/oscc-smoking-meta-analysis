"""Integrity tests against the REAL raw exports. Skipped until the file is restored."""
import pytest

from scripts.acquisition import nbib
from scripts.acquisition.verify_raw import registered_checksums, sha256
from scripts.common.config import ROOT, load_sources

SOURCES = load_sources()


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s.source_id)
def test_raw_file_matches_registry(source):
    if source.export_missing:
        pytest.skip(f"{source.source_id}: records an execution whose export is missing, by design")
    if not source.raw_path.exists():
        pytest.skip(f"{source.raw_file} not present")
    text = nbib.decode(source.raw_path.read_bytes())
    records = nbib.parse(text)
    assert len(records) == nbib.count_records(text) == source.expected_records
    pmids = [r.first("PMID") for r in records]
    assert len(pmids) == len(set(pmids))

    rel = source.raw_path.relative_to(ROOT).as_posix()
    registered = registered_checksums().get(rel)
    if registered is None:
        pytest.skip("checksum not yet registered")
    assert sha256(source.raw_path) == registered
