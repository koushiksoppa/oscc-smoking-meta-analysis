"""Stage 1 validation of a parsed citation table. Fails loudly; repairs nothing.

    python -m scripts.validation.validate_citations --source pubmed_v1

ERROR (exit 1): record count != expected, missing required field, non-numeric PMID or year,
                duplicate PMID, duplicate DOI (case-insensitive), duplicate record_id,
                a record that contradicts a filter the registry says was applied at retrieval.
WARNING:        malformed DOI, multiple DOIs, implausible year, a filter cross-check that cannot
                be applied, records not matching the documented query terms (diagnostic only).
SUMMARY:        counts, including records that a filter would have removed had one been applied.
Report: results/validation/<source_id>_citations_validation.md

Filter cross-checks read `filters_applied` from config/sources.yaml and never assume a filter was
used: claiming one in a report without evidence is itself a provenance error (D011, D013).
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from dataclasses import dataclass, field

from scripts.common.config import PROCESSED_DIR, VALIDATION_DIR, Source, get_source

REQUIRED = ["record_id", "source_id", "pmid", "title", "pub_year"]
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$")

# Diagnostic re-expression of a search's query string, applied to title + abstract + author
# keywords. PubMed's own [tiab] matching differs in detail, so non-matches are reported for
# inspection, never used to exclude records. Keyed by search_version, because every execution of
# the same query string shares one diagnostic (v1 and v1r use an identical query; D011).
QUERY_BLOCKS = {
    "v1": {
        "outcome": re.compile(r"oral squamous cell carcinoma|\boscc", re.I),
        "exposure": re.compile(r"\bsmoking\b|\bcigarette", re.I),
        "design": re.compile(r"case[\s-]control|\bcohort", re.I),
    },
}
QUERY_BLOCKS["v1r"] = QUERY_BLOCKS["v1"]


@dataclass
class Findings:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)


def claims_filter(source: Source, name: str) -> bool:
    """Whether the registry records that this filter was applied at retrieval."""
    return any(applied.strip().lower() == name for applied in source.filters_applied)


def language_tags(row: dict[str, str]) -> list[str]:
    """Language tags exactly as reported, for display. Compare with has_english()."""
    return [t for t in (row.get("languages") or "").split("; ") if t.strip()]


def has_english(row: dict[str, str]) -> bool:
    """Whether any reported language tag is English, compared case-insensitively.

    MEDLINE writes lowercase three-letter codes, but a case-sensitive test would silently
    misclassify a record tagged 'ENG' as non-English.
    """
    return any(tag.strip().lower() == "eng" for tag in language_tags(row))


def mesh_descriptors(row: dict[str, str]) -> set[str]:
    """Descriptor part of each MeSH heading: 'Mouth Neoplasms/*epidemiology' -> 'mouth neoplasms'."""
    return {
        heading.split("/")[0].lstrip("*").strip().lower()
        for heading in (row.get("mesh_terms") or "").split("; ")
        if heading.strip()
    }


def pmid_list(rows: list[dict[str, str]], limit: int = 10) -> str:
    shown = [r.get("pmid", "?") for r in rows[:limit]]
    return ", ".join(shown) + (f", … (+{len(rows) - limit} more)" if len(rows) > limit else "")


def check_filters(rows: list[dict[str, str]], source: Source, f: Findings) -> None:
    """Cross-check the records against the filters the registry says were applied.

    A record that a claimed filter would have removed is an error: either the filter was not
    actually applied, or this file is not the export the registry entry describes. Where no filter
    is claimed, such records are reported as counts — they are excluded at screening instead
    (D013), and the report must not imply a filter was involved.
    """
    # Language: PubMed assigns LA to every citation, indexed or not, so this check always applies.
    non_english = [r for r in rows if language_tags(r) and not has_english(r)]
    if claims_filter(source, "english"):
        for r in non_english:
            f.errors.append(
                f"{r.get('record_id', '?')}: language tag(s) {language_tags(r)}, but this source "
                "records an English filter at retrieval, so the record could not have been "
                "retrieved. Either the filter was not used or this file is not the export this "
                "entry describes."
            )
    elif non_english:
        f.info.append(
            f"records with no English language tag: {len(non_english)} "
            f"(this source retrieved without an English filter; they are excluded at screening "
            f"as not_english) — {pmid_list(non_english)}"
        )

    # Species: PubMed's Humans filter matches the MeSH term, which unindexed records lack. So the
    # check needs MeSH to be present in the export at all; see the limitation note below.
    if not any((r.get("mesh_terms") or "").strip() for r in rows):
        f.warnings.append(
            "no record carries MeSH headings, so the Humans-filter cross-check cannot be applied. "
            "This is consistent with an export containing only unindexed records, but also with an "
            "export that omitted MeSH; the two cannot be told apart from the records alone."
        )
        return

    lacks_humans = [r for r in rows if "humans" not in mesh_descriptors(r)]
    if claims_filter(source, "humans"):
        for r in lacks_humans:
            reason = ("no MeSH headings at all, so it is not MEDLINE-indexed"
                      if not (r.get("mesh_terms") or "").strip()
                      else "MeSH headings present but not 'Humans'")
            f.errors.append(
                f"{r.get('record_id', '?')}: {reason}, but this source records a Humans filter at "
                "retrieval. That filter matches the MeSH term 'Humans', so the record could not "
                "have been retrieved. Either the filter was not used or this file is not the "
                "export this entry describes."
            )
    elif lacks_humans:
        # Why this says nothing about indexing: the MEDLINE STAT field, which would distinguish
        # "not yet indexed" from "in a journal MEDLINE does not index", is not part of the
        # citation dataset. Claiming either from the absence of MeSH alone would assert a fact
        # this input cannot support.
        f.info.append(
            f"records without MeSH 'Humans': {len(lacks_humans)} "
            "(this source retrieved without a Humans filter; MeSH indexing status is not "
            "available in the citation dataset, so species eligibility is unknown from these "
            "records and is assessed at screening)"
        )


def check(rows: list[dict[str, str]], source: Source) -> Findings:
    f = Findings()
    if source.expected_records is None:
        f.warnings.append(
            f"{len(rows)} records parsed, but no independently reported count is recorded for "
            "this source, so the total cannot be cross-checked"
        )
    elif len(rows) != source.expected_records:
        f.errors.append(f"{len(rows)} records; expected {source.expected_records}")

    for field_name in REQUIRED:
        missing = [r.get("record_id") or f"row {i + 2}" for i, r in enumerate(rows) if not (r.get(field_name) or "").strip()]
        if missing:
            f.errors.append(f"missing required field '{field_name}': {', '.join(missing)}")

    bad_pmid = [r["pmid"] for r in rows if r.get("pmid") and not r["pmid"].isdigit()]
    if bad_pmid:
        f.errors.append(f"non-numeric PMID: {', '.join(bad_pmid)}")

    for key, label in (("record_id", "record_id"), ("pmid", "PMID")):
        dupes = [v for v, n in Counter(r[key] for r in rows if r.get(key)).items() if n > 1]
        if dupes:
            f.errors.append(f"duplicate {label}: {', '.join(dupes)}")

    doi_counts = Counter(r["doi"].strip().lower() for r in rows if r.get("doi", "").strip())
    dupes = [d for d, n in doi_counts.items() if n > 1]
    if dupes:
        f.errors.append(f"duplicate DOI: {', '.join(dupes)}")

    for r in rows:
        rid = r.get("record_id", "?")
        for doi in filter(None, (r.get("doi_all") or "").split("; ")):
            if not DOI_PATTERN.match(doi):
                f.warnings.append(f"{rid}: malformed DOI {doi!r}")
        if "; " in (r.get("doi_all") or ""):
            f.warnings.append(f"{rid}: multiple DOIs reported ({r['doi_all']}); first used as primary")
        year = (r.get("pub_year") or "").strip()
        if year and not year.isdigit():
            f.errors.append(f"{rid}: non-numeric publication year {year!r}")
        elif year and not (1900 <= int(year) <= 2100):
            f.warnings.append(f"{rid}: implausible publication year {year}")

    check_filters(rows, source, f)

    blocks = QUERY_BLOCKS.get(source.search_version)
    if blocks:
        for r in rows:
            text = " ".join((r.get("title", ""), r.get("abstract", ""), r.get("keywords", "")))
            unmatched = [name for name, rx in blocks.items() if not rx.search(text)]
            if unmatched:
                f.warnings.append(f"{r.get('record_id')}: search terms not found for block(s) {unmatched} (diagnostic)")

    n = len(rows)
    f.info += [
        f"records: {n}",
        f"with DOI: {sum(1 for r in rows if r.get('doi'))}",
        f"with abstract: {sum(1 for r in rows if r.get('abstract'))}",
        f"publication years: {min((r['pub_year'] for r in rows if r.get('pub_year')), default='-')}"
        f"–{max((r['pub_year'] for r in rows if r.get('pub_year')), default='-')}",
        f"latest Entrez date (bounds search date from below): "
        f"{max((r['entrez_date'] for r in rows if r.get('entrez_date')), default='-')}",
    ]
    return f


def write_report(findings: Findings, source: Source) -> str:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    path = VALIDATION_DIR / f"{source.source_id}_citations_validation.md"
    status = "FAIL" if findings.errors else "PASS"
    lines = [f"# Citation validation — {source.source_id}", "", f"**Status: {status}**", ""]
    for title, items in (("Errors", findings.errors), ("Warnings", findings.warnings), ("Summary", findings.info)):
        lines += [f"## {title} ({len(items)})", ""] + [f"- {x}" for x in items] + [""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True)
    args = ap.parse_args(argv)
    source = get_source(args.source)
    csv_path = PROCESSED_DIR / "citations" / f"{source.source_id}_citations.csv"
    if not csv_path.exists():
        print(f"FAIL: {csv_path} not found; run parse_citations first", file=sys.stderr)
        return 1
    with open(csv_path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    findings = check(rows, source)
    report = write_report(findings, source)
    print(f"{'FAIL' if findings.errors else 'PASS'}: {len(findings.errors)} errors, "
          f"{len(findings.warnings)} warnings -> {report}")
    return 1 if findings.errors else 0


if __name__ == "__main__":
    sys.exit(main())
