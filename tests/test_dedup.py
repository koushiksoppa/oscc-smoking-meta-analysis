"""Deduplication: matching, grouping, report_id assignment and record conservation.

Rows are structural stubs (field values like 't1', 'Last, First'), not citations — D007.
"""
import csv
import json
from types import SimpleNamespace

import pytest
import yaml

from scripts.acquisition import verify_raw
from scripts.common import config
from scripts.common.config import PipelineError
from scripts.dedup import deduplicate, match, normalise

ORDER = ["src_a", "src_b"]


def row(rid, pmid="", doi="", title="", author="", year="", source="src_a"):
    return {"record_id": rid, "source_id": source, "pmid": pmid, "doi": doi,
            "title": title, "first_author": author, "pub_year": year}


def group_of(rows, rid):
    groups, _ = match.find_duplicates(rows)
    return sorted(groups.as_groups()[next(
        i for i, g in enumerate(groups.as_groups()) if rid in g)])


# --- normalisation -------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("10.1000/182", "10.1000/182"),
    ("  10.1000/182  ", "10.1000/182"),
    ("10.1000/ABC", "10.1000/abc"),
    ("https://doi.org/10.1000/182", "10.1000/182"),
    ("doi:10.1000/182", "10.1000/182"),
    ("https://dx.doi.org/10.1000/182.", "10.1000/182"),
    ("", ""),
    (None, ""),
])
def test_doi_normalisation(raw, expected):
    assert normalise.normalise_doi(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("Title: a study!", "title a study"),
    ("TITLE   a  study", "title a study"),
    ("Tïtle a study", "title a study"),
    ("", ""),
    (None, ""),
])
def test_title_normalisation(raw, expected):
    assert normalise.normalise_title(raw) == expected


def test_surname_takes_the_part_before_the_comma():
    assert normalise.surname("Last, First M") == "last"
    assert normalise.surname("O'Brien, A") == "obrien"
    assert normalise.surname(None) == ""


def test_fingerprint_requires_all_three_parts():
    assert normalise.fingerprint("T", "Last, F", "2001") == "t|last|2001"
    for args in (("T", "Last, F", ""), ("", "Last, F", "2001"), ("T", "", "2001")):
        assert normalise.fingerprint(*args) == ""


# --- matching ------------------------------------------------------------------------

def test_shared_doi_merges_across_sources():
    rows = [row("a:1", doi="10.1000/182"), row("b:9", doi="HTTPS://doi.org/10.1000/182", source="src_b")]
    assert group_of(rows, "a:1") == ["a:1", "b:9"]


def test_shared_pmid_merges():
    rows = [row("a:1", pmid="7"), row("b:9", pmid="7", source="src_b")]
    assert group_of(rows, "a:1") == ["a:1", "b:9"]


def test_identical_fingerprint_merges_without_identifiers():
    rows = [row("a:1", title="A study", author="Last, F", year="2001"),
            row("b:9", title="a  study!", author="Last, First", year="2001", source="src_b")]
    groups, pairs = match.find_duplicates(rows)
    assert len(groups.as_groups()) == 1
    assert any(p.criterion == match.BY_FINGERPRINT for p in pairs)


def test_empty_keys_never_match():
    """The classic deduplication bug: records with no DOI must not group on ''."""
    rows = [row("a:1", pmid="1"), row("a:2", pmid="2"), row("a:3", pmid="3")]
    groups, pairs = match.find_duplicates(rows)
    assert len(groups.as_groups()) == 3
    assert pairs == []


def test_same_title_different_year_does_not_merge():
    rows = [row("a:1", pmid="1", title="A study", author="Last, F", year="2001"),
            row("a:2", pmid="2", title="A study", author="Last, F", year="2009")]
    groups, _ = match.find_duplicates(rows)
    assert len(groups.as_groups()) == 2


