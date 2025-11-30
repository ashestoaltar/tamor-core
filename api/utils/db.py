# utils/db.py
import sqlite3
from core.config import MEMORY_DB  # <- single source of truth

def get_db():
    """
    Return a sqlite3 connection to the Tamor memory DB,
    with row_factory set so we can use dict(row).
    """
    conn = sqlite3.connect(MEMORY_DB)
    conn.row_factory = sqlite3.Row
    return conn

