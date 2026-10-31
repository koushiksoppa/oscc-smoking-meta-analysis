"""The extraction schema, loaded from config/extraction.yaml.

Two tables, following docs/data_dictionary/extraction_schema.md:
  studies   — one row per study_id, the unit of analysis (D004)
  estimates — one row per reported effect estimate; all are preserved (provenance rule 8)

A field whose `status` is `unresolved` depends on a protocol decision that has not been made.
Extraction can still record what a study reported, but the validator says so rather than treating
any value as protocol-conformant.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field

import yaml

from scripts.common.config import ROOT, PipelineError

EXTRACTION_CONFIG = ROOT / "config" / "extraction.yaml"
STUDIES = "studies"
ESTIMATES = "estimates"
TABLES = (STUDIES, ESTIMATES)
UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class Field:
    name: str
    type: str
    description: str = ""
    values: tuple[str, ...] = ()
    status: str = ""
    depends_on: str = ""

    @property
    def is_unresolved(self) -> bool:
        return self.status == UNRESOLVED


@dataclass(frozen=True)
class Table:
    name: str
    fields: tuple[Field, ...]
    required: tuple[str, ...]

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)

    def field(self, name: str) -> Field | None:
        return next((f for f in self.fields if f.name == name), None)


@dataclass(frozen=True)
class Schema:
    tables: dict[str, Table]
    missing_codes: tuple[str, ...]
    thresholds: dict[str, float] = dc_field(default_factory=dict)

    def table(self, name: str) -> Table:
        if name not in self.tables:
            raise PipelineError(f"unknown table {name!r}; expected one of {TABLES}")
        return self.tables[name]

    @property
    def unresolved_fields(self) -> tuple[Field, ...]:
        return tuple(f for t in self.tables.values() for f in t.fields if f.is_unresolved)


def load_schema() -> Schema:
    with open(EXTRACTION_CONFIG, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    tables = {}
    for name in TABLES:
        if name not in data:
            raise PipelineError(f"{EXTRACTION_CONFIG.name}: missing table {name!r}")
        spec = data[name]
        fields = tuple(
            Field(name=fname, type=f.get("type", "text"), description=f.get("description", ""),
                  values=tuple(f.get("values", ())), status=f.get("status", ""),
                  depends_on=f.get("depends_on", ""))
            for fname, f in spec["fields"].items()
        )
        required = tuple(spec.get("required", ()))
        unknown = [r for r in required if r not in {f.name for f in fields}]
        if unknown:
            raise PipelineError(f"{name}: required field(s) not defined: {unknown}")
        for f in fields:
            if f.type == "enum" and not f.values:
                raise PipelineError(f"{name}.{f.name}: enum field with no values")
            if f.is_unresolved and not f.depends_on:
                raise PipelineError(
                    f"{name}.{f.name}: an unresolved field must name the decision it waits on"
                )
        tables[name] = Table(name=name, fields=fields, required=required)

    return Schema(tables=tables,
                  missing_codes=tuple(data.get("missing_codes", ())),
                  thresholds=dict(data.get("thresholds", {})))