def test_merging_is_transitive():
    rows = [row("a:1", pmid="1", doi="10.1000/x"),
            row("a:2", pmid="1", doi=""),
            row("a:3", pmid="", doi="10.1000/X")]
    assert group_of(rows, "a:1") == ["a:1", "a:2", "a:3"]


# --- similar titles are flagged, never merged ----------------------------------------

def test_similar_title_is_flagged_for_review_and_not_merged():
    rows = [row("a:1", pmid="1", title="Smoking and oral cancer in adults", author="Last, F", year="2001"),
            row("a:2", pmid="2", title="Smoking and oral cancer in adult", author="Other, S", year="2001")]
    groups, pairs = match.find_duplicates(rows)
    assert len(groups.as_groups()) == 2, "similar titles must not be merged automatically"
    flagged = [p for p in pairs if p.resolution == match.NEEDS_REVIEW]
    assert len(flagged) == 1 and "similar title" in flagged[0].criterion


def test_unrelated_titles_are_not_flagged():
    rows = [row("a:1", pmid="1", title="Alpha beta gamma delta", author="Last, F", year="2001"),
            row("a:2", pmid="2", title="Completely different words here", author="Other, S", year="2001")]
    _, pairs = match.find_duplicates(rows)
    assert pairs == []


def test_already_merged_pairs_are_not_also_flagged():
    rows = [row("a:1", pmid="1", doi="10.1000/x", title="Smoking and oral cancer", author="Last, F", year="2001"),
            row("a:2", pmid="2", doi="10.1000/x", title="Smoking and oral cancr", author="Last, F", year="2001")]
    _, pairs = match.find_duplicates(rows)
    assert [p.resolution for p in pairs] == [match.MERGED]


# --- report_id assignment ------------------------------------------------------------

def test_every_record_is_assigned_exactly_once():
    rows = [row("a:1", pmid="1"), row("a:2", pmid="2"), row("b:1", pmid="1", source="src_b")]
    groups, pairs = match.find_duplicates(rows)
    assignment = match.assign_report_ids(rows, groups, pairs, ORDER)
    assert set(assignment) == {"a:1", "a:2", "b:1"}
    assert len({a["report_id"] for a in assignment.values()}) == 2


def test_duplicate_points_at_its_primary_with_a_criterion():
    rows = [row("a:1", pmid="1"), row("b:1", pmid="1", source="src_b")]
    groups, pairs = match.find_duplicates(rows)
    assignment = match.assign_report_ids(rows, groups, pairs, ORDER)
    assert assignment["a:1"]["is_primary"] == "yes"
    assert assignment["b:1"] == {"report_id": assignment["a:1"]["report_id"], "is_primary": "no",
                                 "duplicate_of": "a:1", "merged_with": "a:1",
                                 "merge_criterion": "shared PMID"}


def test_a_direct_match_is_never_labelled_transitive():
    """Regression: a non-primary record appearing as pair.record_a was mislabelled 'transitive'.

    Here the primary has the HIGHER record_id (its source comes first), so the duplicate is the
    first element of the pair — the end the old code never inspected.
    """
    rows = [row("b:1", pmid="5", source="src_b"), row("z:9", pmid="5")]
    result = match.resolve(rows, ORDER)

    assert result.assignment["z:9"]["is_primary"] == "yes"
    assert result.assignment["b:1"]["merge_criterion"] == match.BY_PMID
    assert result.assignment["b:1"]["merged_with"] == "z:9"
    assert "transitive" not in {i["merge_criterion"] for i in result.assignment.values()}


def test_chained_group_names_the_record_actually_matched():
    """a:3 links to a:2 by DOI, not to the primary a:1 — the report must say so.

    Previously `merge_criterion` sat beside `duplicate_of` and so asserted evidence between two
    records sharing nothing.
    """
    rows = [row("a:1", pmid="7"), row("a:2", pmid="7", doi="10.1000/z"), row("a:3", doi="10.1000/Z")]
    result = match.resolve(rows, ORDER)
    a2, a3 = result.assignment["a:2"], result.assignment["a:3"]

    assert a2["duplicate_of"] == "a:1" and a2["merged_with"] == "a:1"
    assert a2["merge_criterion"] == match.BY_PMID
    assert a3["duplicate_of"] == "a:1", "the group's primary"
    assert a3["merged_with"] == "a:2", "but the DOI match is with a:2"
    assert a3["merge_criterion"] == match.BY_DOI


