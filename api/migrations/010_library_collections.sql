-- Migration 010: Library Collections
-- Organize library files into named collections (flat structure)

BEGIN TRANSACTION;

-- ============================================================================
-- LIBRARY COLLECTIONS
-- Named groups of library files (e.g., "Founding Era", "Patristics")
-- ============================================================================

CREATE TABLE IF NOT EXISTS library_collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    color TEXT DEFAULT '#6366f1',  -- Accent color for UI
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- COLLECTION FILES (JUNCTION TABLE)
-- Many-to-many: files can belong to multiple collections
-- ============================================================================

CREATE TABLE IF NOT EXISTS library_collection_files (
    collection_id INTEGER NOT NULL,
    library_file_id INTEGER NOT NULL,
    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (collection_id, library_file_id),
    FOREIGN KEY (collection_id) REFERENCES library_collections(id) ON DELETE CASCADE,
    FOREIGN KEY (library_file_id) REFERENCES library_files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_collection_files_collection ON library_collection_files(collection_id);
CREATE INDEX IF NOT EXISTS idx_collection_files_file ON library_collection_files(library_file_id);

COMMIT;
