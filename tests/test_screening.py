"""Stage 3 screening: vocabulary, worksheet generation, validation and PRISMA accounting.

Rows are structural stubs with no bibliographic content (D007). No test records a screening
decision that is presented as a reviewer's; decisions here are synthetic inputs used to prove the
validator's rules, and they never touch the project's own screening files.
"""
import csv

import pytest
import yaml

from scripts.common import config
from scripts.common.config import PipelineError
from scripts.screening import prisma, validate_screening, vocabulary, worksheet
from scripts.screening.vocabulary import EXCLUDE, FT, INCLUDE, TA, UNRESOLVED


# --- vocabulary ----------------------------------------------------------------------

def test_project_vocabulary_loads():
    vocab = vocabulary.load_vocabulary()
    assert {INCLUDE, EXCLUDE, UNRESOLVED} <= set(vocab.decisions)
    assert "unavailable" in vocab.retrieval_statuses
    assert len(vocab.reasons) >= 10


def test_vocabulary_matches_the_protocol_document():
    """The config and docs/protocol/eligibility_criteria.md must not drift apart."""
    doc = (config.ROOT / "docs" / "protocol" / "eligibility_criteria.md").read_text(encoding="utf-8")
    documented = set()
    for line in doc.splitlines():
        if line.startswith("| `") and "`" in line[3:]:
            documented.add(line.split("`")[1])
    coded = set(vocabulary.load_vocabulary().codes())

    # full_text_unavailable is documented as a retrieval status, not an exclusion reason.
    assert documented - {"full_text_unavailable"} == coded, (
        f"documented-only: {sorted(documented - {'full_text_unavailable'} - coded)}; "
        f"config-only: {sorted(coded - documented)}"
    )


def test_full_text_unavailable_is_a_retrieval_status_not_a_reason():
    vocab = vocabulary.load_vocabulary()
    assert "full_text_unavailable" not in vocab.codes()


def test_stage_restrictions_are_asymmetric():
    vocab = vocabulary.load_vocabulary()
    ta, ft = set(vocab.codes(TA)), set(vocab.codes(FT))
    assert ta < ft, "every title/abstract reason must also be valid at full text"
    assert {"no_reference_group", "no_usable_data", "outcome_not_separable",
            "duplicate_publication"} <= (ft - ta), \
        "reasons needing the methods section must not be available at title/abstract"


@pytest.mark.parametrize("bad", [
    {"reasons": [{"code": "a", "description": "d", "stages": []}]},
    {"reasons": [{"code": "a", "description": "d", "stages": ["nowhere"]}]},
    {"reasons": [{"code": "a", "description": "d", "stages": ["ta"]},
                 {"code": "a", "description": "d2", "stages": ["ft"]}]},
])
def test_malformed_vocabulary_is_rejected(tmp_path, monkeypatch, bad):
    path = tmp_path / "screening.yaml"
    path.write_text(yaml.safe_dump({
        "decisions": ["include", "exclude", "unresolved"],
        "retrieval_statuses": ["sought", "retrieved", "unavailable"], **bad}), encoding="utf-8")
    monkeypatch.setattr(vocabulary, "SCREENING_CONFIG", path)
    with pytest.raises(PipelineError):
        vocabulary.load_vocabulary()


def test_vocabulary_requires_the_three_decisions(tmp_path, monkeypatch):
    path = tmp_path / "screening.yaml"
    path.write_text(yaml.safe_dump({
        "decisions": ["include", "exclude"],          # 'unresolved' missing
        "retrieval_statuses": ["sought"],
        "reasons": [{"code": "a", "description": "d", "stages": ["ta"]}]}), encoding="utf-8")
    monkeypatch.setattr(vocabulary, "SCREENING_CONFIG", path)
    with pytest.raises(PipelineError, match="unresolved"):
        vocabulary.load_vocabulary()


# --- validation rules ----------------------------------------------------------------

def src_row(report_id, pmid="1", title="t"):
    return {"report_id": report_id, "pmid": pmid, "title": title}


def ws_row(report_id, pmid="1", title="t", decision="", reason="", reviewer="", notes="",
           status=""):
    return {"report_id": report_id, "pmid": pmid, "title": title, "decision": decision,
            "reason_code": reason, "reviewer": reviewer, "notes": notes,
            "full_text_status": status}


def check(rows, source=None, stage=TA):
    return validate_screening.check(rows, source or [src_row(r["report_id"]) for r in rows], stage)


def test_unscreened_worksheet_passes_with_a_progress_warning():
    f = check([ws_row("R0001"), ws_row("R0002")])
    assert f.errors == []
    assert any("not yet screened" in w for w in f.warnings)