def test_every_duplicate_names_a_real_direct_match():
    """Across several topologies, merged_with must be a genuine same-group partner."""
    topologies = [
        [row("a:1", pmid="1"), row("a:2", pmid="1"), row("a:3", pmid="1")],
        [row("a:1", pmid="1", doi="10.1000/x"), row("a:2", pmid="1"), row("a:3", doi="10.1000/X")],
        [row("b:1", pmid="5", source="src_b"), row("z:9", pmid="5")],
        [row("a:1", title="T", author="L, F", year="2001"),
         row("b:1", title="t", author="L, First", year="2001", source="src_b")],
    ]
    for rows in topologies:
        result = match.resolve(rows, ORDER)
        for rid, info in result.assignment.items():
            if info["is_primary"] == "yes":
                assert info["merged_with"] == "" and info["merge_criterion"] == ""
                continue
            partner = info["merged_with"]
            assert partner, f"{rid}: no record named for its match"
            assert result.assignment[partner]["report_id"] == info["report_id"]
            assert info["merge_criterion"] != "transitive"


def test_primary_prefers_the_earlier_source():
    rows = [row("b:1", pmid="5", source="src_b"), row("a:9", pmid="5", source="src_a")]
    groups, pairs = match.find_duplicates(rows)
    assignment = match.assign_report_ids(rows, groups, pairs, ORDER)
    assert assignment["a:9"]["is_primary"] == "yes"


def test_assignment_is_deterministic_regardless_of_input_order():
    rows = [row("a:3", pmid="3"), row("a:1", pmid="1"), row("a:2", pmid="2")]
    first = match.assign_report_ids(rows, *match.find_duplicates(rows), ORDER)
    shuffled = list(reversed(rows))
    second = match.assign_report_ids(shuffled, *match.find_duplicates(shuffled), ORDER)
    assert first == second


def test_duplicate_record_ids_in_input_fail_loudly():
    with pytest.raises(ValueError, match="duplicate record_id"):
        match.find_duplicates([row("a:1", pmid="1"), row("a:1", pmid="2")])

# --- criterion priority: report the strongest evidence for a merge (D014) -------------

def test_pair_sharing_both_identifiers_is_reported_as_a_pmid_match():
    """PMID outranks DOI, so report_index must name PMID, not whichever sorted first."""
    rows = [row("a:1", pmid="7", doi="10.1000/x"),
            row("b:9", pmid="7", doi="10.1000/X", source="src_b")]
    groups, pairs = match.find_duplicates(rows)
    assignment = match.assign_report_ids(rows, groups, pairs, ORDER)

    assert assignment["b:9"]["merge_criterion"] == match.BY_PMID
    assert {p.criterion for p in pairs} == {match.BY_PMID, match.BY_DOI}, \
        "the audit still records every criterion that matched, not only the strongest"


def test_identifier_match_outranks_a_fingerprint_match():
    """Regression: a pair sharing a PMID was reported as a fingerprint match."""
    rows = [row("a:1", pmid="5", title="T", author="L, F", year="2001"),
            row("b:1", pmid="5", title="t", author="L, First", year="2001", source="src_b")]
    groups, pairs = match.find_duplicates(rows)
    assignment = match.assign_report_ids(rows, groups, pairs, ORDER)

    assert assignment["b:1"]["merge_criterion"] == match.BY_PMID


