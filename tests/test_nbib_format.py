"""Parser tests on FORMAT FRAGMENTS only.

Per docs/protocol/provenance_rules.md (no synthetic citations), these fragments exercise
MEDLINE tag syntax and carry no bibliographic content. They never touch data/ and cannot
enter the pipeline, which reads only checksum-registered files under data/raw/.
"""
import pytest

from scripts.acquisition import nbib


def test_continuation_lines_are_joined():
    recs = nbib.parse("PMID- 1\nTI  - part one\n      part two\n")
    assert recs[0].first("TI") == "part one part two"


def test_blank_lines_separate_records_and_line_numbers_are_kept():
    recs = nbib.parse("PMID- 1\nTI  - a\n\nPMID- 2\nTI  - b\n")
    assert [r.first("PMID") for r in recs] == ["1", "2"]
    assert [r.line_start for r in recs] == [1, 4]


def test_crlf_and_repeated_tags_preserved_in_order():
    recs = nbib.parse("PMID- 1\r\nPT  - x\r\nPT  - y\r\n")
    assert recs[0].all("PT") == ["x", "y"]


def test_bom_tolerated_but_invalid_utf8_rejected():
    assert nbib.decode(b"\xef\xbb\xbfPMID- 1\n").startswith("PMID")
    with pytest.raises(nbib.NbibFormatError):
        nbib.decode(b"PMID- 1\nTI  - \xff\n")


@pytest.mark.parametrize("text", [
    "      orphan continuation\n",
    "PMID- 1\nnot a tag line\n",
    "TI  - record without PMID\n",
])
def test_malformed_input_fails_loudly(text):
    with pytest.raises(nbib.NbibFormatError):
        nbib.parse(text)


def test_count_records_is_independent_of_parser():
    assert nbib.count_records("PMID- 1\n\nPMID- 2\n") == 2


def test_doi_extraction_prefers_aid_and_deduplicates():
    # 10.1000/182 is the DOI of the DOI Handbook itself (doi.org), used here as a format example.
    rec = nbib.parse("PMID- 1\nLID - 10.1000/182 [doi]\nAID - 10.1000/182 [doi]\nAID - S0000 [pii]\n")[0]
    assert nbib.extract_dois(rec) == ["10.1000/182"]


def test_no_doi_gives_empty_list_not_a_guess():
    rec = nbib.parse("PMID- 1\nAID - S0000 [pii]\n")[0]
    assert nbib.extract_dois(rec) == []


@pytest.mark.parametrize("dp,year", [("2019 Mar 5", "2019"), ("2020", "2020"), ("", None), (None, None), ("Spring", None)])
def test_year_extraction_does_not_infer(dp, year):
    assert nbib.extract_year(dp) == year
