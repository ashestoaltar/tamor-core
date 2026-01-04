#!/usr/bin/env python3
"""
Tamor DB Doctor
- Sanity-checks schema presence, schema_version, and task/task_runs consistency.
- Exits nonzero if problems found.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from typing import Any, Iterable


VALID_TASK_STATUSES = {
    "detected",
    "needs_confirmation",
    "confirmed",
    "scheduled",
    "completed",
    "dismissed",
    "cancelled",
}

VALID_RUN_STATUSES = {
    "started",
    "completed",
    "success",   # legacy/current naming
    "failed",
    "cancelled",
}


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def q(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    cur = conn.execute(sql, tuple(params))
    return cur.fetchall()


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    rows = q(conn, "SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (name,))
    return bool(rows)


def col_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    rows = q(conn, f"PRAGMA table_info({table});")
    return any(r["name"] == col for r in rows)


def parse_json_maybe(s: Any) -> dict:
    if not s:
        return {}
    if isinstance(s, dict):
        return s
    if isinstance(s, (bytes, bytearray)):
        s = s.decode("utf-8", "ignore")
    if not isinstance(s, str):
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--db",
        default=os.environ.get("MEMORY_DB", os.path.expanduser("~/tamor-core/api/memory/tamor.db")),
        help="Path to tamor SQLite DB (default: $MEMORY_DB or ~/tamor-core/api/memory/tamor.db)",
    )
    args = ap.parse_args()

    db_path = args.db
    if not os.path.exists(db_path):
        eprint(f"[FAIL] DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    failures: list[str] = []
    warns: list[str] = []

    # ---- Required tables
    required_tables = ["schema_version", "conversations"]
    for t in required_tables:
        if not table_exists(conn, t):
            failures.append(f"Missing required table: {t}")

    # detected_tasks/task_runs are expected in your current Tamor build.
    # If you are mid-migration, keep these as warnings instead of fails.
    if not table_exists(conn, "detected_tasks"):
        warns.append("Table detected_tasks not found (skipping task checks)")
    if not table_exists(conn, "task_runs"):
        warns.append("Table task_runs not found (skipping run checks)")

    # ---- schema_version sanity (do not assume an 'id' column)
    if table_exists(conn, "schema_version"):
        sv_cols = [r["name"] for r in q(conn, "PRAGMA table_info(schema_version);")]
        print(f"[INFO] schema_version columns: {sv_cols}")


        # Choose a sensible ordering column if one exists, otherwise use SQLite rowid.
        order_candidates = ["applied_at", "updated_at", "created_at", "ts", "timestamp", "version"]
        order_col = next((c for c in order_candidates if c in sv_cols), None)

        if order_col:
            rows = q(conn, f"SELECT * FROM schema_version ORDER BY {order_col} DESC LIMIT 1;")
        else:
            rows = q(conn, "SELECT rowid, * FROM schema_version ORDER BY rowid DESC LIMIT 1;")

        if not rows:
            failures.append("schema_version has no rows (migration state unknown)")
        else:
            row = rows[0]
            # Prefer 'version' if present, otherwise print whichever column we ordered by.
            v = row["version"] if "version" in row.keys() else (row[order_col] if order_col else None)
            if v is None:
                warns.append(f"schema_version present but no readable version field (cols={sv_cols})")
            else:
                print(f"[OK] schema_version: {v}")

    # ---- detected_tasks checks
    if table_exists(conn, "detected_tasks"):
        # Columns we expect (don’t hard-fail if some are missing; warn and keep going)
        expected_cols = ["id", "status", "conversation_id", "normalized_json"]
        for c in expected_cols:
            if not col_exists(conn, "detected_tasks", c):
                warns.append(f"detected_tasks missing column: {c}")

        # Invalid statuses
        if col_exists(conn, "detected_tasks", "status"):
            rows = q(
                conn,
                "SELECT id, status FROM detected_tasks WHERE status IS NULL OR status='';",
            )
            for r in rows:
                failures.append(f"Task {r['id']} has empty status")

            rows = q(
                conn,
                "SELECT id, status FROM detected_tasks WHERE status IS NOT NULL;",
            )
            for r in rows:
                st = (r["status"] or "").strip()
                if st and st not in VALID_TASK_STATUSES:
                    failures.append(f"Task {r['id']} has invalid status: {st}")

        # Confirmed/scheduled tasks must have scheduled_for in normalized_json
        has_norm = col_exists(conn, "detected_tasks", "normalized_json")
        if has_norm:
            rows = q(
                conn,
                """
                SELECT id, status, normalized_json
                FROM detected_tasks
                WHERE status IN ('confirmed','scheduled')
                """,
            )
            for r in rows:
                norm = parse_json_maybe(r["normalized_json"])
                scheduled_for = norm.get("scheduled_for")
                if not scheduled_for:
                    failures.append(
                        f"Task {r['id']} status={r['status']} missing normalized_json.scheduled_for"
                    )

        # Orphan conversation_id (if both columns/tables exist)
        if table_exists(conn, "conversations") and col_exists(conn, "detected_tasks", "conversation_id"):
            rows = q(
                conn,
                """
                SELECT t.id, t.conversation_id
                FROM detected_tasks t
                LEFT JOIN conversations c ON c.id = t.conversation_id
                WHERE t.conversation_id IS NOT NULL AND c.id IS NULL
                """,
            )
            if rows:
                # Summarize orphaned conversation_ids
                counts: dict[int, int] = {}
                for r in rows:
                    cid = int(r["conversation_id"])
                    counts[cid] = counts.get(cid, 0) + 1

                # Show up to 10 examples and then summary
                example_rows = q(
                    conn,
                    """
                    SELECT t.id, t.conversation_id
                    FROM detected_tasks t
                    LEFT JOIN conversations c ON c.id = t.conversation_id
                    WHERE t.conversation_id IS NOT NULL AND c.id IS NULL
                    ORDER BY t.conversation_id, t.id
                    LIMIT 10
                    """,
                )
                for r in example_rows:
                    warns.append(f"Task {r['id']} references missing conversation_id={r['conversation_id']}")

                warns.append(
                    "Orphaned tasks summary: "
                    + ", ".join(f"conversation_id={cid} ({n} tasks)" for cid, n in sorted(counts.items()))
                )

        print("[OK] detected_tasks checks complete")

    # ---- task_runs checks
    if table_exists(conn, "task_runs"):
        expected_cols = ["id", "task_id", "status", "started_at", "finished_at"]
        for c in expected_cols:
            if not col_exists(conn, "task_runs", c):
                warns.append(f"task_runs missing column: {c}")

        # Missing task_id
        if col_exists(conn, "task_runs", "task_id"):
            rows = q(conn, "SELECT id FROM task_runs WHERE task_id IS NULL;")
            for r in rows:
                failures.append(f"task_runs {r['id']} missing task_id")

        # Orphan task_id
        if table_exists(conn, "detected_tasks") and col_exists(conn, "task_runs", "task_id"):
            rows = q(
                conn,
                """
                SELECT r.id, r.task_id
                FROM task_runs r
                LEFT JOIN detected_tasks t ON t.id = r.task_id
                WHERE r.task_id IS NOT NULL AND t.id IS NULL
                LIMIT 50
                """,
            )
            for r in rows:
                failures.append(f"task_runs {r['id']} references missing task_id={r['task_id']}")

        # Invalid run statuses
        if col_exists(conn, "task_runs", "status"):
            rows = q(conn, "SELECT id, status FROM task_runs WHERE status IS NOT NULL;")
            for r in rows:
                st = (r["status"] or "").strip()
                if st and st not in VALID_RUN_STATUSES:
                    warns.append(f"task_runs {r['id']} has unknown status: {st}")

        print("[OK] task_runs checks complete")

    # ---- Report
    for w in warns:
        eprint(f"[WARN] {w}")

    if failures:
        for f in failures:
            eprint(f"[FAIL] {f}")
        eprint(f"\nDB Doctor: FAIL ({len(failures)} issues, {len(warns)} warnings)")
        return 1

    print(f"DB Doctor: OK ({len(warns)} warnings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