def test_valid_decisions_are_accepted():
    f = check([
        ws_row("R0001", decision=INCLUDE, reviewer="SSK"),
        ws_row("R0002", decision=EXCLUDE, reason="review_or_meta", reviewer="SSK"),
        ws_row("R0003", decision=UNRESOLVED, reviewer="SSK"),
    ])
    assert f.errors == []


def test_unknown_decision_is_an_error():
    f = check([ws_row("R0001", decision="maybe", reviewer="SSK")])
    assert any("unknown decision" in e for e in f.errors)


def test_exclusion_without_a_reason_is_an_error():
    f = check([ws_row("R0001", decision=EXCLUDE, reviewer="SSK")])
    assert any("no reason_code" in e for e in f.errors)


def test_unknown_reason_code_is_an_error():
    f = check([ws_row("R0001", decision=EXCLUDE, reason="not_a_code", reviewer="SSK")])
    assert any("unknown reason_code" in e for e in f.errors)


def test_full_text_reason_is_refused_at_title_abstract():
    f = check([ws_row("R0001", decision=EXCLUDE, reason="no_reference_group", reviewer="SSK")], stage=TA)
    assert any("not permitted at title/abstract" in e for e in f.errors)


def test_same_reason_is_accepted_at_full_text():
    f = validate_screening.check(
        [ws_row("R0001", decision=EXCLUDE, reason="no_reference_group", reviewer="SSK",
                status="retrieved")],
        [src_row("R0001")], FT)
    assert f.errors == []


def test_reason_on_an_inclusion_is_an_error():
    f = check([ws_row("R0001", decision=INCLUDE, reason="wrong_design", reviewer="SSK")])
    assert any("belong only to exclusions" in e for e in f.errors)


def test_decision_without_a_reviewer_is_an_error():
    f = check([ws_row("R0001", decision=INCLUDE)])
    assert any("no reviewer" in e for e in f.errors)


def test_other_requires_a_written_justification():
    f = check([ws_row("R0001", decision=EXCLUDE, reason="other", reviewer="SSK")])
    assert any("requires a written justification" in e for e in f.errors)
    ok = check([ws_row("R0001", decision=EXCLUDE, reason="other", reviewer="SSK", notes="why")])
    assert ok.errors == []


def test_retrieval_status_cannot_be_used_as_an_exclusion_reason():
    f = validate_screening.check(
        [ws_row("R0001", decision=EXCLUDE, reason="full_text_unavailable", reviewer="SSK")],
        [src_row("R0001")], FT)
    assert any("not an exclusion reason" in e for e in f.errors)


def test_unavailable_full_text_cannot_carry_a_decision():
    f = validate_screening.check(
        [ws_row("R0001", decision=EXCLUDE, reason="wrong_design", reviewer="SSK",
                status="unavailable")],
        [src_row("R0001")], FT)
    assert any("no eligibility decision can be made" in e for e in f.errors)


def test_unknown_full_text_status_is_an_error():
    f = validate_screening.check([ws_row("R0001", status="maybe")], [src_row("R0001")], FT)
    assert any("unknown full_text_status" in e for e in f.errors)


def test_unresolved_records_are_warned_about():
    f = check([ws_row("R0001", decision=UNRESOLVED, reviewer="SSK")])
    assert any("unresolved" in w for w in f.warnings)


# --- identifier integrity ------------------------------------------------------------

def test_duplicate_report_id_is_an_error():
    f = check([ws_row("R0001"), ws_row("R0001")])
    assert any("duplicate report_id" in e for e in f.errors)


def test_deleted_rows_are_detected():
    f = validate_screening.check([ws_row("R0001")], [src_row("R0001"), src_row("R0002")], TA)
    assert any("missing from the worksheet" in e for e in f.errors)


def test_added_rows_are_detected():
    f = validate_screening.check([ws_row("R0001"), ws_row("R9999")], [src_row("R0001")], TA)
    assert any("not in the source set" in e for e in f.errors)


def test_edited_derived_column_is_detected():
    """Guards against spreadsheet re-import mangling identifiers or titles."""
    f = validate_screening.check([ws_row("R0001", pmid="999")], [src_row("R0001", pmid="1")], TA)
    assert any("derived column 'pmid' differs" in e for e in f.errors)


def test_empty_worksheet_is_handled():
    f = validate_screening.check([], [], TA)
    assert f.errors == []
    assert any("reports in worksheet: 0" in i for i in f.info)


# --- worksheet generation, end to end ------------------------------------------------

