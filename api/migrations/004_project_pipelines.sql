-- Migration 004: Add project_pipelines table for workflow tracking (Phase 5.2)
-- Tracks pipeline state and progress for projects

CREATE TABLE IF NOT EXISTS project_pipelines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    pipeline_type TEXT NOT NULL,
    current_step INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    step_data_json TEXT,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE INDEX IF NOT EXISTS idx_project_pipelines_project ON project_pipelines(project_id);
CREATE INDEX IF NOT EXISTS idx_project_pipelines_status ON project_pipelines(status);
