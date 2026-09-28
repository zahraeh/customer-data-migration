"""Prove the migration: every row accounted for, every euro accounted for.

Row counts alone are not proof. A value can be loaded successfully and
still be wrong, so control totals provided by the customer from their
legacy system are checked independently of our own transforms.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .pipeline import PipelineResult
from .target import TargetPlatform


@dataclass
class EntityBalance:
    entity: str
    source_rows: int
    accepted: int
    merged: int
    skipped: int
    rejected: int
    in_target_this_run: Optional[int] = None
    stale_in_target: Optional[int] = None
    orphans_in_target: Optional[int] = None

    @property
    def balanced(self) -> bool:
        return self.source_rows == self.accepted + self.merged + self.skipped + self.rejected

    @property
    def target_matches(self) -> Optional[bool]:
        if self.in_target_this_run is None:
            return None
        return self.in_target_this_run == self.accepted and not self.stale_in_target and not self.orphans_in_target


@dataclass
class ControlTotalCheck:
    entity: str
    field: str
    expected: float
    provided_by: str
    migrated: float
    on_hold: float
    unparseable_on_hold: int
    tolerance: float

    @property
    def unexplained(self) -> float:
        return round(self.expected - self.migrated - self.on_hold, 2) or 0.0  # no '-0.00'

    @property
    def matches(self) -> bool:
        return abs(self.unexplained) <= self.tolerance and self.unparseable_on_hold == 0


@dataclass
class Reconciliation:
    version: str
    balances: List[EntityBalance]
    control_totals: List[ControlTotalCheck]
    reject_rate: float
    max_reject_rate: float
    loaded: bool
    blockers: List[str] = field(default_factory=list)

    @property
    def go(self) -> bool:
        return not self.blockers


def reconcile(result: PipelineResult, target: Optional[TargetPlatform] = None, run_id: Optional[str] = None) -> Reconciliation:
    cfg = result.config
    balances = []
    for name, ent in result.entities.items():
        b = EntityBalance(
            entity=name,
            source_rows=len(ent.outcomes),
            accepted=ent.count("accepted"),
            merged=ent.count("merged"),
            skipped=ent.count("skipped"),
            rejected=ent.count("rejected"),
        )
        if target is not None:
            b.in_target_this_run = target.count(name, run_id)
            b.stale_in_target = target.count(name) - b.in_target_this_run
            if ent.spec.parent:
                b.orphans_in_target = target.orphans(name, ent.spec.parent.field, ent.spec.parent.entity)
        balances.append(b)

    checks = []
    for ct in cfg.control_totals:
        ent = result.entities[ct.entity]
        if target is not None:
            migrated = target.total(ct.entity, ct.sum_field, run_id)
        else:
            migrated = round(sum(r.get(ct.sum_field) or 0 for r in ent.accepted_records), 2)
        # Rows the customer still has to decide on carry value too; count what we can parse.
        on_hold_rows = [o for o in ent.with_status("rejected") if not _out_of_scope(ent.spec, o)]
        on_hold = round(sum(o.record.get(ct.sum_field) or 0 for o in on_hold_rows), 2)
        unparseable = sum(1 for o in on_hold_rows if o.record.get(ct.sum_field) is None)
        checks.append(ControlTotalCheck(
            entity=ct.entity, field=ct.sum_field, expected=ct.expected, provided_by=ct.provided_by,
            migrated=migrated, on_hold=on_hold, unparseable_on_hold=unparseable, tolerance=ct.tolerance,
        ))

    reject_rate = result.total_rejected / result.total_rows if result.total_rows else 0.0
    rec = Reconciliation(
        version=cfg.version, balances=balances, control_totals=checks,
        reject_rate=reject_rate, max_reject_rate=cfg.go_live.max_reject_rate, loaded=target is not None,
    )

    for b in balances:
        if not b.balanced:
            rec.blockers.append(f"{b.entity}: {b.source_rows} source rows but outcomes add up to "
                                f"{b.accepted + b.merged + b.skipped + b.rejected}")
        if b.target_matches is False:
            if b.in_target_this_run != b.accepted:
                rec.blockers.append(f"{b.entity}: {b.accepted} accepted but {b.in_target_this_run} in target")
            if b.stale_in_target:
                rec.blockers.append(f"{b.entity}: {b.stale_in_target} rows in target from an earlier run")
            if b.orphans_in_target:
                rec.blockers.append(f"{b.entity}: {b.orphans_in_target} rows in target with no parent")
    if reject_rate > cfg.go_live.max_reject_rate:
        rec.blockers.append(f"reject rate {reject_rate:.1%} is above the agreed {cfg.go_live.max_reject_rate:.1%}")
    if cfg.go_live.control_totals_must_match:
        for c in checks:
            if not c.matches:
                if c.unparseable_on_hold:
                    rec.blockers.append(f"{c.entity}.{c.field}: {c.unparseable_on_hold} rejected rows have no readable value")
                if abs(c.unexplained) > c.tolerance:
                    rec.blockers.append(f"{c.entity}.{c.field}: €{c.unexplained:,.2f} unexplained vs. the legacy control total")
    return rec


def _out_of_scope(spec, outcome) -> bool:
    return bool(spec.scope and outcome.record.get(spec.scope.field) in spec.scope.exclude)
