-- Migration 003: Add project_reasoning table for multi-file reasoning (Phase 4.2)
-- Stores cross-document analysis results: relationships, contradictions, logic flow

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
