# upgrade_db_phase2_filesearch.py
"""
Phase 2.1 migration: file_chunks table for semantic multi-file search.

Usage:
    cd /home/tamor/tamor-core/api
    python upgrade_db_phase2_filesearch.py
"""

from utils.db import get_db


def main() -> None:
    conn = get_db()
    cur = conn.cursor()

    # Core table: each row is one embedded chunk from a file
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS file_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            file_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (file_id) REFERENCES project_files(id)
        );
        """
    )

    # Helpful indexes
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_file_chunks_project
        ON file_chunks(project_id);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_file_chunks_file
        ON file_chunks(file_id);
        """
    )

    conn.commit()
    conn.close()
    print("✅ file_chunks table created / verified.")


if __name__ == "__main__":
    main()
