-- Migration 014: Tiered Memory System (Phase 9.1)
-- Redesigns memory from flat pinned/unpinned to tiered architecture:
--   core: always loaded (identity, values, fundamental preferences)
--   long_term: searchable, subject to decay (knowledge, preferences, project facts)
--   episodic: session summaries, fade over time
--   working: ephemeral, not persisted (handled in-memory, not in DB)

-- Add tier and lifecycle columns to memories table
-- Note: CHECK constraint not supported in SQLite ALTER TABLE; enforced in application layer
ALTER TABLE memories ADD COLUMN memory_tier TEXT DEFAULT 'long_term';
ALTER TABLE memories ADD COLUMN last_accessed DATETIME;
ALTER TABLE memories ADD COLUMN access_count INTEGER DEFAULT 0;
ALTER TABLE memories ADD COLUMN confidence REAL DEFAULT 0.5;
ALTER TABLE memories ADD COLUMN summary TEXT;

-- Entity table for knowledge graph nodes
CREATE TABLE IF NOT EXISTS memory_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,  -- person, project, tool, concept, organization, source
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, entity_type)
);

-- Relationship links between memories and entities
CREATE TABLE IF NOT EXISTS memory_entity_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id INTEGER NOT NULL,
    entity_id INTEGER NOT NULL,
    relationship TEXT NOT NULL,  -- about, mentions, created_by, uses, teaches, etc.
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE,
    FOREIGN KEY (entity_id) REFERENCES memory_entities(id) ON DELETE CASCADE,
    UNIQUE(memory_id, entity_id, relationship)
);

-- Indexes for tiered retrieval
CREATE INDEX IF NOT EXISTS idx_memories_tier ON memories(memory_tier);
CREATE INDEX IF NOT EXISTS idx_memories_last_accessed ON memories(last_accessed);
CREATE INDEX IF NOT EXISTS idx_memories_confidence ON memories(confidence);
CREATE INDEX IF NOT EXISTS idx_memory_entity_links_memory ON memory_entity_links(memory_id);
CREATE INDEX IF NOT EXISTS idx_memory_entity_links_entity ON memory_entity_links(entity_id);
CREATE INDEX IF NOT EXISTS idx_memory_entities_type ON memory_entities(entity_type);

-- Backfill existing memories into tiers based on category
-- Core tier: identity, purpose, philosophy (fundamental, always relevant)
UPDATE memories SET memory_tier = 'core', confidence = 0.9
    WHERE category IN ('identity', 'purpose', 'philosophy');

-- Episodic tier: conversation fragments
UPDATE memories SET memory_tier = 'episodic', confidence = 0.3
    WHERE category IN ('conversation', 'reminder');

-- Long-term tier: everything else (default, already set by column default)
UPDATE memories SET confidence = 0.7
    WHERE memory_tier = 'long_term' AND category IN ('preference', 'preferences', 'project', 'theology', 'engineering', 'music');

UPDATE memories SET confidence = 0.5
    WHERE memory_tier = 'long_term' AND confidence = 0.5
    AND category IN ('knowledge', 'knowledge_code', 'knowledge_theology');

-- Set last_accessed to created time for existing memories
UPDATE memories SET last_accessed = COALESCE(updated_at, timestamp);
