"""The screening batch-display CLI: selection, read-only guarantees and rendering.

Rows are structural stubs with no bibliographic content (D007). Where a row carries a `decision`
it is a synthetic input used to prove that an already-recorded decision is *displayed*; no test
asserts, produces or implies a reviewer's judgement, and none touches the project's own worksheet
other than to read it.
"""
import csv
import hashlib
import json

import pytest

from scripts.common.config import PipelineError
from scripts.screening import show, worksheet
from scripts.screening.show import NOT_RECORDED, load_languages, render_json, render_text, select
from scripts.screening.vocabulary import TA

FIELDS = worksheet.FIELDS[TA]


def row(n, **over):
    """A structurally complete worksheet row with no bibliographic content."""
    r = {f: "" for f in FIELDS}
    r.update({
        "report_id": f"R{n:04d}", "record_id": f"rec-{n:04d}", "source_id": "stub_v1",
        "pmid": f"{9000000 + n}", "pub_year": "2000", "first_author": f"Author{n}",
        "journal": "Journal", "publication_types": "Journal Article",
        "title": f"Title {n}", "abstract": f"Abstract {n}",
    })
    r.update(over)
    return r


def rows(n=50, **decided):
    """n rows; `decided` maps a 1-based position to a decision value."""
    out = [row(i) for i in range(1, n + 1)]
    for pos, decision in decided.items():
        out[int(pos) - 1]["decision"] = decision
    return out


@pytest.fixture
def sheet(tmp_path, monkeypatch):
    """An isolated screening directory plus citation tree, and a writer for both."""
    screening = tmp_path / "data" / "screening"
    screening.mkdir(parents=True)
    citations = tmp_path / "data" / "processed" / "citations"
    monkeypatch.setattr(worksheet, "SCREENING_DIR", screening)
    monkeypatch.setattr(show, "PROCESSED_DIR", citations.parent)

    def write(records, languages=None):
        path = worksheet.worksheet_path(TA)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(records)
        if languages is not None:
            citations.mkdir(parents=True, exist_ok=True)
            with open(citations / "stub_v1_citations.csv", "w", encoding="utf-8",
                      newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=["record_id", "languages"])
                w.writeheader()
                w.writerows({"record_id": k, "languages": v} for k, v in languages.items())
        return path

    return write


def bundle(records, languages=None, start=1, size=20, unscreened_only=False):
    """The four arguments the renderers take, for a given set of rows."""
    batch, meta = select(records, start, size, unscreened_only)
    languages = languages or {}
    return batch, meta, languages, show.warnings_for(batch, languages)


# --- selection -------------------------------------------------------------------------

def test_first_batch_is_the_first_size_records_in_worksheet_order():
    batch, meta = select(rows(50), start=1, size=20)
    assert [r["report_id"] for r in batch] == [f"R{i:04d}" for i in range(1, 21)]
    assert (meta["batch_number"], meta["range_start"], meta["range_end"]) == (1, 1, 20)


def test_second_batch_continues_without_overlap_or_gap():
    first, _ = select(rows(50), start=1, size=20)
    second, meta = select(rows(50), start=21, size=20)
    assert [r["report_id"] for r in second] == [f"R{i:04d}" for i in range(21, 41)]
    assert not ({r["report_id"] for r in first} & {r["report_id"] for r in second})
    assert meta["batch_number"] == 2


def test_a_short_final_batch_reports_its_true_range():
    batch, meta = select(rows(50), start=41, size=20)
    assert len(batch) == 10
    assert (meta["batch_number"], meta["range_start"], meta["range_end"]) == (3, 41, 50)


def test_selection_never_reorders_or_sorts_records():
    """Order is the worksheet's. Sorting would renumber batches between runs."""
    shuffled = [row(9), row(3), row(41), row(1)]
    batch, _ = select(shuffled, start=1, size=4)
    assert [r["report_id"] for r in batch] == ["R0009", "R0003", "R0041", "R0001"]


def test_metadata_reports_total_screened_and_remaining():
    _, meta = select(rows(50, **{"1": "include", "2": "exclude"}), start=1, size=20)
    assert (meta["total_records"], meta["screened"], meta["remaining"]) == (50, 2, 48)


# --- unscreened-only -------------------------------------------------------------------

def test_unscreened_only_skips_records_that_already_have_a_decision():
    batch, meta = select(rows(50, **{"1": "include", "3": "exclude"}),
                         start=1, size=5, unscreened_only=True)
    assert [r["report_id"] for r in batch] == ["R0002", "R0004", "R0005", "R0006", "R0007"]
    assert meta["pool_size"] == 48
    assert meta["total_records"] == 50, "the dataset total is not reduced by the filter"


def test_unscreened_only_treats_whitespace_as_no_decision():
    batch, _ = select(rows(5, **{"1": "   "}), start=1, size=5, unscreened_only=True)
    assert len(batch) == 5


