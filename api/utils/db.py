import os
import sqlite3

# BASE_DIR should be the /api folder, not /api/utils
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

DB_PATH = os.path.join(BASE_DIR, "tamor.db")


def get_db():
    """
    Return a sqlite3 connection to the main Tamor DB.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

