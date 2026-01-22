-- Tamor Database Schema
-- Last updated: 2026-01-21 (Phase 3.3)
--
-- This file documents the current database schema.
-- For migrations, see ../migrations/
--
-- Migration tracking: Uses migrations table (replaces legacy schema_version)
-- Schema Version: 1

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT,
    password_hash TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Projects for organizing content
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Conversations (chat sessions)
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    project_id INTEGER,
    title TEXT,
    mode TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Chat messages
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    sender TEXT,
    role TEXT,
    content TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

-- ============================================================================
-- TASK SYSTEM
-- ============================================================================

-- Detected tasks from chat messages
CREATE TABLE IF NOT EXISTS detected_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    project_id INTEGER,
    conversation_id INTEGER,
    message_id INTEGER,
    task_type TEXT,
    title TEXT,
    confidence REAL,
    payload_json TEXT,
    normalized_json TEXT,
    status TEXT DEFAULT 'needs_confirmation',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    FOREIGN KEY (message_id) REFERENCES messages(id)
);

-- Task execution history
CREATE TABLE IF NOT EXISTS task_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME,
    status TEXT NOT NULL,
    error_text TEXT,
    FOREIGN KEY (task_id) REFERENCES detected_tasks(id)
);

CREATE INDEX IF NOT EXISTS idx_task_runs_task ON task_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_task_runs_status ON task_runs(status);

-- ============================================================================
-- FILE SYSTEM
-- ============================================================================

-- Project files
CREATE TABLE IF NOT EXISTS project_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    project_id INTEGER NOT NULL,
    conversation_id INTEGER,
    filename TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

-- File text extraction cache
CREATE TABLE IF NOT EXISTS file_text_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    text TEXT,
    meta_json TEXT,
    parser TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES project_files(id)
);

-- File chunks for semantic search
CREATE TABLE IF NOT EXISTS file_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    file_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT,
    embedding BLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (file_id) REFERENCES project_files(id)
);

-- File insights for auto-analysis (Phase 4.1)
CREATE TABLE IF NOT EXISTS file_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL UNIQUE,
    project_id INTEGER NOT NULL,
    insights_json TEXT,
    summary TEXT,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    model_used TEXT,
    FOREIGN KEY (file_id) REFERENCES project_files(id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE INDEX IF NOT EXISTS idx_file_insights_project ON file_insights(project_id);
CREATE INDEX IF NOT EXISTS idx_file_insights_file ON file_insights(file_id);

-- Project reasoning for cross-document analysis (Phase 4.2)
CREATE TABLE IF NOT EXISTS project_reasoning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    reasoning_type TEXT NOT NULL,
    result_json TEXT NOT NULL,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    model_used TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE INDEX IF NOT EXISTS idx_project_reasoning_project ON project_reasoning(project_id);
CREATE INDEX IF NOT EXISTS idx_project_reasoning_type ON project_reasoning(project_id, reasoning_type);

-- Message to file references
CREATE TABLE IF NOT EXISTS message_file_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    file_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id),
    FOREIGN KEY (file_id) REFERENCES project_files(id)
);

-- ============================================================================
-- KNOWLEDGE GRAPH
-- ============================================================================

-- Extracted symbols from files
CREATE TABLE IF NOT EXISTS file_symbols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    file_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    value TEXT,
    line_number INTEGER,
    char_offset INTEGER,
    snippet TEXT,
    embedding BLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (file_id) REFERENCES project_files(id)
);

-- ============================================================================
-- MEMORY SYSTEM
-- ============================================================================

-- Long-term memories with embeddings
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    conversation_id INTEGER,
    message_id INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    category TEXT,
    content TEXT,
    embedding BLOB,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    FOREIGN KEY (message_id) REFERENCES messages(id)
);

-- ============================================================================
-- PROJECT NOTES
-- ============================================================================

-- User notes on projects
CREATE TABLE IF NOT EXISTS project_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    content TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- ============================================================================
-- INTENT SYSTEM
-- ============================================================================

-- Pending intents for disambiguation
CREATE TABLE IF NOT EXISTS pending_intents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    original_title TEXT,
    candidates TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

-- ============================================================================
-- MIGRATION TRACKING
-- ============================================================================

-- New migration tracking with history
CREATE TABLE IF NOT EXISTS migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version INTEGER NOT NULL,
    name TEXT NOT NULL,
    checksum TEXT,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(version)
);

-- Legacy schema version (kept for backwards compatibility)
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

-- Initialize schema version if empty
INSERT INTO schema_version (version)
SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_version);
