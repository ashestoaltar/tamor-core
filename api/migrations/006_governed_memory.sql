-- Migration 006: Governed Memory System (Phase 6.1)
-- Adds governance controls, pinning, and settings to the memory system

-- Add new columns to memories table
-- Note: SQLite doesn't allow DEFAULT CURRENT_TIMESTAMP in ALTER TABLE, so we use NULL
ALTER TABLE memories ADD COLUMN source TEXT DEFAULT 'auto';
ALTER TABLE memories ADD COLUMN is_pinned INTEGER DEFAULT 0;
ALTER TABLE memories ADD COLUMN consent_at DATETIME;
ALTER TABLE memories ADD COLUMN updated_at DATETIME;

-- Create memory_settings table for per-user governance controls
CREATE TABLE IF NOT EXISTS memory_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    auto_save_enabled INTEGER DEFAULT 1,
    auto_save_categories TEXT DEFAULT '["identity","preference","project"]',
    max_pinned_memories INTEGER DEFAULT 10,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create index for pinned memories lookup
CREATE INDEX IF NOT EXISTS idx_memories_pinned ON memories(is_pinned);
CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(source);
CREATE INDEX IF NOT EXISTS idx_memory_settings_user ON memory_settings(user_id);
