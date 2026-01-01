#!/usr/bin/env python3
import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "memory", "tamor.db")
DB_PATH = os.getenv("MEMORY_DB", DEFAULT_DB)

EXPECTED_DB = "/home/tamor/tamor-core/api/memory/tamor.db"
DEMO_PROJECT_NAME = "Anchor Spec Search Demo"


def ensure_correct_db_path() -> None:
    if DB_PATH != EXPECTED_DB:
        raise RuntimeError(
            f"[seed_anchor_demo] Refusing to run on wrong DB.\n"
            f"DB_PATH   = {DB_PATH}\n"
            f"EXPECTED  = {EXPECTED_DB}\n"
        )


def get_or_create_demo_project(conn: sqlite3.Connection) -> int:
    cur = conn.cursor()

    # Check if project already exists
    cur.execute(
        "SELECT id FROM projects WHERE name = ? ORDER BY id LIMIT 1;",
        (DEMO_PROJECT_NAME,),
    )
    row = cur.fetchone()
    if row:
        project_id = row[0]
        print(f"[seed_anchor_demo] Demo project already exists with id={project_id}.")
        return project_id

    # Create project if missing
    cur.execute(
        """
        INSERT INTO projects (name, created_at)
        VALUES (?, datetime('now'))
        """,
        (DEMO_PROJECT_NAME,),
    )
    project_id = cur.lastrowid
    print(f"[seed_anchor_demo] Created demo project '{DEMO_PROJECT_NAME}' with id={project_id}.")
    return project_id


def run_seed(conn: sqlite3.Connection) -> None:
    project_id = get_or_create_demo_project(conn)

    # If you want to add demo project_files/messages/intents later, this is where to do it.
    # It's deliberately conservative right now to avoid touching your data unexpectedly.

    conn.commit()
    print(f"[seed_anchor_demo] Seeding complete for project id={project_id}.")


def main() -> None:
    ensure_correct_db_path()
    print(f"[{datetime.now().isoformat()}] [seed_anchor_demo] Using DB: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        run_seed(conn)
        print("[seed_anchor_demo] Finished.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

