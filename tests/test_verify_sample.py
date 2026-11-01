"""Blinded verification of a sample of recorded title/abstract decisions.

Rows are structural stubs with no bibliographic content (D007). Decisions here are synthetic
inputs used to exercise the agreement arithmetic and the pre-specified acceptance rule; none is
presented as a reviewer's judgement, and no test writes to the project's own worksheet.
"""
import csv
import hashlib

import pytest

from scripts.common.config import PipelineError
from scripts.screening import verify_sample, worksheet
from scripts.screening.verify_sample import (ADOPT_AT, EXTEND_AT, RESPONSE, SHEET_FIELDS, build_sheet,
                                             draw, kappa, score, seed_from, verdict)
from scripts.screening.vocabulary import EXCLUDE, INCLUDE, TA, UNRESOLVED

FIELDS = worksheet.FIELDS[TA]


def ta_row(n, decision="", reason=""):
    r = {f: "" for f in FIELDS}
    r.update({"report_id": f"R{n:04d}", "record_id": f"rec-{n:04d}", "source_id": "stub_v1",
              "pmid": f"{9000000 + n}", "pub_year": "2000", "first_author": f"Author{n}",
              "journal": "Journal", "publication_types": "Journal Article",
              "title": f"Title {n}", "abstract": f"Abstract {n}",
              "decision": decision, "reason_code": reason,
              "reviewer": "SSK" if decision else "", "screened_date": "2026-11-01" if decision else ""})
    return r


def population(n_exclude=60, n_include=40, reason="wrong_outcome"):
    rows = [ta_row(i, EXCLUDE, reason) for i in range(1, n_exclude + 1)]
    rows += [ta_row(i, INCLUDE) for i in range(n_exclude + 1, n_exclude + n_include + 1)]
    return rows


def sheet_from(ta_rows, reviewer_decisions):
    """A completed sheet: reviewer_decisions maps report_id -> (decision, reason)."""
    out = []
    for r in ta_rows:
        d, reason = reviewer_decisions[r["report_id"]]
        entry = {f: "" for f in SHEET_FIELDS}
        entry.update({"report_id": r["report_id"], "title": r["title"],
                      "your_decision": d, "your_reason_code": reason})
        out.append(entry)
    return out


def as_recorded(ta_rows, flip=0, direction="exclude_to_include"):
    """Reviewer agrees with every record except `flip` of them, in the stated direction."""
    out, flipped = {}, 0
    for r in ta_rows:
        d, reason = r["decision"], r["reason_code"]
        if flipped < flip:
            if direction == "exclude_to_include" and d == EXCLUDE:
                d, reason, flipped = INCLUDE, "", flipped + 1
            elif direction == "include_to_exclude" and d == INCLUDE:
                d, reason, flipped = EXCLUDE, "wrong_design", flipped + 1
        out[r["report_id"]] = (d, reason)
    assert flipped == flip, "fixture could not flip the requested number"
    return out


# --- the draw is reproducible and unchosen ---------------------------------------------

def test_the_seed_is_derived_from_the_worksheet_not_chosen():
    assert seed_from("5938922a529a7f73") == 0x5938922a == 1496879658
    assert seed_from("00000001ffff") == 1


def test_the_same_worksheet_always_draws_the_same_sample():
    rows = population()
    a = [r["report_id"] for r in draw(rows, 40, 1496879658)]
    b = [r["report_id"] for r in draw(rows, 40, 1496879658)]
    assert a == b and len(a) == 40


def test_a_different_seed_draws_a_different_sample():
    rows = population()
    a = {r["report_id"] for r in draw(rows, 40, 1)}
    b = {r["report_id"] for r in draw(rows, 40, 2)}
    assert a != b


def test_the_sample_is_returned_in_worksheet_order_and_without_repeats():
    ids = [r["report_id"] for r in draw(population(), 40, 7)]
    assert ids == sorted(ids) and len(set(ids)) == 40


@pytest.mark.parametrize("size", [0, -1, 101])
def test_an_impossible_sample_size_is_refused(size):
    with pytest.raises(PipelineError):
        draw(population(), size, 1)


# --- the instrument is genuinely blinded ------------------------------------------------

def test_the_sheet_carries_no_recorded_decision():
    """If the reviewer can see the recorded decision, this confirms rather than verifies."""
    sample = draw(population(), 40, 1496879658)
    sheet = build_sheet(sample, {})
    for leak in ("decision", "reason_code", "reviewer", "screened_date", "notes"):
        assert leak not in sheet[0], f"{leak} must not appear in the blinded sheet"
    joined = " ".join(v for row in sheet for v in row.values())
    assert EXCLUDE not in joined and INCLUDE not in joined
    assert all(row[f] == "" for row in sheet for f in RESPONSE)


