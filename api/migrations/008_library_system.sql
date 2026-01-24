-- Migration 008: Global Library System (Phase 7.1)
-- Centralized knowledge repository with project references (no duplication)

BEGIN TRANSACTION;

-- ============================================================================
-- LIBRARY CONFIG
-- Key-value store for library settings (mount path, etc.)
-- ============================================================================

CREATE TABLE IF NOT EXISTS library_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Default mount path
INSERT OR IGNORE INTO library_config (key, value) VALUES ('mount_path', '/mnt/library');

-- ============================================================================
-- LIBRARY FILES
-- Central repository for all documents, media, and transcripts
-- ============================================================================

CREATE TABLE IF NOT EXISTS library_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,              -- Full path on NAS/filesystem
    mime_type TEXT,
    size_bytes INTEGER,
    file_hash TEXT,                         -- SHA-256 for deduplication
    source_type TEXT DEFAULT 'manual',      -- 'manual', 'scan', 'transcription'
    source_path TEXT,                       -- Original path if ingested
    source_library_file_id INTEGER,         -- For transcripts: link to source audio/video
    metadata_json TEXT,                     -- Title, author, chapters, etc.
    text_content TEXT,                      -- Extracted text (cached)
    text_extracted_at DATETIME,
    last_indexed_at DATETIME,               -- When embeddings were generated
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_library_file_id) REFERENCES library_files(id)
);

-- Unique constraint on hash to prevent duplicates
CREATE UNIQUE INDEX IF NOT EXISTS idx_library_files_hash ON library_files(file_hash);
CREATE INDEX IF NOT EXISTS idx_library_files_mime ON library_files(mime_type);
CREATE INDEX IF NOT EXISTS idx_library_files_source ON library_files(source_type);
CREATE INDEX IF NOT EXISTS idx_library_files_filename ON library_files(filename);
CREATE INDEX IF NOT EXISTS idx_library_files_source_file ON library_files(source_library_file_id);

-- ============================================================================
-- LIBRARY TEXT CACHE
-- Separate table for extracted text (allows large text without bloating main table)
-- ============================================================================

CREATE TABLE IF NOT EXISTS library_text_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    library_file_id INTEGER NOT NULL UNIQUE,
    text_content TEXT,                          -- Extracted text content
    meta_json TEXT,                             -- Parsing metadata (page count, etc.)
    parser TEXT,                                -- Parser used (pdf, docx, txt, etc.)
    extracted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (library_file_id) REFERENCES library_files(id) ON DELETE CASCADE
);

-- ============================================================================
-- LIBRARY CHUNKS
-- Embeddings for library files (similar to file_chunks but library-scoped)
-- ============================================================================

CREATE TABLE IF NOT EXISTS library_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    library_file_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT,
    embedding BLOB,
    page INTEGER,                           -- Source page if applicable
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (library_file_id) REFERENCES library_files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_library_chunks_file ON library_chunks(library_file_id);
CREATE INDEX IF NOT EXISTS idx_library_chunks_file_index ON library_chunks(library_file_id, chunk_index);

-- ============================================================================
-- PROJECT LIBRARY REFERENCES
-- Links projects to library items (reference model, no file duplication)
-- ============================================================================

CREATE TABLE IF NOT EXISTS project_library_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    library_file_id INTEGER NOT NULL,
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    added_by INTEGER,                       -- user_id who added the reference
    notes TEXT,                             -- Optional user notes about this reference
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (library_file_id) REFERENCES library_files(id) ON DELETE CASCADE,
    FOREIGN KEY (added_by) REFERENCES users(id),
    UNIQUE(project_id, library_file_id)     -- Prevent duplicate refs
);

CREATE INDEX IF NOT EXISTS idx_project_library_refs_project ON project_library_refs(project_id);
CREATE INDEX IF NOT EXISTS idx_project_library_refs_file ON project_library_refs(library_file_id);

COMMIT;
