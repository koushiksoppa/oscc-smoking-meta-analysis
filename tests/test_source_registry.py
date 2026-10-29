"""Registry invariants (D011): one entry per search execution, and no entry can lie about itself.

The real config/sources.yaml is also checked, so a malformed registry fails the suite.
"""
import pytest

from scripts.acquisition.verify_raw import registered_checksums
from scripts.common import config
from scripts.common.config import PipelineError, Source, load_sources


def entry(**overrides):
    fields = dict(
        source_id="s1", database="PubMed", search_version="v1", execution="re_execution",
        strategy_doc="docs/search/x.md", format="nbib", status="awaiting_registration",
        raw_file="data/raw/pubmed/x.nbib", expected_records=10, count_source="results page",
    )
    return Source(**{**fields, **overrides})


def write_registry(tmp_path, monkeypatch, *entries):
    import yaml
    path = tmp_path / "sources.yaml"
    path.write_text(yaml.safe_dump({"sources": list(entries)}), encoding="utf-8")
    monkeypatch.setattr(config, "SOURCES_FILE", path)


def as_dict(source: Source) -> dict:
    return {k: getattr(source, k) for k in (
        "source_id", "database", "search_version", "execution", "strategy_doc", "format",
        "status", "raw_file", "expected_records", "count_source", "filters_applied")}


# --- the real registry ---------------------------------------------------------------

def test_the_project_registry_loads_and_validates():
    sources = {s.source_id: s for s in load_sources()}
    assert "pubmed_v1" in sources and "pubmed_v1r" in sources


def test_historical_v1_records_a_missing_export_and_keeps_its_own_count():
    v1 = next(s for s in load_sources() if s.source_id == "pubmed_v1")
    assert v1.export_missing and v1.raw_file is None and v1.raw_path is None
    assert v1.expected_records == 138, "the documented v1 claim must not be edited to match a re-run"
    assert v1.execution == "historical"


def test_reexecution_is_a_separate_entry_with_its_own_file_and_count():
    v1r = next(s for s in load_sources() if s.source_id == "pubmed_v1r")
    assert v1r.execution == "re_execution"
    assert v1r.expected_records == 194
    assert v1r.filters_applied == [], "the re-execution applied no filters; that is the v1 difference"
    assert v1r.raw_file != "data/raw/pubmed/pubmed-OralSquamo-set.nbib", \
        "a re-execution must not occupy the original export's filename (D012)"


def test_every_reported_count_states_where_it_came_from():
    for source in load_sources():
        if source.expected_records is not None:
            assert source.count_source, f"{source.source_id}: count without provenance"


# --- the registry's status must agree with the checksum manifest -----------------------
#
# `verify_raw --register` writes data/raw/SHA256SUMS but deliberately does not rewrite
# config/sources.yaml: the registry is human-curated and carries the explanatory comments that
# record why each entry exists, which a programmatic YAML rewrite would destroy. These tests are
# what keep the two in step, so a registration that leaves the status stale fails loudly.

def test_status_registered_agrees_with_the_checksum_manifest():
    manifest = registered_checksums()
    for source in load_sources():
        if source.export_missing:
            continue
        if source.raw_file in manifest:
            assert source.status == config.REGISTERED, (
                f"{source.source_id}: its checksum is in data/raw/SHA256SUMS, so status should be "
                f"'{config.REGISTERED}', not {source.status!r}. Update config/sources.yaml."
            )
        else:
            assert source.status == config.AWAITING_REGISTRATION, (
                f"{source.source_id}: status is {source.status!r} but no checksum for "
                f"{source.raw_file} appears in data/raw/SHA256SUMS. Either register the export or "
                f"set status to '{config.AWAITING_REGISTRATION}'."
            )


def test_pubmed_v1r_is_recorded_as_registered():
    v1r = next(s for s in load_sources() if s.source_id == "pubmed_v1r")
    assert v1r.status == config.REGISTERED
    assert v1r.raw_file in registered_checksums()


def test_export_missing_entries_claim_no_checksum():
    manifest = registered_checksums()
    for source in load_sources():
        if source.export_missing:
            assert source.raw_file is None
            assert not any(source.source_id in path for path in manifest), (
                f"{source.source_id}: records a missing export, yet SHA256SUMS lists a file for it"
            )


