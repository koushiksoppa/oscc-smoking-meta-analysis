"""Intake gate: read-only inspection, anomaly detection, and checksum registration.

Fixture files are MEDLINE format fragments (structural stubs with no bibliographic content,
per D007), written to pytest's temp directory. Nothing here touches the repository's data/.
"""
import pytest

from scripts.acquisition import nbib, verify_raw
from scripts.common import config
from scripts.common.config import PipelineError, Source

TWO_RECORDS = "PMID- 1\nTI  - a\nDP  - 2000\n\nPMID- 2\nTI  - b\nDP  - 2001\n"


def stub(n):
    return "\n".join(f"PMID- {i}\nTI  - t{i}\nDP  - 2000\n" for i in range(1, n + 1))


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Relocate ROOT, SHA256SUMS and the report directory into a temp tree."""
    checksums = tmp_path / "data" / "raw" / "SHA256SUMS"
    (tmp_path / "data" / "raw" / "pubmed").mkdir(parents=True)
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(verify_raw, "ROOT", tmp_path)
    monkeypatch.setattr(config, "CHECKSUM_FILE", checksums)
    monkeypatch.setattr(verify_raw, "CHECKSUM_FILE", checksums)
    monkeypatch.setattr(verify_raw, "VALIDATION_DIR", tmp_path / "results" / "validation")
    return tmp_path, checksums


def make_source(tmp_path, text, expected=2, **overrides):
    path = tmp_path / "data" / "raw" / "pubmed" / "export.nbib"
    path.write_text(text, encoding="utf-8")
    return source_entry(expected_records=expected, **overrides)


def source_entry(**overrides):
    fields = dict(
        source_id="test_src", database="PubMed", search_version="vX",
        execution="re_execution", strategy_doc="docs/search/x.md", format="nbib",
        status="awaiting_registration", raw_file="data/raw/pubmed/export.nbib",
        expected_records=2, count_source="test fixture",
    )
    return Source(**{**fields, **overrides})


# --- read-only guarantee -------------------------------------------------------------

def test_report_only_writes_a_report_and_registers_nothing(sandbox):
    tmp_path, checksums = sandbox
    source = make_source(tmp_path, TWO_RECORDS)
    result = verify_raw.inspect(source)
    report = verify_raw.write_intake_report(result, source)

    assert result.anomalies == []
    assert result.count_confirmed
    assert (tmp_path / report).exists()
    assert not checksums.exists(), "report-only must never write SHA256SUMS"
    body = (tmp_path / report).read_text(encoding="utf-8")
    assert result.sha256 in body and "not a registration" in body


def test_inspect_does_not_modify_the_source_file(sandbox):
    tmp_path, _ = sandbox
    source = make_source(tmp_path, TWO_RECORDS)
    before = source.raw_path.read_bytes()
    verify_raw.inspect(source)
    assert source.raw_path.read_bytes() == before


def test_report_is_written_even_when_anomalies_are_found(sandbox):
    tmp_path, checksums = sandbox
    source = make_source(tmp_path, TWO_RECORDS, expected=138)
    result = verify_raw.inspect(source)
    report = verify_raw.write_intake_report(result, source)
    assert result.anomalies and not checksums.exists()
    assert "ANOMALIES FOUND" in (tmp_path / report).read_text(encoding="utf-8")


# --- anomaly detection (pure) --------------------------------------------------------

def test_count_mismatch_is_an_anomaly():
    anomalies, _ = verify_raw.check_records(nbib.parse(stub(2)), expected=138)
    assert any("may not be the export it is registered against" in a for a in anomalies)


def test_duplicate_pmid_within_file_is_an_anomaly():
    anomalies, _ = verify_raw.check_records(nbib.parse("PMID- 1\nTI  - a\nDP  - 2000\n\nPMID- 1\nTI  - b\nDP  - 2000\n"), 2)
    assert any("Duplicate PMIDs" in a for a in anomalies)


def test_missing_required_tag_is_an_anomaly():
    anomalies, _ = verify_raw.check_records(nbib.parse("PMID- 1\nDP  - 2000\n"), 1)
    assert any("no title" in a for a in anomalies)


def test_entrez_date_is_reported_as_a_lower_bound_only():
    _, notes = verify_raw.check_records(nbib.parse("PMID- 1\nTI  - a\nDP  - 2000\nEDAT- 2024/01/02\n"), 1)
    assert any("LOWER BOUND" in n for n in notes)


def test_clean_records_produce_no_anomalies():
    anomalies, _ = verify_raw.check_records(nbib.parse(stub(3)), expected=3)
    assert anomalies == []


# --- registration gate ---------------------------------------------------------------

def test_verify_refuses_until_registered_then_succeeds(sandbox):
    tmp_path, checksums = sandbox
    source = make_source(tmp_path, TWO_RECORDS)

    with pytest.raises(PipelineError, match="not registered"):
        verify_raw.verify(source)

    assert verify_raw.verify(source, register=True)["status"] == "registered"
    assert checksums.exists()
    assert verify_raw.verify(source)["status"] == "verified"


def test_register_reminds_which_registry_line_to_update(sandbox, monkeypatch, capsys):
    """A first registration must name the registry line whose status is now stale."""
    tmp_path, _ = sandbox
    registry = tmp_path / "sources.yaml"
    registry.write_text(
        "sources:\n"
        "  - source_id: test_src\n"
        "    database: PubMed\n"
        "    search_version: vX\n"
        "    execution: re_execution\n"
        "    strategy_doc: docs/search/x.md\n"
        "    format: nbib\n"
        "    status: awaiting_registration\n"          # line 8
        "    raw_file: data/raw/pubmed/export.nbib\n"
        "    expected_records: 2\n"
        "    count_source: test fixture\n",
        encoding="utf-8")
    monkeypatch.setattr(config, "SOURCES_FILE", registry)
    (tmp_path / "data" / "raw" / "pubmed" / "export.nbib").write_text(TWO_RECORDS, encoding="utf-8")

    assert verify_raw.main(["--source", "test_src", "--register"]) == 0
    out = capsys.readouterr().out

    assert "REGISTERED" in out
    assert "line 8" in out and "status: registered" in out
    assert "awaiting_registration" in out, "the reminder states the stale value it found"


def test_reminder_is_not_printed_when_the_registry_is_already_correct(sandbox, monkeypatch, capsys):
    tmp_path, _ = sandbox
    registry = tmp_path / "sources.yaml"
    registry.write_text(
        "sources:\n"
        "  - source_id: test_src\n"
        "    database: PubMed\n"
        "    search_version: vX\n"
        "    execution: re_execution\n"
        "    strategy_doc: d\n"
        "    format: nbib\n"
        "    status: registered\n"
        "    raw_file: data/raw/pubmed/export.nbib\n"
        "    expected_records: 2\n"
        "    count_source: test fixture\n",
        encoding="utf-8")
    monkeypatch.setattr(config, "SOURCES_FILE", registry)
    (tmp_path / "data" / "raw" / "pubmed" / "export.nbib").write_text(TWO_RECORDS, encoding="utf-8")

    assert verify_raw.main(["--source", "test_src", "--register"]) == 0
    assert "Reminder" not in capsys.readouterr().out


def test_altered_raw_file_fails_after_registration(sandbox):
    tmp_path, _ = sandbox
    source = make_source(tmp_path, TWO_RECORDS)
    verify_raw.verify(source, register=True)

    source.raw_path.write_text(TWO_RECORDS.replace("TI  - a", "TI  - A"), encoding="utf-8")
    with pytest.raises(PipelineError, match="CHECKSUM MISMATCH"):
        verify_raw.verify(source)


def test_registration_refused_when_count_disagrees(sandbox):
    tmp_path, checksums = sandbox
    source = make_source(tmp_path, TWO_RECORDS, expected=138)
    with pytest.raises(PipelineError, match="may not be the export it is registered against"):
        verify_raw.verify(source, register=True)
    assert not checksums.exists()


def test_registered_checksum_is_never_overwritten(sandbox):
    tmp_path, checksums = sandbox
    source = make_source(tmp_path, TWO_RECORDS)
    verify_raw.verify(source, register=True)
    first = checksums.read_text(encoding="utf-8")
    verify_raw.verify(source, register=True)
    assert checksums.read_text(encoding="utf-8") == first


def test_missing_file_forbids_substituting_another_execution(sandbox):
    source = source_entry(raw_file="data/raw/pubmed/absent.nbib")
    with pytest.raises(PipelineError, match="Do not substitute a different"):
        verify_raw.inspect(source)


def test_export_missing_entry_has_no_file_by_design(sandbox):
    """An entry recording a lost export must not be inspected, substituted or recreated."""
    source = source_entry(status="export_missing", raw_file=None, execution="historical")
    with pytest.raises(PipelineError, match="no file by design"):
        verify_raw.inspect(source)


def test_unrecorded_expected_count_blocks_registration(sandbox):
    """Without an independently reported count there is nothing to cross-check against."""
    tmp_path, checksums = sandbox
    source = make_source(tmp_path, TWO_RECORDS, expected=None, count_source=None)
    result = verify_raw.inspect(source)

    assert result.anomalies == []
    assert not result.count_confirmed
    assert any("cannot be cross-checked" in n for n in result.notes)
    with pytest.raises(PipelineError, match="count could not be confirmed"):
        verify_raw.verify(source, register=True)
    assert not checksums.exists()
