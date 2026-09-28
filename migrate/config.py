"""Migration config: one YAML file per mapping version (see config/)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from . import transforms


@dataclass
class FieldSpec:
    name: str
    source: str
    transforms: List[Any]
    required: bool = False
    # What happens when an optional field fails its transform:
    #   warn   → load the row with this field empty, flag it in the exceptions file
    #   reject → reject the whole row
    on_error: str = "warn"

    def __post_init__(self):
        self.apply = transforms.chain(self.transforms)


@dataclass
class ParentSpec:
    entity: str
    source: str
    field: str


@dataclass
class ScopeRule:
    field: str
    exclude: List[str]
    reason: str


@dataclass
class DedupeSpec:
    strong_key: Optional[str] = None
    review_keys: List[str] = field(default_factory=list)


@dataclass
class EntitySpec:
    name: str
    source: Path
    key: str
    fields: List[FieldSpec]
    parent: Optional[ParentSpec] = None
    scope: Optional[ScopeRule] = None
    dedupe: Optional[DedupeSpec] = None


@dataclass
class ControlTotal:
    entity: str
    sum_field: str
    expected: float
    provided_by: str
    tolerance: float = 0.01


@dataclass
class GoLiveCriteria:
    max_reject_rate: float
    control_totals_must_match: bool = True


@dataclass
class MigrationConfig:
    project: str
    version: str
    notes: str
    entities: List[EntitySpec]
    control_totals: List[ControlTotal]
    go_live: GoLiveCriteria
    path: Path

    def entity(self, name: str) -> EntitySpec:
        return next(e for e in self.entities if e.name == name)


def load(path) -> MigrationConfig:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    base = path.parent.parent  # config/ lives at the repo root

    entities = []
    for name, spec in raw["entities"].items():
        fields = [
            FieldSpec(
                name=fname,
                source=f["source"],
                transforms=f.get("transforms", ["strip"]),
                required=f.get("required", False),
                on_error=f.get("on_error", "reject" if f.get("required") else "warn"),
            )
            for fname, f in spec["fields"].items()
        ]
        parent = ParentSpec(**spec["parent"]) if spec.get("parent") else None
        scope = ScopeRule(**spec["scope"]) if spec.get("scope") else None
        dedupe = DedupeSpec(**spec["dedupe"]) if spec.get("dedupe") else None
        entities.append(EntitySpec(
            name=name,
            source=(base / spec["source"]).resolve(),
            key=spec["key"],
            fields=fields,
            parent=parent,
            scope=scope,
            dedupe=dedupe,
        ))

    control_totals = [ControlTotal(**ct) for ct in raw.get("control_totals", [])]
    go_live = GoLiveCriteria(**raw["go_live"])
    return MigrationConfig(
        project=raw["project"],
        version=raw["version"],
        notes=raw.get("notes", "").strip(),
        entities=entities,
        control_totals=control_totals,
        go_live=go_live,
        path=path,
    )
