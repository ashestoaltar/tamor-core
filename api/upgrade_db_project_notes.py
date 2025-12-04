"""
Upgrade script: add `project_notes` table for per-project notes.

Usage:
    cd /home/tamor/tamor-core/api
    python upgrade_db_project_notes.py
"""

import os
import sqlite3

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_PATH = os.getenv("MEMORY_DB", "memory/tamor.db")


def main():
    print("[*] Using DB:", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()

        # Create table if it doesn't exist.
        # One row per (user_id, project_id).
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS project_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                project_id INTEGER NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, project_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            """
        )

        # Trigger to keep updated_at fresh on UPDATE
        cur.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_project_notes_updated_at
            AFTER UPDATE ON project_notes
            BEGIN
                UPDATE project_notes
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = NEW.id;
            END;
            """
        )

        conn.commit()
        print("[✓] project_notes table ready.")
    except Exception as e:
        print("[X] Error creating project_notes table:", e)
        conn.rollback()
        raise
    finally:
        conn.close()
        print("[*] Connection closed.")


if __name__ == "__main__":
    main()