def test_the_sheet_shows_what_the_reviewer_needs_to_judge():
    sheet = build_sheet([ta_row(1, EXCLUDE, "wrong_outcome")], {"rec-0001": "eng"})
    assert sheet[0]["title"] == "Title 1" and sheet[0]["abstract"] == "Abstract 1"
    assert sheet[0]["publication_types"] == "Journal Article"
    assert sheet[0]["language"] == "eng", "language is needed to judge not_english"


# --- agreement arithmetic ----------------------------------------------------------------

def test_kappa_matches_a_hand_worked_value():
    """5 (exc,exc) + 1 (exc,inc) + 4 (inc,inc): po=0.9, pe=0.5, kappa=0.8."""
    pairs = [(EXCLUDE, EXCLUDE)] * 5 + [(EXCLUDE, INCLUDE)] + [(INCLUDE, INCLUDE)] * 4
    assert kappa(pairs) == pytest.approx(0.8)


def test_kappa_is_undefined_rather_than_zero_without_variation():
    """Both raters excluding everything gives 0/0; reporting 0.0 would read as chance agreement."""
    assert kappa([(EXCLUDE, EXCLUDE)] * 40) is None
    assert kappa([]) is None


@pytest.mark.parametrize("rate,expected", [
    (1.0, "ADOPT"), (ADOPT_AT, "ADOPT"), (0.949, "EXTEND"),
    (EXTEND_AT, "EXTEND"), (0.899, "RE-SCREEN"), (0.0, "RE-SCREEN"),
])
def test_the_acceptance_rule_is_applied_as_pre_specified(rate, expected):
    assert verdict(rate) == expected


def test_full_agreement_adopts_the_remainder():
    rows = population()
    sample = draw(rows, 40, 1496879658)
    result = score(sheet_from(sample, as_recorded(sample)), rows)
    assert result["agreed"] == 40 and result["rate"] == 1.0
    assert result["verdict"] == "ADOPT" and result["discrepancies"] == []


def test_two_discrepancies_in_forty_still_adopts():
    rows = population()
    sample = draw(rows, 40, 1496879658)
    result = score(sheet_from(sample, as_recorded(sample, flip=2)), rows)
    assert result["rate"] == pytest.approx(0.95) and result["verdict"] == "ADOPT"


def test_three_discrepancies_extends_the_sample():
    rows = population()
    sample = draw(rows, 40, 1496879658)
    result = score(sheet_from(sample, as_recorded(sample, flip=3)), rows)
    assert result["rate"] == pytest.approx(0.925) and result["verdict"] == "EXTEND"


def test_five_discrepancies_forces_a_full_re_screen():
    rows = population()
    sample = draw(rows, 40, 1496879658)
    result = score(sheet_from(sample, as_recorded(sample, flip=5)), rows)
    assert result["rate"] == pytest.approx(0.875) and result["verdict"] == "RE-SCREEN"


# --- the asymmetry rule -------------------------------------------------------------------

def test_an_erroneous_exclusion_triggers_a_sweep_of_that_reason_code():
    rows = population(reason="wrong_outcome")
    sample = draw(rows, 40, 1496879658)
    result = score(sheet_from(sample, as_recorded(sample, flip=1)), rows)
    assert result["sweeps"] == ["wrong_outcome"]
    assert result["sweep_sizes"]["wrong_outcome"] == 60, "every record with that reason"
    assert "evidence lost" in verify_sample.render(result, 1, "x" * 64)


def test_the_opposite_direction_triggers_no_sweep():
    """Including something the reviewer would exclude costs retrieval effort, not evidence."""
    rows = population()
    sample = draw(rows, 40, 1496879658)
    result = score(sheet_from(sample, as_recorded(sample, flip=1,
                                                  direction="include_to_exclude")), rows)
    assert result["discrepancies"] and result["sweeps"] == []
    assert "Not triggered" in verify_sample.render(result, 1, "x" * 64)


def test_reason_code_disagreement_is_reported_without_changing_the_decision_rate():
    rows = population()
    sample = draw(rows, 40, 1496879658)
    responses = as_recorded(sample)
    rid = next(r["report_id"] for r in sample if r["decision"] == EXCLUDE)
    responses[rid] = (EXCLUDE, "wrong_design")
    result = score(sheet_from(sample, responses), rows)
    assert result["rate"] == 1.0, "the decision still agrees"
    assert result["reason_discrepancies"] == [(rid, "wrong_outcome", "wrong_design")]


# --- the completed sheet must be valid before it is scored ---------------------------------

