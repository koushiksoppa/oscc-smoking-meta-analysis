"""Duplicate matching: pure logic, no file access.

Two confidence levels, deliberately separated:

  MERGED       — records linked by a shared persistent identifier (DOI, PMID) or by an exact
                 normalised title+author+year fingerprint. Deterministic and auditable.
  NEEDS_REVIEW — records whose titles are merely *similar*. These are reported as candidate
                 pairs and are NOT merged. Only the human reviewer can resolve them, because a
                 near-identical title can be a conference abstract, an erratum, a reanalysis or a
                 genuinely different paper (D010: automated tooling is not a reviewer).

Nothing is deleted at any confidence level; grouping only assigns a shared report_id.
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from scripts.dedup import normalise

MERGED = "merged"
NEEDS_REVIEW = "needs_review"

BY_PMID = "shared PMID"
BY_DOI = "shared DOI"
BY_FINGERPRINT = "identical title + first author + year fingerprint"

# Keys compared for exact equality, in order of decreasing authority (D014).
# PMID first: it is PubMed's own stable key for a citation, whereas DOI strings vary in form and
# are occasionally shared between records or recorded incorrectly. The fingerprint is the
# documented fallback for records carrying neither identifier.
EXACT_KEYS = (
    ("pmid", BY_PMID),
    ("doi", BY_DOI),
    ("fingerprint", BY_FINGERPRINT),
)
# Rank used to report WHY a record was merged when several criteria matched the same pair.
# Without this the strongest available evidence can be misreported: a pair sharing a PMID could
# be recorded as a fingerprint match purely because of how the pair list happened to be ordered.
CRITERION_PRIORITY = {criterion: rank for rank, (_, criterion) in enumerate(EXACT_KEYS)}
TITLE_SIMILARITY_THRESHOLD = 0.92


@dataclass(frozen=True)
class Pair:
    record_a: str
    record_b: str
    criterion: str
    matched_value: str
    resolution: str


class Groups:
    """Union-find over record_ids. Deterministic: group members are kept sorted."""

    def __init__(self, record_ids):
        self._parent = {r: r for r in record_ids}

    def find(self, item: str) -> str:
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[item] != root:          # path compression
            self._parent[item], item = root, self._parent[item]
        return root

    def union(self, a: str, b: str) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        lo, hi = sorted((ra, rb))                   # lower record_id becomes the root
        self._parent[hi] = lo
        return True

    def as_groups(self) -> list[list[str]]:
        out: dict[str, list[str]] = {}
        for item in self._parent:
            out.setdefault(self.find(item), []).append(item)
        return sorted((sorted(members) for members in out.values()), key=lambda g: g[0])


def keys_for(row: dict[str, str]) -> dict[str, str]:
    """Matching keys for one citation row. An empty key never matches anything."""
    return {
        "doi": normalise.normalise_doi(row.get("doi")),
        "pmid": (row.get("pmid") or "").strip(),
        "fingerprint": normalise.fingerprint(
            row.get("title"), row.get("first_author"), row.get("pub_year")
        ),
    }


def find_duplicates(rows: list[dict[str, str]]) -> tuple[Groups, list[Pair]]:
    """Group records and return every candidate pair with its criterion and resolution."""
    ids = [r["record_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("find_duplicates received duplicate record_id values")
    groups = Groups(ids)
    keys = {r["record_id"]: keys_for(r) for r in rows}
    pairs: list[Pair] = []

    for key_name, criterion in EXACT_KEYS:
        buckets: dict[str, list[str]] = {}
        for rid in ids:
            value = keys[rid][key_name]
            if value:                               # empty keys are never grouped
                buckets.setdefault(value, []).append(rid)
        for value, members in sorted(buckets.items()):
            members.sort()
            for other in members[1:]:
                pairs.append(Pair(members[0], other, criterion, value, MERGED))
                groups.union(members[0], other)

    pairs += _similar_titles(rows, groups)
    return groups, sorted(pairs, key=lambda p: (p.record_a, p.record_b, p.criterion))


def _similar_titles(rows: list[dict[str, str]], groups: Groups) -> list[Pair]:
    """Flag similar-but-not-identical titles within the same publication year."""
    by_year: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        year = (row.get("pub_year") or "").strip()
        title = normalise.normalise_title(row.get("title"))
        if year and title:
            by_year.setdefault(year, []).append((row["record_id"], title))

    found: list[Pair] = []
    for year in sorted(by_year):
        entries = sorted(by_year[year])
        for i, (rid_a, title_a) in enumerate(entries):
            for rid_b, title_b in entries[i + 1:]:
                if groups.find(rid_a) == groups.find(rid_b):
                    continue                        # already merged on a stronger criterion
                if title_a == title_b:
                    continue                        # exact match without a shared fingerprint
                ratio = SequenceMatcher(None, title_a, title_b).ratio()
                if ratio >= TITLE_SIMILARITY_THRESHOLD:
                    found.append(Pair(
                        rid_a, rid_b, "similar title, same year",
                        f"similarity {ratio:.3f}", NEEDS_REVIEW,
                    ))
    return found


@dataclass(frozen=True)
class DuplicateGroup:
    """A canonical report backed by more than one source record."""
    report_id: str
    primary: str                    # the record representing the group
    members: tuple[str, ...]        # every source record_id in the group, primary included
    criteria: tuple[str, ...]       # every criterion that linked records inside this group

    @property
    def duplicates(self) -> tuple[str, ...]:
        return tuple(m for m in self.members if m != self.primary)


def _duplicate_groups(
    assignment: dict[str, dict[str, str]], pairs: list[Pair]
) -> list[DuplicateGroup]:
    """Groups holding more than one record, with the evidence that linked them.

    Reported separately from the merged-pair count: one group of three records is three pairs
    but a single canonical report. Pairs awaiting review are never included — they are not
    merged, so they form no group (D010).
    """
    members: dict[str, list[str]] = {}
    primary: dict[str, str] = {}
    for record_id, info in sorted(assignment.items()):
        members.setdefault(info["report_id"], []).append(record_id)
        if info["is_primary"] == "yes":
            primary[info["report_id"]] = record_id

    groups: list[DuplicateGroup] = []
    for report_id, group in sorted(members.items()):
        if len(group) < 2:
            continue
        inside = set(group)
        criteria = sorted(
            {p.criterion for p in pairs
             if p.resolution == MERGED and p.record_a in inside and p.record_b in inside},
            key=lambda c: CRITERION_PRIORITY.get(c, len(CRITERION_PRIORITY)),
        )
        groups.append(DuplicateGroup(
            report_id=report_id,
            primary=primary[report_id],
            members=tuple(sorted(group)),
            criteria=tuple(criteria),
        ))
    return groups


@dataclass(frozen=True)
class MatchResult:
    """One matching run over one set of records.

    The pair list and the record assignment are produced together and travel together, so they
    cannot be combined with each other's mismatched counterparts — every derived count is a
    property of this object rather than a function taking the two separately.
    """
    rows: list[dict[str, str]]
    pairs: list[Pair]
    assignment: dict[str, dict[str, str]]

    @property
    def merged_pairs(self) -> list[Pair]:
        return [p for p in self.pairs if p.resolution == MERGED]

    @property
    def unresolved_pairs(self) -> list[Pair]:
        return [p for p in self.pairs if p.resolution == NEEDS_REVIEW]

    @property
    def report_ids(self) -> set[str]:
        return {info["report_id"] for info in self.assignment.values()}

    @property
    def duplicate_groups(self) -> list[DuplicateGroup]:
        return _duplicate_groups(self.assignment, self.pairs)


def resolve(rows: list[dict[str, str]], source_order: list[str]) -> MatchResult:
    """Match, group and assign report_ids in one step. The entry point stages should use."""
    groups, pairs = find_duplicates(rows)
    return MatchResult(rows, pairs, assign_report_ids(rows, groups, pairs, source_order))


def primary_sort_key(row: dict[str, str], source_order: list[str]) -> tuple:
    """Deterministic choice of the record that represents a group.

    Preference: earliest source in config/sources.yaml, then lowest numeric PMID, then record_id.
    Source order is used because the first-listed search version is the one whose record the
    PRISMA flow attributes the report to.
    """
    source_id = row.get("source_id", "")
    index = source_order.index(source_id) if source_id in source_order else len(source_order)
    pmid = row.get("pmid", "")
    return (index, int(pmid) if pmid.isdigit() else float("inf"), row["record_id"])


def assign_report_ids(
    rows: list[dict[str, str]],
    groups: Groups,
    pairs: list[Pair],
    source_order: list[str],
) -> dict[str, dict[str, str]]:
    """Map each record_id to its report_id, primary flag, and how it was matched.

    `merged_with` names the record this one was directly matched against, and `merge_criterion`
    the evidence for *that* match. The two are reported together because a group can be a chain:
    a record's direct match is often not the group's primary, and reporting a criterion beside
    `duplicate_of` alone would assert evidence between records that share nothing.

    Both ends of every pair are considered. Where a record has several direct matches the
    strongest is reported (CRITERION_PRIORITY), with the lower record_id breaking ties.
    """
    by_id = {r["record_id"]: r for r in rows}
    direct: dict[str, tuple[int, str, str]] = {}        # record -> (rank, criterion, other record)
    for pair in pairs:
        if pair.resolution != MERGED:
            continue
        rank = CRITERION_PRIORITY[pair.criterion]
        for this, other in ((pair.record_a, pair.record_b), (pair.record_b, pair.record_a)):
            held = direct.get(this)
            if held is None or (rank, other) < (held[0], held[2]):
                direct[this] = (rank, pair.criterion, other)

    assignment: dict[str, dict[str, str]] = {}
    ordered = sorted(
        groups.as_groups(),
        key=lambda g: primary_sort_key(by_id[min(g)], source_order),
    )
    for n, members in enumerate(ordered, start=1):
        report_id = f"R{n:04d}"
        primary = min(members, key=lambda rid: primary_sort_key(by_id[rid], source_order))
        for rid in sorted(members):
            # Every member of a multi-record group took part in at least one pair, since that is
            # the only way it could have been grouped. 'transitive' is therefore a defensive
            # fallback for a broken invariant, not an expected value.
            found = None if rid == primary else direct.get(rid)
            assignment[rid] = {
                "report_id": report_id,
                "is_primary": "yes" if rid == primary else "no",
                "duplicate_of": "" if rid == primary else primary,
                "merged_with": found[2] if found else "",
                "merge_criterion": "" if rid == primary else (found[1] if found else "transitive"),
            }
    return assignment