def test_doi_only_pair_still_merges_and_is_reported_as_a_doi_match():
    rows = [row("a:1", doi="10.1000/x"), row("b:9", doi="10.1000/x", source="src_b")]
    groups, pairs = match.find_duplicates(rows)
    assignment = match.assign_report_ids(rows, groups, pairs, ORDER)

    assert len(groups.as_groups()) == 1
    assert assignment["b:9"]["merge_criterion"] == match.BY_DOI


def test_group_membership_is_independent_of_criterion_order(monkeypatch):
    """Grouping is the transitive closure of all criteria, so priority cannot change it."""
    rows = [row("a:1", pmid="1", doi="10.1000/x"), row("a:2", pmid="1"),
            row("a:3", doi="10.1000/X"), row("a:4", pmid="9")]
    expected = match.find_duplicates(rows)[0].as_groups()

    reversed_keys = tuple(reversed(match.EXACT_KEYS))
    monkeypatch.setattr(match, "EXACT_KEYS", reversed_keys)
    assert match.find_duplicates(rows)[0].as_groups() == expected


# --- duplicate groups, reported separately from pair counts ---------------------------

def test_duplicate_groups_expose_members_primary_and_criteria():
    rows = [row("a:1", pmid="1"), row("a:2", pmid="1"), row("b:1", pmid="1", source="src_b"),
            row("a:9", pmid="9")]
    result = match.resolve(rows, ORDER)

    assert len(result.duplicate_groups) == 1, "only groups with >1 record are duplicate groups"
    group = result.duplicate_groups[0]
    assert group.members == ("a:1", "a:2", "b:1")
    assert group.primary == "a:1"
    assert group.duplicates == ("a:2", "b:1")
    assert group.criteria == (match.BY_PMID,)
    assert group.report_id == result.assignment["a:1"]["report_id"]


def test_three_record_group_is_one_group_but_several_pairs():
    result = match.resolve([row("a:1", pmid="1"), row("a:2", pmid="1"), row("a:3", pmid="1")], ORDER)

    assert len(result.duplicate_groups) == 1
    assert len(result.merged_pairs) == 2
    assert result.report_ids == {result.assignment["a:1"]["report_id"]}


def test_pairs_awaiting_review_form_no_group():
    result = match.resolve([
        row("a:1", pmid="1", title="Smoking and oral cancer in adults", author="L, F", year="2001"),
        row("a:2", pmid="2", title="Smoking and oral cancer in adult", author="O, S", year="2001"),
    ], ORDER)

    assert [p.resolution for p in result.pairs] == [match.NEEDS_REVIEW]
    assert result.unresolved_pairs == result.pairs and result.merged_pairs == []
    assert result.duplicate_groups == []


def test_match_result_bundles_pairs_with_their_assignment():
    """The two cannot be mismatched: every derived count comes from one run."""
    result = match.resolve([row("a:1", pmid="1"), row("a:2", pmid="1"), row("a:9", pmid="9")], ORDER)

    assert set(result.assignment) == {r["record_id"] for r in result.rows}
    assert len(result.report_ids) == 2
    assert len(result.merged_pairs) + len(result.unresolved_pairs) == len(result.pairs)
    assert not hasattr(match, "duplicate_groups"), \
        "the standalone function is private; callers must go through MatchResult"


# --- the stage, end to end, with real provenance --------------------------------------

