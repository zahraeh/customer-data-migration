"""Reports: a Markdown summary for the project team, CSV exceptions for the customer.

Exceptions files are written UTF-8 with BOM and ';' separators so they open
correctly in French-locale Excel with a double-click, which is how the
customer's ops team will actually open them.
"""
from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path
from typing import Optional

from .loader import LoadReport
from .pipeline import PipelineResult
from .reconcile import Reconciliation

_ID = re.compile(r"\b(CL|CT|CTR)[-\d]+\b")
_QUOTED = re.compile(r"'[^']*'")
_PAREN = re.compile(r"\([^)]*\)")


def _pattern(message: str) -> str:
    return _PAREN.sub("", _QUOTED.sub("…", _ID.sub("#", message))).replace("  ", " ").replace(" ;", ";").strip()


def write_exceptions(result: PipelineResult, out_dir: Path) -> None:
    for name, ent in result.entities.items():
        path = out_dir / f"exceptions_{name}.csv"
        rows = []
        for o in ent.outcomes:
            if o.status == "rejected":
                status, issues = "REJECTED - needs your decision", o.reasons + o.warnings
            elif o.status == "merged":
                status, issues = f"MERGED into {o.merged_into}", o.reasons
            elif o.status == "skipped":
                status, issues = "OUT OF SCOPE - not migrated", o.reasons
            elif o.warnings:
                status, issues = "MIGRATED with warning", o.warnings
            else:
                continue
            rows.append([o.line, o.external_id or "", status, " | ".join(issues)] +
                        [o.source_row.get(h, "") for h in ent.source.headers])
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["Line in export", "Legacy ID", "Status", "Issue(s)"] + ent.source.headers)
            w.writerows(rows)


def _decision_block(rec: Reconciliation) -> str:
    if rec.go:
        return "## Decision: ✅ GO\n\nAll go-live criteria met.\n"
    lines = ["## Decision: ⛔ NO-GO\n"]
    lines += [f"- {b}" for b in rec.blockers]
    return "\n".join(lines) + "\n"


def summary_markdown(result: PipelineResult, rec: Reconciliation, load: Optional[LoadReport] = None) -> str:
    cfg = result.config
    mode = f"Load — run `{load.run_id}`" if load else "Dry run (nothing written to the target)"
    out = [f"# Migration report — {cfg.version}\n",
           f"**Project:** {cfg.project}  ",
           f"**Mode:** {mode}  ",
           f"**Config:** `{cfg.path.name}`\n"]
    if cfg.notes:
        out.append("> " + cfg.notes.replace("\n", "\n> ") + "\n")
    out.append(_decision_block(rec))

    out.append("## 1. Every row accounted for\n")
    header = "| Entity | Source rows | Accepted | Merged | Skipped | Rejected | Balanced |"
    sep = "|---|---:|---:|---:|---:|---:|:---:|"
    if rec.loaded:
        header += " In target | Stale | Orphans |"
        sep += "---:|---:|---:|"
    out += [header, sep]
    for b in rec.balances:
        row = (f"| {b.entity} | {b.source_rows} | {b.accepted} | {b.merged} | {b.skipped} | "
               f"{b.rejected} | {'✅' if b.balanced else '❌'} |")
        if rec.loaded:
            row += f" {b.in_target_this_run} | {b.stale_in_target} | {b.orphans_in_target if b.orphans_in_target is not None else '—'} |"
        out.append(row)
    out.append(f"\nReject rate: **{rec.reject_rate:.2%}** (go-live limit {rec.max_reject_rate:.1%})\n")

    if rec.control_totals:
        out.append("## 2. Every euro accounted for\n")
        out.append("Control totals come from the customer's legacy system, not from our own transforms.\n")
        out += ["| Check | Legacy control total | Migrated | On hold (rejected rows) | Unexplained | Result |",
                "|---|---:|---:|---:|---:|:---:|"]
        for c in rec.control_totals:
            out.append(
                f"| {c.entity}.{c.field} | €{c.expected:,.2f} | €{c.migrated:,.2f} | €{c.on_hold:,.2f} | "
                f"**€{c.unexplained:,.2f}** | {'✅' if c.matches else '❌'} |"
            )
        out.append("")
        out += [f"_Source of control total: {c.provided_by}_" for c in rec.control_totals]
        out.append("")

    out.append("## 3. Why rows were rejected\n")
    any_rejects = False
    for name, ent in result.entities.items():
        counter = Counter(_pattern(r) for o in ent.with_status("rejected") for r in o.reasons)
        if not counter:
            continue
        any_rejects = True
        out.append(f"**{name}**\n")
        out += ["| Reason | Rows |", "|---|---:|"]
        out += [f"| {reason} | {n} |" for reason, n in counter.most_common()]
        out.append("")
    if not any_rejects:
        out.append("No rejected rows.\n")

    out.append("## 4. Loaded, but worth a look\n")
    out += ["| Entity | Warning | Rows |", "|---|---|---:|"]
    warn_rows = 0
    for name, ent in result.entities.items():
        counter = Counter(_pattern(w) for o in ent.outcomes if o.status != "rejected" for w in o.warnings)
        for w, n in counter.most_common():
            out.append(f"| {name} | {w} | {n} |")
            warn_rows += 1
    if not warn_rows:
        out.append("| — | none | 0 |")
    out.append("")

    if load:
        out.append("## 5. Load\n")
        out.append(f"{load.batches} batches, {load.retries} transient failures retried with exponential backoff.\n")

    out.append("---\nPer-row detail for the customer: `exceptions_<entity>.csv` in this folder.\n")
    return "\n".join(out)


def write(result: PipelineResult, rec: Reconciliation, out_dir, load: Optional[LoadReport] = None) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_exceptions(result, out_dir)
    path = out_dir / ("load_report.md" if load else "dry_run_report.md")
    path.write_text(summary_markdown(result, rec, load), encoding="utf-8")
    return path
