"""Transform, validate and de-duplicate every source row.

Every row in every source file ends up with exactly one status:

    accepted  → will be (or was) loaded into the target platform
    merged    → a duplicate of another row, folded into that "survivor"
    skipped   → valid, but out of scope by agreement with the customer
    rejected  → cannot be loaded; goes to the customer's exceptions file

That invariant is what makes reconciliation possible: source rows must
equal accepted + merged + skipped + rejected, per entity, every run.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import source as source_io
from .config import EntitySpec, MigrationConfig
from .transforms import TransformError, strip

STATUSES = ("accepted", "merged", "skipped", "rejected")


@dataclass
class RowOutcome:
    entity: str
    line: int
    external_id: Optional[str]
    status: str
    record: Dict
    source_row: Dict
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    merged_into: Optional[str] = None


@dataclass
class EntityResult:
    spec: EntitySpec
    source: source_io.SourceFile
    outcomes: List[RowOutcome]
    merge_map: Dict[str, str] = field(default_factory=dict)

    def count(self, status: str) -> int:
        return sum(1 for o in self.outcomes if o.status == status)

    def with_status(self, status: str) -> List[RowOutcome]:
        return [o for o in self.outcomes if o.status == status]

    @property
    def accepted_records(self) -> List[Dict]:
        return [o.record for o in self.outcomes if o.status == "accepted"]


@dataclass
class PipelineResult:
    config: MigrationConfig
    entities: Dict[str, EntityResult]

    @property
    def total_rows(self) -> int:
        return sum(len(e.outcomes) for e in self.entities.values())

    @property
    def total_rejected(self) -> int:
        return sum(e.count("rejected") for e in self.entities.values())


class ConfigError(Exception):
    pass


def _normalise_name(value: Optional[str]) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"\b(sarl|sas|sa|eurl|sci|m\.?|mme|et)\b", " ", value.lower())
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _completeness(record: Dict) -> int:
    return sum(1 for v in record.values() if v not in (None, ""))


def _transform_row(spec: EntitySpec, row: Dict, outcome: RowOutcome) -> None:
    for f in spec.fields:
        raw = row.get(f.source, "")
        try:
            value = f.apply(raw)
        except TransformError as e:
            if f.required or f.on_error == "reject":
                outcome.reasons.append(f"{f.name}: {e}")
            else:
                outcome.warnings.append(f"{f.name}: {e} (loaded empty)")
            value = None
        else:
            if value is None and f.required:
                outcome.reasons.append(f"{f.name} is required but empty")
        outcome.record[f.name] = value


def _check_parent(spec: EntitySpec, row: Dict, outcome: RowOutcome, results: Dict[str, EntityResult]) -> None:
    parent_result = results[spec.parent.entity]
    parent_id = strip(row.get(spec.parent.source, ""))
    if not parent_id:
        outcome.reasons.append(f"no {spec.parent.entity} reference ({spec.parent.source} is empty)")
        return

    resolved = parent_result.merge_map.get(parent_id, parent_id)
    outcome.record[spec.parent.field] = resolved
    if resolved != parent_id:
        outcome.warnings.append(f"re-linked from duplicate {parent_id} to surviving record {resolved}")

    status = {o.external_id: o.status for o in parent_result.outcomes}.get(resolved)
    if status == "accepted":
        return
    if status is None:
        outcome.reasons.append(f"{spec.parent.entity} {parent_id} does not exist in the {spec.parent.entity} export")
    else:
        outcome.reasons.append(f"{spec.parent.entity} {parent_id} was {status}, so this row cannot be attached to it")


def _dedupe(spec: EntitySpec, result: EntityResult) -> None:
    accepted = result.with_status("accepted")

    # Strong key (e.g. SIRET): same legal entity, merge automatically.
    if spec.dedupe.strong_key:
        groups: Dict[str, List[RowOutcome]] = {}
        for o in accepted:
            key = o.record.get(spec.dedupe.strong_key)
            if key:
                groups.setdefault(key, []).append(o)
        for key, group in groups.items():
            if len(group) < 2:
                continue
            survivor = max(group, key=lambda o: (_completeness(o.record), -o.line))
            for dup in group:
                if dup is survivor:
                    continue
                for k, v in dup.record.items():
                    if survivor.record.get(k) in (None, "") and v not in (None, ""):
                        survivor.record[k] = v
                        survivor.warnings.append(f"{k} filled in from duplicate {dup.external_id}")
                dup.status = "merged"
                dup.merged_into = survivor.external_id
                dup.reasons.append(
                    f"same {spec.dedupe.strong_key} ({key}) as {survivor.external_id}; merged into it"
                )
                result.merge_map[dup.external_id] = survivor.external_id

    # Weak keys (e.g. name + postcode): never merge on a guess, ask the customer.
    if spec.dedupe.review_keys:
        candidates: Dict[tuple, List[RowOutcome]] = {}
        for o in result.with_status("accepted"):
            if spec.dedupe.strong_key and o.record.get(spec.dedupe.strong_key):
                continue
            key = tuple(
                _normalise_name(o.record.get(k)) if k == "name" else (o.record.get(k) or "")
                for k in spec.dedupe.review_keys
            )
            if all(key):
                candidates.setdefault(key, []).append(o)
        for group in candidates.values():
            if len(group) < 2:
                continue
            ids = [o.external_id for o in group]
            for o in group:
                others = ", ".join(i for i in ids if i != o.external_id)
                o.warnings.append(
                    f"possible duplicate of {others} (same {' + '.join(spec.dedupe.review_keys)}); "
                    "loaded separately, please confirm"
                )


def process_entity(spec: EntitySpec, results: Dict[str, EntityResult]) -> EntityResult:
    src = source_io.read(spec.source)
    missing = [f.source for f in spec.fields if f.source not in src.headers]
    if spec.key not in src.headers:
        missing.append(spec.key)
    if spec.parent and spec.parent.source not in src.headers:
        missing.append(spec.parent.source)
    if missing:
        raise ConfigError(
            f"{spec.name}: columns {missing} not found in {src.path.name}. Headers are: {src.headers}"
        )

    result = EntityResult(spec=spec, source=src, outcomes=[])
    first_seen: Dict[str, int] = {}

    for index, row in enumerate(src.rows):
        line = src.line_number(index)
        ext_id = strip(row.get(spec.key, ""))
        outcome = RowOutcome(
            entity=spec.name, line=line, external_id=ext_id, status="accepted",
            record={"external_id": ext_id}, source_row=row,
        )

        if not ext_id:
            outcome.reasons.append(f"missing legacy ID ({spec.key})")
        elif ext_id in first_seen:
            outcome.reasons.append(f"legacy ID {ext_id} appears twice (also on line {first_seen[ext_id]})")
        else:
            first_seen[ext_id] = line

        _transform_row(spec, row, outcome)
        if spec.parent:
            _check_parent(spec, row, outcome, results)

        if outcome.reasons:
            outcome.status = "rejected"
        elif spec.scope and outcome.record.get(spec.scope.field) in spec.scope.exclude:
            outcome.status = "skipped"
            outcome.reasons.append(spec.scope.reason)

        result.outcomes.append(outcome)

    if spec.dedupe:
        _dedupe(spec, result)
    return result


def run(config: MigrationConfig) -> PipelineResult:
    results: Dict[str, EntityResult] = {}
    for spec in config.entities:
        if spec.parent and spec.parent.entity not in results:
            raise ConfigError(f"{spec.name} depends on {spec.parent.entity}, which must be listed first")
        results[spec.name] = process_entity(spec, results)
    return PipelineResult(config=config, entities=results)