@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A processed-data tree with two unique reports, one of them a duplicate group."""
    processed = tmp_path / "data" / "processed"
    (processed / "citations").mkdir(parents=True)
    (processed / "dedup").mkdir(parents=True)
    monkeypatch.setattr(worksheet, "PROCESSED_DIR", processed)
    monkeypatch.setattr(worksheet, "SCREENING_DIR", tmp_path / "data" / "screening")
    monkeypatch.setattr(prisma, "PROCESSED_DIR", processed)
    monkeypatch.setattr(prisma, "VALIDATION_DIR", tmp_path / "results" / "validation")
    monkeypatch.setattr(validate_screening, "VALIDATION_DIR", tmp_path / "results" / "validation")
    # Provenance is verified by the dedup stage; bypassing it here would not be a screening test.
    monkeypatch.setattr(worksheet, "verify_provenance", lambda source_id: "0" * 64)

    def write(name, rows, fields=None):
        path = processed / name
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields or list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    write("citations/src_citations.csv", [
        {"record_id": "src:1", "journal": "J1", "publication_types": "Journal Article",
         "abstract": "abstract one"},
        {"record_id": "src:2", "journal": "J2", "publication_types": "Review",
         "abstract": "abstract two"},
    ])
    write("dedup/report_index.csv", [
        {"record_id": "src:1", "source_id": "src", "report_id": "R0001", "is_primary": "yes",
         "pmid": "11", "doi": "10.1/a", "pub_year": "2001", "first_author": "A, B", "title": "t1"},
        {"record_id": "src:2", "source_id": "src", "report_id": "R0002", "is_primary": "yes",
         "pmid": "22", "doi": "", "pub_year": "2002", "first_author": "C, D", "title": "t2"},
    ])
    return tmp_path


def test_worksheet_is_generated_with_no_decisions(sandbox):
    result = worksheet.build(TA)
    rows = worksheet.read_csv(worksheet.worksheet_path(TA))

    assert result["rows"] == 2 and result["added"] == 2
    assert [r["report_id"] for r in rows] == ["R0001", "R0002"]
    for r in rows:
        assert r["decision"] == "" and r["reason_code"] == "" and r["reviewer"] == "", \
            "the generator must never record a decision (D010)"


def test_worksheet_preserves_citation_information(sandbox):
    worksheet.build(TA)
    rows = {r["report_id"]: r for r in worksheet.read_csv(worksheet.worksheet_path(TA))}
    assert rows["R0001"]["pmid"] == "11" and rows["R0001"]["title"] == "t1"
    assert rows["R0001"]["abstract"] == "abstract one"
    assert rows["R0002"]["publication_types"] == "Review"
    assert rows["R0002"]["doi"] == ""


def test_generation_refuses_to_overwrite_an_existing_worksheet(sandbox):
    worksheet.build(TA)
    with pytest.raises(PipelineError, match="not overwritten"):
        worksheet.build(TA)


def test_refresh_preserves_recorded_decisions(sandbox):
    worksheet.build(TA)
    path = worksheet.worksheet_path(TA)
    rows = worksheet.read_csv(path)
    rows[0].update(decision=EXCLUDE, reason_code="review_or_meta", reviewer="SSK",
                   screened_date="2026-11-01", notes="n")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    result = worksheet.build(TA, refresh=True)
    after = {r["report_id"]: r for r in worksheet.read_csv(path)}

    assert result["decisions_carried"] == 1
    assert after["R0001"]["decision"] == EXCLUDE
    assert after["R0001"]["reason_code"] == "review_or_meta"
    assert after["R0001"]["reviewer"] == "SSK" and after["R0001"]["notes"] == "n"
    assert after["R0002"]["decision"] == ""


def test_refresh_adds_new_reports_without_disturbing_old_ones(sandbox):
    worksheet.build(TA)
    index = worksheet.PROCESSED_DIR / "dedup" / "report_index.csv"
    rows = worksheet.read_csv(index)
    rows.append({**rows[0], "record_id": "src:3", "report_id": "R0003", "pmid": "33",
                 "title": "t3"})
    with open(index, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    result = worksheet.build(TA, refresh=True)
    assert result["rows"] == 3 and result["added"] == 1


def test_refresh_refuses_to_discard_a_decision_for_a_vanished_report(sandbox):
    worksheet.build(TA)
    path = worksheet.worksheet_path(TA)
    rows = worksheet.read_csv(path)
    rows[1].update(decision=INCLUDE, reviewer="SSK")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    index = worksheet.PROCESSED_DIR / "dedup" / "report_index.csv"
    kept = [r for r in worksheet.read_csv(index) if r["report_id"] != "R0002"]
    with open(index, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(kept[0]))
        w.writeheader()
        w.writerows(kept)

    with pytest.raises(PipelineError, match="would discard recorded work"):
        worksheet.build(TA, refresh=True)


def test_worksheet_generation_does_not_modify_source_data(sandbox):
    index = worksheet.PROCESSED_DIR / "dedup" / "report_index.csv"
    citations = worksheet.PROCESSED_DIR / "citations" / "src_citations.csv"
    before = (index.read_bytes(), citations.read_bytes())
    worksheet.build(TA)
    assert (index.read_bytes(), citations.read_bytes()) == before


def test_full_text_worksheet_contains_only_title_abstract_includes(sandbox):
    worksheet.build(TA)
    path = worksheet.worksheet_path(TA)
    rows = worksheet.read_csv(path)
    rows[0].update(decision=INCLUDE, reviewer="SSK")
    rows[1].update(decision=EXCLUDE, reason_code="review_or_meta", reviewer="SSK")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    worksheet.build(FT)
    ft = worksheet.read_csv(worksheet.worksheet_path(FT))
    assert [r["report_id"] for r in ft] == ["R0001"]
    assert ft[0]["full_text_status"] == "" and ft[0]["decision"] == ""


def test_full_text_worksheet_requires_the_title_abstract_stage_first(sandbox):
    with pytest.raises(PipelineError, match="no includes to carry forward"):
        worksheet.build(FT)


def test_missing_report_index_is_refused(sandbox):
    (worksheet.PROCESSED_DIR / "dedup" / "report_index.csv").unlink()
    with pytest.raises(PipelineError, match="Run scripts.dedup.deduplicate first"):
        worksheet.build(TA)


def test_missing_citations_file_is_refused(sandbox):
    (worksheet.PROCESSED_DIR / "citations" / "src_citations.csv").unlink()
    with pytest.raises(PipelineError, match="not found"):
        worksheet.build(TA)


# --- PRISMA accounting ---------------------------------------------------------------

def test_prisma_marks_unrun_stages_pending_not_zero(sandbox, monkeypatch):
    monkeypatch.setattr(prisma, "load_sources", lambda: [])
    monkeypatch.setattr(prisma.worksheet, "worksheet_path",
                        lambda stage: sandbox / "data" / "screening" / f"screening_{stage}.csv")
    flow = prisma.gather()

    assert flow["duplicates_removed"] == 0 and flow["unique_reports"] == 2
    assert flow["ta_screened"] == prisma.PENDING, "an unrun stage is pending, not zero"
    assert flow["included_studies"] == prisma.PENDING
    assert prisma.consistency(flow) == []


def test_prisma_counts_awaiting_screening_separately(sandbox, monkeypatch):
    monkeypatch.setattr(prisma, "load_sources", lambda: [])
    monkeypatch.setattr(prisma.worksheet, "worksheet_path",
                        lambda stage: sandbox / "data" / "screening" / f"screening_{stage}.csv")
    worksheet.build(TA)
    path = worksheet.worksheet_path(TA)
    rows = worksheet.read_csv(path)
    rows[0].update(decision=EXCLUDE, reason_code="review_or_meta", reviewer="SSK")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    flow = prisma.gather()
    assert flow["ta_total"] == 2 and flow["ta_screened"] == 1
    assert flow["ta_unscreened"] == 1 and flow["ta_excluded"] == 1 and flow["ta_included"] == 0
    assert prisma.consistency(flow) == []


def test_prisma_detects_an_unreconcilable_flow():
    flow = {"identified": 100, "duplicates_removed": 5, "unique_reports": 90,
            "ta_reasons": {}, "ft_reasons": {}, "ft_exists": False}
    assert any("does not equal unique reports" in p for p in prisma.consistency(flow))


def test_prisma_detects_reasons_not_matching_exclusions():
    flow = {"ft_excluded": 3, "ft_reasons": {"wrong_design": 1}, "ta_reasons": {},
            "ft_exists": True}
    assert any("every exclusion needs exactly one reason" in p for p in prisma.consistency(flow))


@pytest.mark.parametrize("total,screened,expect", [
    (None, None, "NOT STARTED"),
    (194, 0, "NOT SCREENED"),
    (194, 50, "IN PROGRESS"),
    (194, 194, "TITLE/ABSTRACT COMPLETE"),
])
def test_prisma_banner_cannot_be_mistaken_for_a_finding(total, screened, expect):
    banner = prisma.screening_banner({"ta_total": total, "ta_screened": screened})
    assert expect in banner
    if expect == "NOT SCREENED":
        assert "not** because nothing was eligible" in banner


def test_prisma_rejects_more_sought_than_included():
    flow = {"ta_included": 2, "ft_sought": 5, "ta_reasons": {}, "ft_reasons": {},
            "ft_exists": True}
    assert any("exceeds title/abstract includes" in p for p in prisma.consistency(flow))
