"""Extraction schema, template generation and validation.

Rows are structural stubs. No row describes a real study, and none is presented as extracted data.
"""
import csv

import pytest

from scripts.common.config import PipelineError
from scripts.extraction import schema, template, validate_extraction
from scripts.extraction.schema import ESTIMATES, STUDIES, load_schema
from scripts.screening import worksheet
from scripts.screening.vocabulary import EXCLUDE, FT, INCLUDE, TA


# --- schema --------------------------------------------------------------------------

def test_schema_loads_both_tables():
    sch = load_schema()
    assert set(sch.tables) == {STUDIES, ESTIMATES}
    assert "NR" in sch.missing_codes
    assert sch.thresholds["min_scc_proportion"] == 90.0


def test_schema_matches_the_data_dictionary():
    """Every field in the config must be documented.

    The reverse is not asserted: the data dictionary also specifies the risk_of_bias table, which
    has no implementation yet because the tool cannot be chosen before the included designs are
    known. Several fields share one table row in the document, so all backticked identifiers are
    collected rather than only the first per line.
    """
    import re

    from scripts.common.config import ROOT
    doc = (ROOT / "docs" / "data_dictionary" / "extraction_schema.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"`([a-z_][a-z0-9_]*)`", doc))
    coded = {f.name for t in load_schema().tables.values() for f in t.fields}
    missing = sorted(coded - documented)
    assert not missing, f"fields in the config but absent from the data dictionary: {missing}"


def test_unresolved_fields_name_their_decision():
    unresolved = {f.name: f.depends_on for f in load_schema().unresolved_fields}
    assert unresolved == {"comparator_type": "P003", "exposure_contrast": "P004"}


def test_required_fields_include_source_location_and_verification():
    estimates = load_schema().table(ESTIMATES)
    assert "source_location" in estimates.required
    assert "verified" in estimates.required
    assert "adjusted_alcohol" in estimates.required, "alcohol adjustment is its own field (D009)"


def test_malformed_schema_is_rejected(tmp_path, monkeypatch):
    import yaml
    path = tmp_path / "extraction.yaml"
    path.write_text(yaml.safe_dump({
        "missing_codes": ["NR"],
        "studies": {"required": ["study_id"], "fields": {"study_id": {"type": "id"}}},
        "estimates": {"required": [], "fields": {
            "x": {"type": "enum", "status": "unresolved"}}},   # no values, no depends_on
    }), encoding="utf-8")
    monkeypatch.setattr(schema, "EXTRACTION_CONFIG", path)
    with pytest.raises(PipelineError, match="enum field with no values"):
        load_schema()


def test_required_field_must_be_defined(tmp_path, monkeypatch):
    import yaml
    path = tmp_path / "extraction.yaml"
    path.write_text(yaml.safe_dump({
        "missing_codes": [],
        "studies": {"required": ["absent_field"], "fields": {"study_id": {"type": "id"}}},
        "estimates": {"required": [], "fields": {"estimate_id": {"type": "id"}}},
    }), encoding="utf-8")
    monkeypatch.setattr(schema, "EXTRACTION_CONFIG", path)
    with pytest.raises(PipelineError, match="required field"):
        load_schema()


# --- validation: studies -------------------------------------------------------------

SCH = load_schema()


def study(study_id="S1", **over):
    row = {c: "" for c in SCH.table(STUDIES).columns}
    row.update(study_id=study_id, primary_report_id="R0001", first_author="A, B",
               pub_year="2001", country="India", design="case_control")
    row.update(over)
    return row


def estimate(estimate_id="E1", **over):
    row = {c: "" for c in SCH.table(ESTIMATES).columns}
    row.update(estimate_id=estimate_id, study_id="S1", source_location="Table 2, p. 4",
               measure="OR", estimate="2.0", ci_low="1.5", ci_high="2.7",
               adjustment="adjusted", adjusted_for="age; sex; alcohol",
               adjusted_alcohol="yes", verified="yes")
    row.update(over)
    return row


def check(studies=None, estimates=None):
    return validate_extraction.check(studies or [study()], estimates or [estimate()], SCH)


def test_minimal_valid_extraction_passes():
    f = check()
    assert f.errors == []


def test_missing_required_field_is_an_error():
    f = check(studies=[study(country="")])
    assert any("'country' is empty" in e for e in f.errors)


def test_duplicate_study_id_is_an_error():
    f = check(studies=[study("S1"), study("S1")])
    assert any("duplicate study_id" in e for e in f.errors)


@pytest.mark.parametrize("fields,match", [
    ({"n_total": "100", "n_cases": "150"}, "exceeds n_total"),
    ({"n_total": "100", "n_controls": "150"}, "exceeds n_total"),
    ({"n_total": "100", "n_cases": "60", "n_controls": "60"}, "exceeds n_total"),
    ({"n_cases": "-5"}, "cannot be negative"),
    ({"n_cases": "12.5"}, "whole number"),
    ({"n_cases": "many"}, "not a number"),
])
def test_impossible_sample_sizes_are_errors(fields, match):
    assert any(match in e for e in check(studies=[study(**fields)]).errors)


def test_scc_proportion_below_the_d008_threshold_is_an_error():
    f = check(studies=[study(scc_proportion="80", histology_confirmed="partial")])
    assert any("below the 90% required by D008" in e for e in f.errors)


def test_scc_proportion_below_threshold_is_accepted_when_histology_is_confirmed_for_all():
    f = check(studies=[study(scc_proportion="80", histology_confirmed="all")])
    assert f.errors == []


def test_impossible_percentage_is_an_error():
    assert any("not a percentage" in e for e in check(studies=[study(scc_proportion="140")]).errors)


def test_unseparable_site_is_warned_about():
    f = check(studies=[study(site_separable="no")])
    assert any("pooled-site estimate ineligible" in w for w in f.warnings)


def test_invalid_enum_is_an_error():
    assert any("not one of" in e for e in check(studies=[study(design="rct")]).errors)


def test_missing_codes_are_accepted_in_enum_fields():
    f = check(studies=[study(histology_confirmed="NR", setting="UNCLEAR")])
    assert f.errors == []


# --- validation: estimates -----------------------------------------------------------

def test_missing_source_location_is_an_error():
    f = check(estimates=[estimate(source_location="")])
    assert any("'source_location' is empty" in e for e in f.errors)


@pytest.mark.parametrize("fields,match", [
    ({"estimate": "0"}, "must be positive"),
    ({"estimate": "-2"}, "must be positive"),
    ({"ci_low": "3.0", "ci_high": "2.0"}, "not below ci_high"),
    ({"estimate": "9.0"}, "outside its own CI"),
    ({"estimate": "abc"}, "not a number"),
])
def test_invalid_effect_estimates_are_errors(fields, match):
    assert any(match in e for e in check(estimates=[estimate(**fields)]).errors)


def test_estimate_inconsistent_with_its_ci_is_warned_about():
    """Inside its interval but far off-centre: 2.6 against a CI whose geometric mean is 2.01.

    sqrt(1.5 x 2.7) = 2.0125, which is 23% below 2.6 — above the 10% tolerance, so a warning.
    An estimate *outside* its interval is a hard error instead, checked separately.
    """
    f = check(estimates=[estimate(estimate="2.6", ci_low="1.5", ci_high="2.7")])
    assert f.errors == []
    assert any("geometric mean of its CI" in w for w in f.warnings)


def test_estimate_referencing_an_unknown_study_is_an_error():
    f = check(estimates=[estimate(study_id="S99")])
    assert any("not in the studies table" in e for e in f.errors)


def test_adjusted_without_covariates_is_an_error():
    f = check(estimates=[estimate(adjusted_for="")])
    assert any("adjusted_for is empty" in e for e in f.errors)


def test_lack_of_alcohol_adjustment_is_warned_about():
    f = check(estimates=[estimate(adjusted_alcohol="no")])
    assert any("not adjusted for alcohol" in w for w in f.warnings)


def test_two_by_two_counts_inconsistent_with_the_estimate_are_warned_about():
    """a=30 b=70 c=10 d=90 implies OR 3.857; a reported 2.0 is a 93% gap."""
    f = check(estimates=[estimate(n_exposed_cases="30", n_exposed_controls="70",
                                  n_unexposed_cases="10", n_unexposed_controls="90")])
    assert any("imply OR 3.86" in w for w in f.warnings)


def test_consistent_two_by_two_counts_raise_no_warning():
    f = check(estimates=[estimate(estimate="3.857", ci_low="2.0", ci_high="7.4",
                                  n_exposed_cases="30", n_exposed_controls="70",
                                  n_unexposed_cases="10", n_unexposed_controls="90")])
    assert not any("imply OR" in w for w in f.warnings)


def test_partial_two_by_two_counts_are_warned_about():
    f = check(estimates=[estimate(n_exposed_cases="30", n_exposed_controls="70")])
    assert any("2 of 4 cell counts" in w for w in f.warnings)


def test_negative_cell_count_is_an_error():
    f = check(estimates=[estimate(n_exposed_cases="-3")])
    assert any("non-negative whole number" in e for e in f.errors)


# --- the synthesis gate ---------------------------------------------------------------

def test_unverified_estimate_cannot_be_selected_for_analysis():
    f = check(estimates=[estimate(verified="no", selected_for_analysis="yes",
                                  selection_rationale="maximally adjusted")])
    assert any("must not enter a synthesis" in e for e in f.errors)


def test_selection_requires_a_recorded_rationale():
    f = check(estimates=[estimate(selected_for_analysis="yes")])
    assert any("no selection_rationale" in e for e in f.errors)


def test_a_study_may_select_only_one_estimate():
    rows = [estimate("E1", selected_for_analysis="yes", selection_rationale="r"),
            estimate("E2", selected_for_analysis="yes", selection_rationale="r")]
    f = check(estimates=rows)
    assert any("2 estimates selected" in e for e in f.errors)


def test_valid_selection_passes():
    f = check(estimates=[estimate(selected_for_analysis="yes",
                                  selection_rationale="maximally adjusted, includes alcohol")])
    assert f.errors == []
    assert any("selected for analysis: 1" in i for i in f.info)


def test_no_selection_is_warned_about():
    f = check()
    assert any("no estimate is selected" in w for w in f.warnings)


def test_duplicate_estimate_id_is_an_error():
    f = check(estimates=[estimate("E1"), estimate("E1")])
    assert any("duplicate estimate_id" in e for e in f.errors)


# --- unresolved fields are reported, not enforced -------------------------------------

def test_unresolved_enum_accepts_a_candidate_value_but_flags_it():
    f = check(estimates=[estimate(comparator_type="never_smoker", exposure_contrast="ever")])
    assert f.errors == []
    assert any("pending P003" in i for i in f.info)
    assert any("pending P004" in i for i in f.info)


def test_unresolved_enum_with_an_unknown_value_warns_rather_than_errors():
    f = check(estimates=[estimate(comparator_type="light_smoker")])
    assert not any("light_smoker" in e for e in f.errors)
    assert any("not yet protocol-conformant" in w for w in f.warnings)


def test_report_records_the_unresolved_decisions():
    f = check()
    assert any("awaits P003" in i for i in f.info)
    assert any("awaits P004" in i for i in f.info)


# --- template generation --------------------------------------------------------------

@pytest.fixture
def seeded(tmp_path, monkeypatch):
    """A full-text worksheet with one include and one exclude."""
    screening = tmp_path / "data" / "screening"
    screening.mkdir(parents=True)
    monkeypatch.setattr(worksheet, "SCREENING_DIR", screening)
    monkeypatch.setattr(template, "EXTRACTION_DIR", tmp_path / "data" / "extraction")

    rows = [
        {"report_id": "R0001", "record_id": "src:1", "pmid": "11", "doi": "10.1/a",
         "pub_year": "2001", "first_author": "A, B", "title": "t1",
         "full_text_status": "retrieved", "decision": INCLUDE, "reason_code": "",
         "reviewer": "SSK", "screened_date": "", "notes": ""},
        {"report_id": "R0002", "record_id": "src:2", "pmid": "22", "doi": "",
         "pub_year": "2002", "first_author": "C, D", "title": "t2",
         "full_text_status": "retrieved", "decision": EXCLUDE, "reason_code": "wrong_design",
         "reviewer": "SSK", "screened_date": "", "notes": ""},
    ]
    path = worksheet.worksheet_path(FT)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return tmp_path


def test_template_seeds_only_full_text_includes(seeded):
    result = template.build(STUDIES)
    rows = worksheet.read_csv(template.table_path(STUDIES))
    assert result["rows"] == 1 and [r["study_id"] for r in rows] == ["R0001"]


def test_template_leaves_every_data_column_empty(seeded):
    template.build(STUDIES)
    row = worksheet.read_csv(template.table_path(STUDIES))[0]
    for col in ("n_total", "n_cases", "design", "scc_proportion", "extracted_by",
                "anatomical_sites", "histology_confirmed"):
        assert row[col] == "", f"{col} must be the reviewer's to enter from the full text"


def test_template_seeds_identifiers_only_from_screening(seeded):
    template.build(STUDIES)
    row = worksheet.read_csv(template.table_path(STUDIES))[0]
    assert row["pmid"] == "11" and row["first_author"] == "A, B" and row["pub_year"] == "2001"


def test_estimates_template_is_empty_because_count_is_unknown(seeded):
    result = template.build(ESTIMATES)
    assert result["rows"] == 0
    assert worksheet.read_csv(template.table_path(ESTIMATES)) == []


def test_template_refuses_to_overwrite(seeded):
    template.build(STUDIES)
    with pytest.raises(PipelineError, match="not overwritten"):
        template.build(STUDIES)


def test_refresh_preserves_extracted_values(seeded):
    template.build(STUDIES)
    path = template.table_path(STUDIES)
    rows = worksheet.read_csv(path)
    rows[0].update(n_total="500", n_cases="200", design="case_control", extracted_by="SSK")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    result = template.build(STUDIES, refresh=True)
    after = worksheet.read_csv(path)[0]
    assert result["carried"] == 1
    assert after["n_total"] == "500" and after["n_cases"] == "200" and after["extracted_by"] == "SSK"


def test_refresh_refuses_to_discard_extracted_values(seeded):
    template.build(STUDIES)
    path = template.table_path(STUDIES)
    rows = worksheet.read_csv(path)
    rows[0]["n_total"] = "500"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    ft = worksheet.worksheet_path(FT)
    kept = [r for r in worksheet.read_csv(ft) if r["report_id"] != "R0001"]
    with open(ft, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(kept[0]))
        w.writeheader()
        w.writerows(kept)

    with pytest.raises(PipelineError, match="would discard recorded work"):
        template.build(STUDIES, refresh=True)


def test_refresh_keeps_reviewer_created_estimate_rows(seeded):
    template.build(ESTIMATES)
    path = template.table_path(ESTIMATES)
    row = estimate("E1")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row))
        w.writeheader()
        w.writerows([row])

    template.build(ESTIMATES, refresh=True)
    after = worksheet.read_csv(path)
    assert len(after) == 1 and after[0]["estimate_id"] == "E1"
    assert after[0]["source_location"] == "Table 2, p. 4"


def test_template_requires_full_text_screening_first(tmp_path, monkeypatch):
    monkeypatch.setattr(worksheet, "SCREENING_DIR", tmp_path / "screening")
    monkeypatch.setattr(template, "EXTRACTION_DIR", tmp_path / "extraction")
    with pytest.raises(PipelineError, match="no study has been included yet"):
        template.build(STUDIES)


def test_validator_requires_the_templates_to_exist(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(template, "EXTRACTION_DIR", tmp_path / "absent")
    assert validate_extraction.main([]) == 1
    assert "not found" in capsys.readouterr().err