@pytest.fixture
def stage(tmp_path, monkeypatch):
    """A sandbox holding a registry, raw exports, registered checksums and parsed data.

    The raw files are MEDLINE format stubs (D007); their only role is to satisfy the record-count
    and checksum gate, so their PMIDs are sequential and independent of the citation rows.
    """
    root = tmp_path
    (root / "data" / "raw" / "pubmed").mkdir(parents=True)
    processed, validation = root / "data" / "processed", root / "results" / "validation"
    checksums, registry = root / "data" / "raw" / "SHA256SUMS", root / "sources.yaml"

    for module in (config, verify_raw):
        monkeypatch.setattr(module, "ROOT", root)
        monkeypatch.setattr(module, "CHECKSUM_FILE", checksums)
    monkeypatch.setattr(config, "SOURCES_FILE", registry)
    monkeypatch.setattr(verify_raw, "VALIDATION_DIR", validation)
    monkeypatch.setattr(deduplicate, "PROCESSED_DIR", processed)
    monkeypatch.setattr(deduplicate, "VALIDATION_DIR", validation)

    entries: list[dict] = []

    def add_source(source_id, rows, *, register=True, csv_table=True, jsonl=True,
                   raw_sha=None, drop_provenance=False, export_missing=False):
        raw_rel = f"data/raw/pubmed/{source_id}.nbib"
        if not export_missing:
            (root / raw_rel).write_text(
                "\n".join(f"PMID- {i}\nTI  - t{i}\nDP  - 2000\n" for i in range(1, len(rows) + 1)),
                encoding="utf-8")
        entries.append(dict(
            source_id=source_id, database="PubMed", search_version="vX",
            execution="historical" if export_missing else "re_execution", strategy_doc="d",
            format="nbib", status="export_missing" if export_missing else "awaiting_registration",
            raw_file=None if export_missing else raw_rel,
            expected_records=len(rows), count_source="test fixture", filters_applied=[]))
        registry.write_text(yaml.safe_dump({"sources": entries}), encoding="utf-8")
        if export_missing:
            return None

        digest = None
        if register:
            digest = verify_raw.verify(config.get_source(source_id), register=True)["sha256"]
        if csv_table:
            path = processed / "citations" / f"{source_id}_citations.csv"
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        if jsonl:
            recorded = raw_sha if raw_sha is not None else digest
            payload = [{"source_id": source_id, "raw_line_start": 1, "fields": []} for _ in rows]
            if not drop_provenance:
                for entry in payload:
                    entry["raw_sha256"] = recorded
            path = processed / "citations" / f"{source_id}_records.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(json.dumps(e) for e in payload) + "\n", encoding="utf-8")
        return digest

    def read_index():
        with open(processed / "dedup" / "report_index.csv", encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    def read_audit():
        with open(processed / "dedup" / "dedup_audit.csv", encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    return SimpleNamespace(add_source=add_source, read_index=read_index, read_audit=read_audit,
                           validation=validation, processed=processed)


def test_stage_retains_every_record_and_maps_duplicates(stage):
    stage.add_source("src_a", [row("a:1", pmid="1"), row("a:2", pmid="2")])
    stage.add_source("src_b", [row("b:1", pmid="1", source="src_b")])

    summary = deduplicate.run(["src_a", "src_b"], ORDER)

    assert (summary["records_in"], summary["unique_reports"],
            summary["duplicates_removed"]) == (3, 2, 1)
    assert len(stage.read_index()) == 3, "no record may be dropped from the index"
    assert [a["criterion"] for a in stage.read_audit()] == [match.BY_PMID]
    assert len(summary["duplicate_groups"]) == 1
    body = (stage.validation / "dedup_summary.md").read_text(encoding="utf-8")
    assert "RESOLVED" in body and "Duplicate groups" in body and "`a:1`" in body


def test_stage_marks_counts_provisional_when_review_is_needed(stage):
    stage.add_source("src_a", [
        row("a:1", pmid="1", title="Smoking and oral cancer in adults", author="L, F", year="2001"),
        row("a:2", pmid="2", title="Smoking and oral cancer in adult", author="O, S", year="2001"),
    ])
    summary = deduplicate.run(["src_a"], ORDER)

    assert len(summary["unresolved_pairs"]) == 1
    assert summary["unique_reports"] == 2, "flagged pairs stay separate until the reviewer decides"
    assert summary["duplicate_groups"] == []
    body = (stage.validation / "dedup_summary.md").read_text(encoding="utf-8")
    assert "UNRESOLVED CANDIDATES" in body and "provisional" in body


# --- provenance: the raw/derived-data consistency check must fail closed ---------------

def test_unregistered_checksum_blocks_deduplication(stage):
    stage.add_source("src_a", [row("a:1", pmid="1")], register=False)
    with pytest.raises(PipelineError, match="checksum not registered"):
        deduplicate.run(["src_a"], ORDER)


def test_parsed_data_from_a_different_raw_file_is_refused(stage):
    stage.add_source("src_a", [row("a:1", pmid="1")], raw_sha="0" * 64)
    with pytest.raises(PipelineError, match="does not derive from the verified raw export"):
        deduplicate.run(["src_a"], ORDER)


def test_one_divergent_record_among_many_is_refused(stage):
    """Every parsed record's provenance is checked, not just the first.

    Only record 3 of 5 diverges, so an implementation that read one line and stopped — or that
    short-circuited on the first match — would accept this file. The source is fully realistic:
    a registered export, its checksum in the manifest, and the derived JSONL the fixture
    produced, with a single line altered afterwards as a stale or tampered file would be.
    """
    rows = [row(f"a:{i}", pmid=str(i)) for i in range(1, 6)]
    digest = stage.add_source("src_a", rows)

    path = stage.processed / "citations" / "src_a_records.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(records) == 5 and {r["raw_sha256"] for r in records} == {digest}, \
        "fixture must start from genuinely consistent provenance"

    records[2]["raw_sha256"] = "0" * 64          # the middle record only; 1, 2, 4, 5 stay correct
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

    with pytest.raises(PipelineError, match="does not derive from the verified raw export") as caught:
        deduplicate.run(["src_a"], ORDER)

    message = str(caught.value)
    assert digest in message and "0" * 64 in message, "the error must name both checksums"
    assert not (stage.processed / "dedup").exists(), \
        "deduplication must refuse before writing any output"


def test_missing_provenance_metadata_cannot_bypass_the_check(stage):
    """Absent raw_sha256 is an error, never an implicit pass."""
    stage.add_source("src_a", [row("a:1", pmid="1")], drop_provenance=True)
    with pytest.raises(PipelineError, match="Missing provenance is not a pass"):
        deduplicate.run(["src_a"], ORDER)


def test_absent_parsed_records_file_is_refused(stage):
    stage.add_source("src_a", [row("a:1", pmid="1")], jsonl=False)
    with pytest.raises(PipelineError, match="provenance cannot be checked"):
        deduplicate.run(["src_a"], ORDER)


def test_missing_citation_table_is_refused(stage):
    stage.add_source("src_a", [row("a:1", pmid="1")], csv_table=False)
    with pytest.raises(PipelineError, match="Run parse_citations"):
        deduplicate.run(["src_a"], ORDER)


# --- sources whose export is missing --------------------------------------------------

def test_export_missing_source_explains_it_cannot_be_parsed(stage):
    stage.add_source("hist_v1", [row("h:1", pmid="1")], export_missing=True)
    with pytest.raises(PipelineError, match="export for this search execution is missing"):
        deduplicate.run(["hist_v1"], ORDER)


def test_default_selection_skips_export_missing_without_touching_the_registry(stage):
    stage.add_source("hist_v1", [row("h:1", pmid="1")], export_missing=True)
    stage.add_source("src_a", [row("a:1", pmid="1"), row("a:2", pmid="2")])

    assert deduplicate.main([]) == 0
    assert [r["source_id"] for r in stage.read_index()] == ["src_a", "src_a"]
    assert {s.source_id for s in config.load_sources()} == {"hist_v1", "src_a"}, \
        "skipping must not delete or rewrite a registry entry"
    assert config.get_source("hist_v1").expected_records == 1


def test_cli_exits_nonzero_when_nothing_has_been_parsed(stage):
    stage.add_source("hist_v1", [row("h:1", pmid="1")], export_missing=True)
    assert deduplicate.main([]) == 1


def test_cli_rejects_an_unknown_source(stage):
    stage.add_source("src_a", [row("a:1", pmid="1")])
    assert deduplicate.main(["--source", "not_a_source"]) == 1
