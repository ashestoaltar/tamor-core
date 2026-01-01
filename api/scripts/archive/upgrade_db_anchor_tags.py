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
            f"[upgrade_db_anchor_tags] Refusing to run on wrong DB.\n"
            f"DB_PATH   = {DB_PATH}\n"
            f"EXPECTED  = {EXPECTED_DB}\n"
        )


def run_migration(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    # If you ever decide to actually use anchor_tags, you can put the schema here.
    # For now, this is an idempotent "create-if-needed" so it's safe.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS anchor_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            tag TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (file_id) REFERENCES project_files(id)
        );
        """
    )

    conn.commit()


def main() -> None:
    ensure_correct_db_path()
    print(f"[{datetime.now().isoformat()}] [upgrade_db_anchor_tags] Using DB: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        run_migration(conn)
        print("[upgrade_db_anchor_tags] Migration completed successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

