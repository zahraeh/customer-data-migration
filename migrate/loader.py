"""Push accepted records to the target in batches, parents before children."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict

from .pipeline import PipelineResult
from .target import RateLimited, TargetPlatform


class LoadFailed(Exception):
    pass


@dataclass
class LoadReport:
    run_id: str
    loaded: Dict[str, int] = field(default_factory=dict)
    batches: int = 0
    retries: int = 0


def new_run_id(version: str) -> str:
    return f"{version}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def load(
    result: PipelineResult,
    target: TargetPlatform,
    run_id: str,
    batch_size: int = 100,
    max_retries: int = 4,
    base_delay: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> LoadReport:
    report = LoadReport(run_id=run_id)
    target.start_run(run_id, result.config.version)
    try:
        for name, entity in result.entities.items():
            records = entity.accepted_records
            if not records:
                report.loaded[name] = 0
                continue
            target.ensure_table(name, list(records[0].keys()))
            loaded = 0
            for batch_no, start in enumerate(range(0, len(records), batch_size), start=1):
                batch = records[start:start + batch_size]
                for attempt in range(max_retries + 1):
                    try:
                        loaded += target.upsert_batch(name, batch, run_id, batch_no)
                        report.batches += 1
                        break
                    except RateLimited:
                        if attempt == max_retries:
                            raise LoadFailed(
                                f"{name} batch {batch_no} still rate-limited after {max_retries} retries"
                            )
                        report.retries += 1
                        sleep(base_delay * (2 ** attempt))
            report.loaded[name] = loaded
    except Exception:
        target.finish_run(run_id, "failed")
        raise
    target.finish_run(run_id, "completed")
    return report
