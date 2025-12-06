# upgrade_db_message_file_refs.py
"""
One-time migration to add a message_file_refs table for linking
messages to uploaded project files.

Usage:
  cd /home/tamor/tamor-core/api
  source venv/bin/activate
  python upgrade_db_message_file_refs.py
"""

from utils.db import get_db


def main() -> None:
    conn = get_db()
    cur = conn.cursor()

    # Core link table between messages and project_files
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS message_file_refs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            file_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(message_id) REFERENCES messages(id),
            FOREIGN KEY(file_id) REFERENCES project_files(id)
        )
        """
    )

    # Helpful indexes for lookups
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_message_file_refs_message_id
        ON message_file_refs(message_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_message_file_refs_file_id
        ON message_file_refs(file_id)
        """
    )

    conn.commit()
    conn.close()
    print("Migration complete: message_file_refs table is ready.")


if __name__ == "__main__":
    main()
