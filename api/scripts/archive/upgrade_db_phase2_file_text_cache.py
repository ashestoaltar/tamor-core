#!/usr/bin/env python
import sqlite3
import os
from pathlib import Path

DB_PATH = os.environ.get("TAMOR_DB_PATH", "memory.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS file_text_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL UNIQUE,
    text TEXT,
    meta_json TEXT,
    parser TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES project_files(id)
);
CREATE INDEX IF NOT EXISTS idx_file_text_cache_file
  ON file_text_cache(file_id);
"""

def main():
    db_path = Path(DB_PATH)
    if not db_path.exists():
        raise SystemExit(f"DB not found at {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.executescript(SCHEMA_SQL)
        conn.commit()
        print("file_text_cache migration complete.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
