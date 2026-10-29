"""Validator rule tests. Rows are structural stubs (field values like 'x'), not citations."""
import pytest

from scripts.common.config import Source
from scripts.validation.validate_citations import check

# The false claim this suite exists to prevent: a report asserting a filter was used when the
# registry records none. See decision log D013 and the P011 regression.
FALSE_CLAIM = "English filter was applied"


def src(expected_records=2, filters=()):
    return Source(
        source_id="test_src", database="PubMed", search_version="vX", execution="re_execution",
        strategy_doc="", format="nbib", status="awaiting_registration",
        raw_file="data/raw/none", expected_records=expected_records,
        count_source="test fixture", filters_applied=list(filters),
    )


SRC = src()                                  # unfiltered, as pubmed_v1r is
FILTERED = src(filters=["Humans", "English"])  # as the historical pubmed_v1 claims


def row(pmid, doi="", title="x", year="2000", languages="eng", mesh="Humans"):
    return {"record_id": f"test_src:{pmid}", "source_id": "test_src", "pmid": pmid,
            "doi": doi, "doi_all": doi, "title": title, "pub_year": year,
            "languages": languages, "mesh_terms": mesh}


def all_findings(f):
    return f.errors + f.warnings + f.info


def test_clean_rows_pass():
    assert check([row("1"), row("2")], SRC).errors == []


def test_record_count_mismatch_is_error():
    assert any("expected 2" in e for e in check([row("1")], SRC).errors)


def test_duplicate_pmid_is_error():
    assert any("duplicate PMID" in e for e in check([row("1"), row("1")], SRC).errors)


def test_duplicate_doi_is_case_insensitive_error():
    errs = check([row("1", doi="10.1000/ABC"), row("2", doi="10.1000/abc")], SRC).errors
    assert any("duplicate DOI" in e for e in errs)


def test_missing_required_field_is_error():
    assert any("'title'" in e for e in check([row("1", title=""), row("2")], SRC).errors)


def test_malformed_doi_is_flagged_not_repaired():
    f = check([row("1", doi="doi:10.1000/182"), row("2")], SRC)
    assert f.errors == []
    assert any("malformed DOI" in w for w in f.warnings)


# --- filter cross-checks: the report must never assert a filter the registry does not record ----

def test_unfiltered_source_does_not_claim_a_filter_was_applied():
    """P011 regression: pubmed_v1r is unfiltered, so a Chinese record is expected, not anomalous."""
    f = check([row("1", languages="chi"), row("2")], SRC)

    assert f.errors == []
    assert not any(FALSE_CLAIM in m for m in all_findings(f)), \
        "a report must not assert an English filter that config/sources.yaml does not record"
    assert any("no English language tag: 1" in i and "not_english" in i for i in f.info)


def test_non_english_record_contradicts_a_claimed_english_filter():
    f = check([row("1", languages="chi"), row("2")], FILTERED)

    assert len(f.errors) == 1
    assert "records an English filter at retrieval" in f.errors[0]
    assert "could not have been retrieved" in f.errors[0]


@pytest.mark.parametrize("source", [SRC, FILTERED], ids=["unfiltered", "filtered"])
def test_multilingual_record_including_english_is_never_flagged(source):
    """PubMed's English filter retrieves records whose LA list contains eng, e.g. 'eng; por'."""
    f = check([row("1", languages="eng; por"), row("2")], source)
    assert f.errors == []
    assert not any("language" in m for m in f.warnings + f.info)


def test_record_without_language_tag_is_not_treated_as_non_english():
    f = check([row("1", languages=""), row("2")], FILTERED)
    assert f.errors == []


@pytest.mark.parametrize("tags", ["ENG", "Eng", "eng", "POR; ENG", " eng "])
def test_english_language_code_is_matched_case_insensitively(tags):
    """MEDLINE writes lowercase codes, but a case-sensitive test would misclassify 'ENG'."""
    assert check([row("1", languages=tags), row("2")], FILTERED).errors == []


def test_language_tags_are_reported_exactly_as_recorded():
    """Case-insensitive comparison must not rewrite the value shown in the report."""
    f = check([row("1", languages="CHI"), row("2")], FILTERED)
    assert "['CHI']" in f.errors[0], "the report must quote the tag as the database recorded it"


# --- the Humans cross-check, within the limits of what MeSH can establish --------------------

def test_missing_humans_mesh_contradicts_a_claimed_humans_filter():
    f = check([row("1", mesh="Mice; Neoplasms"), row("2")], FILTERED)

    assert len(f.errors) == 1
    assert "not 'Humans'" in f.errors[0] and "records a Humans filter" in f.errors[0]


def test_unindexed_record_contradicts_a_claimed_humans_filter():
    f = check([row("1", mesh=""), row("2")], FILTERED)

    assert len(f.errors) == 1
    assert "not MEDLINE-indexed" in f.errors[0]


def test_unfiltered_source_reports_records_without_humans_mesh_as_a_count_not_an_error():
    f = check([row("1", mesh=""), row("2")], SRC)

    assert f.errors == []
    assert any("without MeSH 'Humans': 1" in i for i in f.info)


def test_report_claims_nothing_about_indexing_status_it_cannot_verify():
    """The MEDLINE STAT field is not in the citation dataset, so neither 'awaiting indexing'
    nor 'non-human' may be asserted from the absence of MeSH alone."""
    f = check([row("1", mesh=""), row("2")], SRC)
    line = next(i for i in f.info if "without MeSH 'Humans'" in i)

    assert "MeSH indexing status is not available in the citation dataset" in line
    assert "species eligibility is unknown from these records" in line
    assert "assessed at screening" in line
    for unsupported in ("awaiting MeSH indexing", "awaiting indexing", "non-human studies"):
        assert unsupported not in line, f"unsupported claim in report: {unsupported!r}"


def test_humans_check_is_skipped_when_the_export_carries_no_mesh_at_all():
    """Cannot distinguish 'all unindexed' from 'export omitted MeSH', so do not invent errors."""
    f = check([row("1", mesh=""), row("2", mesh="")], FILTERED)

    assert f.errors == [], "an export with no MeSH must not produce one error per record"
    assert any("cannot be applied" in w for w in f.warnings)


def test_mesh_subheadings_and_major_topic_markers_are_parsed():
    f = check([row("1", mesh="*Humans/genetics; Mouth Neoplasms/*epidemiology"), row("2")], FILTERED)
    assert f.errors == []
