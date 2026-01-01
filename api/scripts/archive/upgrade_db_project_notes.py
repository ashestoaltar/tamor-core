#!/usr/bin/env python3
import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "memory", "tamor.db")
DB_PATH = os.getenv("MEMORY_DB", DEFAULT_DB)

EXPECTED_DB = "/home/tamor/tamor-core/api/memory/tamor.db"


def ensure_correct_db_path() -> None:
    if DB_PATH != EXPECTED_DB:
        raise RuntimeError(
            f"[upgrade_db_project_notes] Refusing to run on wrong DB.\n"
            f"DB_PATH   = {DB_PATH}\n"
            f"EXPECTED  = {EXPECTED_DB}\n"
        )


def run_migration(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_notes';")
    row = cur.fetchone()
    if row:
        print("[upgrade_db_project_notes] Table 'project_notes' already exists. No changes made.")
    else:
        # If you ever need to bootstrap this table, define schema here.
        print("[upgrade_db_project_notes] WARNING: 'project_notes' does not exist. No automatic creation performed.")
    conn.commit()


def main() -> None:
    ensure_correct_db_path()
    print(f"[{datetime.now().isoformat()}] [upgrade_db_project_notes] Using DB: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        run_migration(conn)
        print("[upgrade_db_project_notes] Migration completed.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

