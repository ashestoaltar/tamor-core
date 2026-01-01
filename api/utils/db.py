# api/utils/db.py
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB = BASE_DIR / "memory" / "tamor.db"

DB_PATH = os.getenv("MEMORY_DB") or os.getenv("TAMOR_DB") or str(DEFAULT_DB)


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

