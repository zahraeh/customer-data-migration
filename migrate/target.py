"""Stand-in for the new platform's bulk import API, backed by SQLite.

It behaves the way a real SaaS import endpoint does in the ways that
matter for a migration:

- upsert keyed on the legacy ID (external_id), so re-running a load
  updates rows instead of duplicating them;
- every row remembers which migration run last wrote it, so a run can be
  rolled back;
- it can be told to fail transiently (HTTP 429 style) to exercise retries.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


class RateLimited(Exception):
    """Transient failure: the caller should back off and retry."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class TargetPlatform:
    def __init__(self, path, fail_first_attempt_every: Optional[int] = None):
        self.path = Path(path)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self._calls = 0
        self._fail_every = fail_first_attempt_every
        self._failed_batches = set()
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS migration_runs (
                run_id TEXT PRIMARY KEY, config_version TEXT, started_at TEXT,
                finished_at TEXT, status TEXT)"""
        )

    # ── Schema ───────────────────────────────────────────────────────────────

    def ensure_table(self, entity: str, columns: List[str]) -> None:
        cols = ", ".join(f'"{c}"' for c in columns if c != "external_id")
        self.conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{entity}" (external_id TEXT PRIMARY KEY, {cols}, '
            "migration_run_id TEXT, loaded_at TEXT)"
        )

    # ── Runs ─────────────────────────────────────────────────────────────────

    def start_run(self, run_id: str, config_version: str) -> None:
        self.conn.execute(
            "INSERT INTO migration_runs VALUES (?, ?, ?, NULL, 'running')",
            (run_id, config_version, _now()),
        )
        self.conn.commit()

    def finish_run(self, run_id: str, status: str) -> None:
        self.conn.execute(
            "UPDATE migration_runs SET finished_at = ?, status = ? WHERE run_id = ?",
            (_now(), status, run_id),
        )
        self.conn.commit()

    def runs(self) -> List[Dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM migration_runs ORDER BY started_at")]

    # ── Import API ───────────────────────────────────────────────────────────

    def upsert_batch(self, entity: str, records: List[Dict], run_id: str, batch_no: int) -> int:
        self._calls += 1
        if self._fail_every and batch_no % self._fail_every == 0 and (entity, batch_no) not in self._failed_batches:
            self._failed_batches.add((entity, batch_no))
            raise RateLimited(f"429 Too Many Requests on {entity} batch {batch_no}")

        if not records:
            return 0
        columns = list(records[0].keys())
        placeholders = ", ".join("?" for _ in columns) + ", ?, ?"
        col_sql = ", ".join(f'"{c}"' for c in columns) + ", migration_run_id, loaded_at"
        updates = ", ".join(f'"{c}" = excluded."{c}"' for c in columns if c != "external_id")
        sql = (
            f'INSERT INTO "{entity}" ({col_sql}) VALUES ({placeholders}) '
            f"ON CONFLICT(external_id) DO UPDATE SET {updates}, "
            "migration_run_id = excluded.migration_run_id, loaded_at = excluded.loaded_at"
        )
        now = _now()
        with self.conn:
            self.conn.executemany(sql, [[r[c] for c in columns] + [run_id, now] for r in records])
        return len(records)

    # ── Queries used by reconciliation ───────────────────────────────────────

    def count(self, entity: str, run_id: Optional[str] = None) -> int:
        sql = f'SELECT COUNT(*) FROM "{entity}"'
        args = ()
        if run_id:
            sql += " WHERE migration_run_id = ?"
            args = (run_id,)
        return self.conn.execute(sql, args).fetchone()[0]

    def total(self, entity: str, column: str, run_id: Optional[str] = None) -> float:
        sql = f'SELECT COALESCE(SUM("{column}"), 0) FROM "{entity}"'
        args = ()
        if run_id:
            sql += " WHERE migration_run_id = ?"
            args = (run_id,)
        return round(self.conn.execute(sql, args).fetchone()[0], 2)

    def orphans(self, child: str, fk: str, parent: str) -> int:
        return self.conn.execute(
            f'SELECT COUNT(*) FROM "{child}" c LEFT JOIN "{parent}" p ON c."{fk}" = p.external_id '
            "WHERE p.external_id IS NULL"
        ).fetchone()[0]

    # ── Rollback ─────────────────────────────────────────────────────────────

    def rollback(self, run_id: str, entities_child_first: List[str]) -> Dict[str, int]:
        removed = {}
        with self.conn:
            for entity in entities_child_first:
                cur = self.conn.execute(f'DELETE FROM "{entity}" WHERE migration_run_id = ?', (run_id,))
                removed[entity] = cur.rowcount
            self.conn.execute("UPDATE migration_runs SET status = 'rolled_back' WHERE run_id = ?", (run_id,))
        return removed
