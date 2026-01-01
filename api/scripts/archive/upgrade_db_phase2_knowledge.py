"""
Phase 2.3 migration: file_symbols table for project knowledge graph.

Usage:
    cd /home/tamor/tamor-core/api
    python upgrade_db_phase2_knowledge.py
"""

from utils.db import get_db


def main() -> None:
    conn = get_db()
    cur = conn.cursor()

    # Core table: each row is one extracted symbol from a file
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS file_symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            file_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            value TEXT,
            line_number INTEGER,
            snippet TEXT,
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
        CREATE INDEX IF NOT EXISTS idx_file_symbols_project
        ON file_symbols(project_id);
        """
    )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_file_symbols_symbol
        ON file_symbols(symbol);
        """
    )

    conn.commit()
    conn.close()
    print("✅ file_symbols table created / verified.")


if __name__ == "__main__":
    main()
