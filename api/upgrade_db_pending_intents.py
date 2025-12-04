"""
Upgrade script: add `pending_intents` table for per-conversation pending flows.

Usage:
    python upgrade_db_pending_intents.py
"""

import os
import sqlite3
from datetime import datetime

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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_intents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                original_title TEXT,
                candidates TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(conversation_id)
            );
            """
        )

        # Trigger to keep updated_at fresh on UPDATE.
        cur.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_pending_intents_updated_at
            AFTER UPDATE ON pending_intents
            BEGIN
                UPDATE pending_intents
                SET updated_at = datetime('now')
                WHERE id = NEW.id;
            END;
            """
        )

        conn.commit()
        print("[✓] pending_intents table ready.")
    except Exception as e:
        print("[X] Error creating pending_intents table:", e)
        conn.rollback()
        raise
    finally:
        conn.close()
        print("[*] Connection closed.")


if __name__ == "__main__":
    main()
