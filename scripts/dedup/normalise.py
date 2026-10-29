"""Deterministic normalisation used for duplicate matching.

Normalised values are used ONLY to decide whether two records describe the same publication.
They are never written back over the values extracted from the source export: the citation
dataset keeps every value exactly as the database reported it (provenance rule 5).
"""
from __future__ import annotations

import re
import unicodedata

DOI_PREFIXES = (
    "https://doi.org/", "http://doi.org/",
    "https://dx.doi.org/", "http://dx.doi.org/",
    "doi.org/", "doi:", "doi ",
)
NON_ALNUM = re.compile(r"[^a-z0-9]+")
WHITESPACE = re.compile(r"\s+")


def normalise_doi(value: str | None) -> str:
    """Lowercase, strip URL/`doi:` prefixes and trailing punctuation. '' if absent."""
    if not value:
        return ""
    v = value.strip().lower()
    changed = True
    while changed:
        changed = False
        for prefix in DOI_PREFIXES:
            if v.startswith(prefix):
                v = v[len(prefix):].strip()
                changed = True
    return v.rstrip(" .;,")


def normalise_title(value: str | None) -> str:
    """Fold accents, lowercase, reduce to alphanumeric words. '' if absent."""
    if not value:
        return ""
    v = unicodedata.normalize("NFKD", value)
    v = "".join(ch for ch in v if not unicodedata.combining(ch)).lower()
    v = NON_ALNUM.sub(" ", v)
    return WHITESPACE.sub(" ", v).strip()


def surname(author: str | None) -> str:
    """First author's surname from MEDLINE 'Last, First' form. '' if absent."""
    if not author:
        return ""
    last = author.split(",")[0]
    return NON_ALNUM.sub("", unicodedata.normalize("NFKD", last).lower())


def fingerprint(title: str | None, first_author: str | None, year: str | None) -> str:
    """Identifier-free key: title + first-author surname + year. '' unless all three exist."""
    t, a, y = normalise_title(title), surname(first_author), (year or "").strip()
    if not (t and a and y):
        return ""
    return f"{t}|{a}|{y}"
