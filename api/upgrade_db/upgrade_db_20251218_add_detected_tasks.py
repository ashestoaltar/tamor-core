# api/upgrade_db/upgrade_db_20251218_add_detected_tasks.py
import sqlite3
from pathlib import Path
import os

# If your project already has a standard way to locate the DB,
# swap this to match it. This version tries common env + default paths.
def _resolve_db_path() -> str:
    env_path = os.getenv("MEMORY_DB") or os.getenv("TAMOR_DB")
    if env_path:
        return env_path

    # Common default based on your earlier /health output patterns
    candidates = [
        "/home/tamor/tamor-core/api/memory/tamor.db",
        str(Path(__file__).resolve().parents[2] / "api" / "memory" / "tamor.db"),
        str(Path(__file__).resolve().parents[1] / "memory" / "tamor.db"),
    ]
    for p in candidates:
        if Path(p).exists():
            return p

    # Fallback: create in expected location (last candidate)
    return candidates[0]


def _table_exists(cur: sqlite3.Cursor, name: str) -> bool:
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    )
    return cur.fetchone() is not None


def main():
    db_path = _resolve_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    if not _table_exists(cur, "detected_tasks"):
        cur.execute(
            """
            CREATE TABLE detected_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                project_id INTEGER,
                conversation_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,

                task_type TEXT NOT NULL,
                title TEXT,
                confidence REAL,
                payload_json TEXT,

                status TEXT NOT NULL DEFAULT 'detected',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        # Useful indexes for UI queries
        cur.execute(
            "CREATE INDEX idx_detected_tasks_conv_status ON detected_tasks(conversation_id, status);"
        )
        cur.execute(
            "CREATE INDEX idx_detected_tasks_msg ON detected_tasks(message_id);"
        )
        cur.execute(
            "CREATE INDEX idx_detected_tasks_user ON detected_tasks(user_id);"
        )

        conn.commit()
        print(f"[upgrade] created detected_tasks table in {db_path}")
    else:
        print("[upgrade] detected_tasks table already exists (no-op)")

    conn.close()


if __name__ == "__main__":
    main()