# --- argument validation ---------------------------------------------------------------

@pytest.mark.parametrize("start,size", [(0, 20), (-1, 20), (1, 0), (1, -5)])
def test_out_of_range_arguments_are_refused(start, size):
    with pytest.raises(PipelineError):
        select(rows(50), start=start, size=size)


def test_a_start_beyond_the_last_record_is_refused_rather_than_shown_as_empty():
    with pytest.raises(PipelineError, match="beyond"):
        select(rows(50), start=51, size=20)


def test_a_start_beyond_the_unscreened_pool_says_so():
    with pytest.raises(PipelineError, match="unscreened"):
        select(rows(5, **{"2": "include", "3": "include", "4": "include", "5": "include"}),
               start=3, size=20, unscreened_only=True)


def test_non_integer_arguments_are_rejected_by_the_parser(sheet):
    sheet(rows(5))
    with pytest.raises(SystemExit):
        show.main(["--start", "abc"])


def test_an_unknown_format_is_rejected(sheet):
    sheet(rows(5))
    with pytest.raises(SystemExit):
        show.main(["--format", "xml"])


# --- decisions are displayed, never produced -------------------------------------------

def test_an_unscreened_record_is_labelled_as_not_yet_screened():
    assert show.decision_line(row(1)) == NOT_RECORDED


def test_a_recorded_decision_is_shown_with_its_audit_fields():
    line = show.decision_line(row(1, decision="exclude", reason_code="wrong_outcome",
                                  reviewer="SSK", screened_date="2026-10-31", notes="see p.3"))
    for part in ("exclude", "wrong_outcome", "SSK", "2026-10-31", "see p.3"):
        assert part in line


def test_the_rendered_batch_carries_no_suggestion_or_recommendation():
    """Eligibility is the reviewer's (D010); the display must not hint at an answer."""
    body = render_text(*bundle(rows(20))).lower()
    for word in ("suggest", "recommend", "likely eligible", "probably", "should include",
                 "should exclude"):
        assert word not in body


# --- missing metadata ------------------------------------------------------------------

def test_a_record_with_no_abstract_is_warned_about_and_still_displayed():
    batch, meta, lang, warns = bundle([row(1, abstract=""), row(2)])
    assert any("no abstract" in w and "R0001" in w for w in warns)
    body = render_text(batch, meta, lang, warns)
    assert "R0001" in body and "no abstract" in body


@pytest.mark.parametrize("field", ["pmid", "title", "pub_year", "first_author", "journal"])
def test_each_missing_metadata_field_is_warned_about(field):
    *_, warns = bundle([row(1, **{field: ""})])
    assert any(field in w and "R0001" in w for w in warns)


def test_a_complete_batch_with_languages_produces_no_warnings():
    *_, warns = bundle([row(1)], languages={"rec-0001": "eng"})
    assert warns == []


def test_an_absent_citation_dataset_is_reported_rather_than_guessed():
    """`languages` is not a worksheet column; if the join source is gone, say so."""
    batch, meta, lang, warns = bundle([row(1)])
    assert any("unavailable" in w for w in warns)
    assert "unavailable" in render_text(batch, meta, lang, warns)


def test_a_record_missing_only_its_language_tag_is_named():
    *_, warns = bundle([row(1), row(2)], languages={"rec-0001": "eng", "rec-0002": ""})
    assert any("language tag" in w and "R0002" in w for w in warns)


def test_language_is_joined_onto_the_matching_record(sheet):
    sheet([row(1)], languages={"rec-0001": "chi"})
    assert load_languages(show.PROCESSED_DIR / "citations") == {"rec-0001": "chi"}


def test_language_lookup_is_empty_when_the_directory_does_not_exist(tmp_path):
    assert load_languages(tmp_path / "absent") == {}


# --- rendering -------------------------------------------------------------------------

def test_the_text_header_states_the_batch_range_and_dataset_progress():
    body = render_text(*bundle(rows(50, **{"1": "include"}), start=21, size=20))
    assert "BATCH 2" in body
    assert "records 21-40" in body
    assert "50 reports" in body and "screened 1" in body and "remaining 49" in body


def test_every_required_field_is_labelled_in_the_text_output():
    body = render_text(*bundle([row(1, doi="10.1000/x")], languages={"rec-0001": "eng"}))
    for label in ("R0001", "PMID 9000001", "AUTHOR", "JOURNAL", "TYPES", "LANGUAGE",
                  "DOI", "DECISION", "Title 1", "Abstract 1", "2000"):
        assert label in body


def test_unscreened_only_output_says_the_view_is_filtered():
    body = render_text(*bundle(rows(5, **{"1": "include"}), unscreened_only=True, size=4))
    assert "unscreened only" in body


