-- Migration 009: Add GHM fields to projects and messages
-- Phase 8.2.7: Global Hermeneutic Mode

ALTER TABLE projects ADD COLUMN hermeneutic_mode TEXT DEFAULT NULL;
-- Values: 'ghm', 'none', or NULL (treated as none)

ALTER TABLE projects ADD COLUMN profile TEXT DEFAULT NULL;
-- Values: profile identifier string (e.g., 'pronomian_trajectory') or NULL

-- Index for quick filtering by mode
CREATE INDEX IF NOT EXISTS idx_projects_hermeneutic_mode ON projects(hermeneutic_mode);

-- GHM audit trail on messages
ALTER TABLE messages ADD COLUMN ghm_active BOOLEAN DEFAULT FALSE;