def test_an_unanswered_row_is_refused():
    rows = population()
    sample = draw(rows, 40, 1496879658)
    sheet = sheet_from(sample, as_recorded(sample))
    sheet[0]["your_decision"] = ""
    with pytest.raises(PipelineError, match="no your_decision"):
        score(sheet, rows)


@pytest.mark.parametrize("decision,reason,match", [
    ("maybe", "", "not a decision value"),
    (EXCLUDE, "", "no reason code"),
    (EXCLUDE, "no_usable_data", "not permitted at title/abstract"),
    (INCLUDE, "wrong_outcome", "reason code recorded on a non-exclusion"),
])
def test_an_invalid_judgement_is_refused(decision, reason, match):
    rows = population()
    sample = draw(rows, 40, 1496879658)
    sheet = sheet_from(sample, as_recorded(sample))
    sheet[0].update(your_decision=decision, your_reason_code=reason)
    with pytest.raises(PipelineError, match=match):
        score(sheet, rows)


def test_unresolved_is_an_acceptable_judgement():
    rows = population()
    sample = draw(rows, 40, 1496879658)
    responses = as_recorded(sample)
    rid = sample[0]["report_id"]
    responses[rid] = (UNRESOLVED, "")
    result = score(sheet_from(sample, responses), rows)
    assert result["agreed"] == 39 and result["sweeps"] == []


def test_a_report_outside_the_worksheet_is_refused():
    rows = population()
    sample = draw(rows, 40, 1496879658)
    sheet = sheet_from(sample, as_recorded(sample))
    sheet[0]["report_id"] = "R9999"
    with pytest.raises(PipelineError, match="not in the title/abstract worksheet"):
        score(sheet, rows)


# --- the CLI never touches the recorded decisions -------------------------------------------

@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    screening = tmp_path / "data" / "screening"
    screening.mkdir(parents=True)
    monkeypatch.setattr(worksheet, "SCREENING_DIR", screening)
    monkeypatch.setattr(verify_sample, "VALIDATION_DIR", tmp_path / "results" / "validation")
    path = worksheet.worksheet_path(TA)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(population())
    return path


def test_drawing_does_not_alter_the_worksheet(sandbox, capsys):
    before = hashlib.sha256(sandbox.read_bytes()).hexdigest()
    assert verify_sample.main(["--draw"]) == 0
    assert hashlib.sha256(sandbox.read_bytes()).hexdigest() == before
    sheet = list(csv.DictReader(open(verify_sample.sheet_path(), encoding="utf-8", newline="")))
    assert len(sheet) == 40 and "decision" not in sheet[0]
    capsys.readouterr()


def test_drawing_refuses_to_overwrite_a_sheet_that_may_hold_judgements(sandbox, capsys):
    assert verify_sample.main(["--draw"]) == 0
    assert verify_sample.main(["--draw"]) == 1
    assert "not overwritten" in capsys.readouterr().err


def test_scoring_before_drawing_fails(sandbox, capsys):
    assert verify_sample.main(["--score"]) == 1
    assert "Run --draw first" in capsys.readouterr().err


def test_scoring_writes_a_report_and_leaves_the_worksheet_alone(sandbox, capsys):
    before = hashlib.sha256(sandbox.read_bytes()).hexdigest()
    verify_sample.main(["--draw"])
    path = verify_sample.sheet_path()
    rows = list(csv.DictReader(open(path, encoding="utf-8", newline="")))
    ta = {r["report_id"]: r for r in population()}
    for r in rows:
        rec = ta[r["report_id"]]
        r["your_decision"], r["your_reason_code"] = rec["decision"], rec["reason_code"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SHEET_FIELDS)
        w.writeheader()
        w.writerows(rows)

    assert verify_sample.main(["--score"]) == 0
    assert hashlib.sha256(sandbox.read_bytes()).hexdigest() == before
    report = (verify_sample.VALIDATION_DIR / "screening_verification.md").read_text(encoding="utf-8")
    assert "**Verdict: ADOPT**" in report
    assert "not** independent duplicate screening" in report
    capsys.readouterr()


def test_the_report_distinguishes_suggestions_decisions_sample_and_agreement():
    """The reader must not be able to mistake this for inter-reviewer agreement."""
    rows = population()
    sample = draw(rows, 40, 1496879658)
    report = verify_sample.render(score(sheet_from(sample, as_recorded(sample)), rows), 1, "x" * 64)
    for term in ("**Automated suggestion**", "**Human reviewer decision**",
                 "**Blinded verification sample**", "**Agreement**"):
        assert term in report
    assert "not a reference standard" in report
    assert "not** inter-reviewer agreement" in report
    assert "not** treat the suggestions as ground truth" in report