def test_status_line_locates_the_key_in_the_real_registry():
    """The reminder printed after --register must point at the right line."""
    lines = config.SOURCES_FILE.read_text(encoding="utf-8").splitlines()
    for source in load_sources():
        n = config.status_line(source.source_id)
        assert n is not None, f"{source.source_id}: status line not located"
        assert lines[n - 1].strip() == f"status: {source.status}"


def test_status_line_is_not_confused_by_nested_sequences(tmp_path, monkeypatch):
    """`filters_applied: - Humans` items are not entries, and `notes:` text is not a key."""
    registry = tmp_path / "sources.yaml"
    registry.write_text(
        "sources:\n"
        "  - source_id: a\n"
        "    status: registered\n"            # line 3
        "    filters_applied:\n"
        "      - Humans\n"
        "      - English\n"
        "    notes: >-\n"
        "      a note mentioning status: awaiting_registration in prose\n"
        "  - source_id: b\n"
        "    filters_applied: []\n"
        "    status: awaiting_registration\n"  # line 11
        "    notes: none\n",
        encoding="utf-8")
    monkeypatch.setattr(config, "SOURCES_FILE", registry)

    assert config.status_line("a") == 3
    assert config.status_line("b") == 11
    assert config.status_line("absent") is None


def test_status_line_handles_an_entry_whose_first_key_is_not_source_id(tmp_path, monkeypatch):
    """yaml.safe_dump sorts keys, so source_id need not lead the entry."""
    registry = tmp_path / "sources.yaml"
    registry.write_text(
        "sources:\n"
        "- count_source: x\n"
        "  source_id: a\n"
        "  status: registered\n",            # line 4
        encoding="utf-8")
    monkeypatch.setattr(config, "SOURCES_FILE", registry)
    assert config.status_line("a") == 4


def test_every_checksum_entry_belongs_to_a_registry_entry():
    """Catches a manifest line left behind after its registry entry was removed or renamed."""
    claimed = {s.raw_file for s in load_sources() if s.raw_file}
    orphans = sorted(set(registered_checksums()) - claimed)
    assert not orphans, f"data/raw/SHA256SUMS lists files no registry entry claims: {orphans}"


# --- invariants ----------------------------------------------------------------------

def test_missing_export_must_not_point_at_a_file(tmp_path, monkeypatch):
    write_registry(tmp_path, monkeypatch,
                   as_dict(entry(status="export_missing", raw_file="data/raw/pubmed/x.nbib")))
    with pytest.raises(PipelineError, match="must not point at a file"):
        load_sources()


def test_entry_without_a_file_must_declare_the_export_missing(tmp_path, monkeypatch):
    write_registry(tmp_path, monkeypatch, as_dict(entry(raw_file=None)))
    with pytest.raises(PipelineError, match="status must be 'export_missing'"):
        load_sources()


def test_two_entries_cannot_claim_the_same_export(tmp_path, monkeypatch):
    write_registry(tmp_path, monkeypatch,
                   as_dict(entry(source_id="a")), as_dict(entry(source_id="b")))
    with pytest.raises(PipelineError, match="same raw_file"):
        load_sources()


def test_duplicate_source_id_is_rejected(tmp_path, monkeypatch):
    write_registry(tmp_path, monkeypatch,
                   as_dict(entry()), as_dict(entry(raw_file="data/raw/pubmed/y.nbib")))
    with pytest.raises(PipelineError, match="Duplicate source_id"):
        load_sources()


def test_count_without_provenance_is_rejected(tmp_path, monkeypatch):
    write_registry(tmp_path, monkeypatch, as_dict(entry(count_source=None)))
    with pytest.raises(PipelineError, match="count_source is empty"):
        load_sources()


@pytest.mark.parametrize("bad", [{"execution": "guess"}, {"status": "probably_fine"}])
def test_unknown_enum_values_are_rejected(tmp_path, monkeypatch, bad):
    write_registry(tmp_path, monkeypatch, as_dict(entry(**bad)))
    with pytest.raises(PipelineError, match="must be one of"):
        load_sources()


def test_raw_file_must_live_under_data_raw(tmp_path, monkeypatch):
    write_registry(tmp_path, monkeypatch, as_dict(entry(raw_file="downloads/x.nbib")))
    with pytest.raises(PipelineError, match="must live under data/raw/"):
        load_sources()


def test_unknown_source_id_lists_the_known_ones():
    with pytest.raises(PipelineError, match="Known: pubmed_v1"):
        config.get_source("pubmed_v9")