def test_special_characters_survive_rendering():
    """Real abstracts carry en dashes, minus signs, CJK titles and Greek letters."""
    text = "OR 2.00, 95% CI 1.00–4.00; −0.5; α = 0.05; 口腔; café"
    body = render_text(*bundle([row(1, title=text, abstract=text, first_author="Müller")]))
    for fragment in ("–4.00", "−0.5", "α", "口腔", "café",
                     "Müller"):
        assert fragment in body


def test_long_abstracts_are_wrapped_not_truncated():
    abstract = " ".join(f"word{i}" for i in range(400))
    body = render_text(*bundle([row(1, abstract=abstract)]))
    assert "word0" in body and "word399" in body
    assert max(len(line) for line in body.splitlines()) <= show.WIDTH


def test_rendering_is_deterministic():
    assert render_text(*bundle(rows(20))) == render_text(*bundle(rows(20)))
    assert render_json(*bundle(rows(20))) == render_json(*bundle(rows(20)))


# --- json ------------------------------------------------------------------------------

def test_json_output_is_valid_and_carries_every_required_field():
    payload = json.loads(render_json(*bundle([row(1)], languages={"rec-0001": "eng"})))
    assert payload["batch"]["batch_number"] == 1
    assert len(payload["records"]) == 1
    record = payload["records"][0]
    for key in ("report_id", "pmid", "title", "first_author", "pub_year", "journal",
                "publication_types", "language", "abstract", "decision"):
        assert key in record
    assert record["language"] == "eng"
    assert record["decision"] == ""


def test_json_preserves_order_and_full_abstract_text():
    payload = json.loads(render_json(*bundle(rows(50), start=21, size=20)))
    assert [r["report_id"] for r in payload["records"]] == [f"R{i:04d}" for i in range(21, 41)]
    assert payload["records"][0]["abstract"] == "Abstract 21"


def test_json_keeps_non_ascii_readable():
    assert "Müller" in render_json(*bundle([row(1, first_author="Müller")]))


# --- the CLI is read-only --------------------------------------------------------------

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_cli_does_not_modify_the_worksheet(sheet, capsys):
    path = sheet(rows(50), languages={f"rec-{i:04d}": "eng" for i in range(1, 51)})
    before = digest(path)
    for argv in (["--start", "1", "--size", "20"], ["--start", "21", "--size", "20"],
                 ["--unscreened-only", "--size", "20"],
                 ["--start", "1", "--size", "20", "--format", "json"]):
        assert show.main(argv) == 0
        assert digest(path) == before, f"{argv} altered the worksheet"
    capsys.readouterr()


def test_the_cli_writes_no_new_files(sheet, tmp_path, capsys):
    sheet(rows(20))
    before = set(tmp_path.rglob("*"))
    assert show.main(["--start", "1", "--size", "20"]) == 0
    assert set(tmp_path.rglob("*")) == before
    capsys.readouterr()


def test_the_default_invocation_shows_the_first_twenty(sheet, capsys):
    sheet(rows(50))
    assert show.main([]) == 0
    out = capsys.readouterr().out
    assert "BATCH 1" in out and "records 1-20" in out
    assert "R0020" in out and "R0021" not in out


def test_repeated_runs_print_identical_output(sheet, capsys):
    sheet(rows(50))
    show.main(["--start", "1", "--size", "20"])
    first = capsys.readouterr().out
    show.main(["--start", "1", "--size", "20"])
    assert capsys.readouterr().out == first


def test_a_missing_worksheet_fails_with_an_instruction(sheet, capsys):
    assert show.main(["--start", "1"]) == 1
    assert "worksheet" in capsys.readouterr().err


def test_an_empty_worksheet_fails_rather_than_printing_an_empty_batch(sheet, capsys):
    sheet([])
    assert show.main(["--start", "1"]) == 1
    assert "no records" in capsys.readouterr().err


def test_a_fully_screened_worksheet_says_so_under_unscreened_only(sheet, capsys):
    sheet(rows(3, **{"1": "include", "2": "exclude", "3": "exclude"}))
    assert show.main(["--unscreened-only"]) == 1
    assert "already has a decision" in capsys.readouterr().err


def test_an_invalid_range_exits_non_zero_without_printing_records(sheet, capsys):
    sheet(rows(5))
    assert show.main(["--start", "99"]) == 1
    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    assert "beyond" in captured.err


# --- against the project's own worksheet -----------------------------------------------

def test_the_project_worksheet_can_be_paged_without_being_touched(capsys):
    path = worksheet.worksheet_path(TA)
    if not path.exists():
        pytest.skip("no title/abstract worksheet in this checkout")
    before = digest(path)
    records = worksheet.read_csv(path)
    batch, meta = select(records, start=1, size=20)

    assert meta["total_records"] == len(records)
    assert meta["screened"] + meta["remaining"] == len(records)
    assert [r["report_id"] for r in batch] == [r["report_id"] for r in records[:20]]

    assert show.main(["--start", "1", "--size", "20"]) == 0
    assert digest(path) == before, "paging the real worksheet must not alter it"
    capsys.readouterr()
