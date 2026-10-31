"""PRISMA flow diagram: box contents, refusals, and that pending never renders as zero.

The wording is tested through `build_boxes()`, which is pure, rather than inferred from the PNG.
Flow dicts here are synthetic inputs used to exercise the renderer; none describes a real review.
"""
import pytest

from scripts.screening.prisma import PENDING
from scripts.visualization import prisma_diagram
from scripts.visualization.prisma_diagram import MAIN, SIDE, build_boxes, count, draw


def flow(**over):
    """A flow with the search and deduplication done and nothing screened — the current state."""
    base = {
        "per_source": {"pubmed_v1r": 194},
        "identified": 194, "duplicates_removed": 0, "unique_reports": 194,
        "ta_total": 194, "ta_screened": 0, "ta_excluded": 0, "ta_included": 0,
        "ta_unresolved": 0, "ta_unscreened": 194, "ta_reasons": {},
        "ft_sought": PENDING, "ft_not_retrieved": PENDING, "ft_assessed": PENDING,
        "ft_excluded": PENDING, "ft_included": PENDING, "ft_unresolved": PENDING,
        "ft_reasons": {}, "ft_exists": False,
        "included_studies": PENDING, "studies_in_synthesis": PENDING, "notes": [],
    }
    base.update(over)
    return base


def texts(diagram):
    return "\n".join(b.text for b in diagram.boxes)


# --- count formatting ----------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (0, "n = 0"), (194, "n = 194"), (PENDING, "n = pending"), (None, "n = pending"),
])
def test_count_keeps_zero_and_pending_distinct(value, expected):
    assert count(value) == expected


def test_pending_never_renders_as_zero():
    body = texts(build_boxes(flow()))
    assert "n = pending" in body
    for line in body.splitlines():
        assert PENDING not in line, "the raw <pending> token should be formatted, not printed"


# --- box contents --------------------------------------------------------------------

def test_identification_lists_every_source_and_the_total():
    body = texts(build_boxes(flow()))
    assert "pubmed_v1r (n = 194)" in body
    assert "Total (n = 194)" in body
    assert "Duplicate records removed (n = 0)" in body


def test_a_source_with_no_export_shows_pending_not_zero():
    body = texts(build_boxes(flow(per_source={"pubmed_v1": f"{PENDING} — export missing",
                                              "pubmed_v1r": 194})))
    assert "pubmed_v1 (n = pending)" in body


def test_partially_screened_stage_shows_both_numbers():
    """Showing only one of 'screened' and 'total' would misrepresent progress."""
    body = texts(build_boxes(flow(ta_screened=50)))
    assert "Records screened (n = 50 of 194)" in body


def test_fully_screened_stage_shows_a_single_number():
    body = texts(build_boxes(flow(ta_screened=194, ta_excluded=160, ta_included=34)))
    assert "Records screened (n = 194)" in body
    assert "Records excluded (n = 160)" in body


def test_unscreened_flow_says_reasons_are_pending_not_absent():
    body = texts(build_boxes(flow()))
    assert "reasons pending" in body


def test_completed_full_text_stage_lists_reasons_with_counts():
    body = texts(build_boxes(flow(
        ta_screened=194, ta_excluded=160, ta_included=34,
        ft_exists=True, ft_sought=34, ft_not_retrieved=2, ft_assessed=32,
        ft_excluded=20, ft_included=12,
        ft_reasons={"wrong_outcome": 12, "no_reference_group": 8},
        included_studies=11)))
    assert "wrong_outcome (n = 12)" in body
    assert "no_reference_group (n = 8)" in body
    assert "Reports not retrieved (n = 2)" in body
    assert "Studies included in review (n = 11)" in body
    assert "Reports of included studies (n = 12)" in body


def test_reasons_with_zero_counts_are_omitted_from_the_diagram():
    """The table lists every code; the diagram would be unreadable, so zeros are dropped."""
    body = texts(build_boxes(flow(ft_exists=True, ft_excluded=5,
                                  ft_reasons={"wrong_design": 5})))
    assert "wrong_design (n = 5)" in body
    assert "animal_or_invitro" not in body


def test_full_text_stage_with_no_exclusions_says_so():
    body = texts(build_boxes(flow(ft_exists=True, ft_excluded=0, ft_reasons={})))
    assert "none recorded" in body


# --- structure -----------------------------------------------------------------------

def test_diagram_has_the_prisma_sections_and_two_columns():
    diagram = build_boxes(flow())
    assert {b.section for b in diagram.boxes} == {"Identification", "Screening", "Included"}
    assert sum(1 for b in diagram.boxes if b.column == MAIN) == 5
    assert sum(1 for b in diagram.boxes if b.column == SIDE) == 4


def test_banner_warns_that_an_unscreened_flow_is_not_a_finding():
    diagram = build_boxes(flow())
    assert "NOT SCREENED" in diagram.banner
    assert "not** because nothing was eligible" in diagram.banner


def test_banner_reflects_a_completed_screening_stage():
    assert "TITLE/ABSTRACT COMPLETE" in build_boxes(flow(ta_screened=194)).banner


def test_banner_strips_markdown_for_the_figure():
    """The banner is written for Markdown; asterisks would print literally in a figure."""
    lines = prisma_diagram.banner_for_figure("**BOLD.** plain **not** plain")
    assert "**" not in "".join(lines)
    assert "BOLD." in lines[0] and "not" in "".join(lines)


def test_banner_wraps_rather_than_running_off_the_figure():
    long = "word " * 80
    lines = prisma_diagram.banner_for_figure(long, width=40)
    assert len(lines) > 1 and all(len(line) <= 40 for line in lines)


def test_banner_never_returns_an_empty_list():
    assert prisma_diagram.banner_for_figure("") == [""]


# --- rendering and refusal ------------------------------------------------------------

def test_diagram_is_written(tmp_path):
    path = draw(build_boxes(flow()), tmp_path / "prisma.png")
    assert path.exists() and path.stat().st_size > 10000


def test_completed_flow_also_renders(tmp_path):
    diagram = build_boxes(flow(ta_screened=194, ta_excluded=160, ta_included=34,
                               ft_exists=True, ft_sought=34, ft_not_retrieved=2,
                               ft_assessed=32, ft_excluded=20, ft_included=12,
                               ft_reasons={"wrong_outcome": 12, "wrong_design": 8},
                               included_studies=11))
    assert draw(diagram, tmp_path / "full.png").stat().st_size > 10000


def test_no_diagram_is_drawn_when_the_flow_does_not_reconcile(tmp_path, monkeypatch, capsys):
    """A flow diagram asserts its numbers add up; an inconsistent one must not be rendered."""
    broken = flow(identified=194, duplicates_removed=5, unique_reports=194)
    monkeypatch.setattr(prisma_diagram.prisma, "gather", lambda: broken)
    drawn = []
    monkeypatch.setattr(prisma_diagram, "draw", lambda *a, **k: drawn.append(a))

    assert prisma_diagram.main(["--out", str(tmp_path / "x.png")]) == 1
    err = capsys.readouterr().err
    assert "does not reconcile" in err and "unique reports" in err
    assert drawn == [], "nothing may be drawn when the flow is inconsistent"


def test_main_draws_and_reports_the_banner(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(prisma_diagram.prisma, "gather", lambda: flow())
    out = tmp_path / "prisma.png"
    assert prisma_diagram.main(["--out", str(out)]) == 0
    assert out.exists()
    assert "NOT SCREENED" in capsys.readouterr().out
