-- Migration 002: Add file_insights table for auto-insights (Phase 4.1)
-- Stores automatically generated insights for project files

CREATE TABLE IF NOT EXISTS file_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL UNIQUE,
    project_id INTEGER NOT NULL,
    insights_json TEXT,           -- Full structured insights (themes, contradictions, etc.)
    summary TEXT,                 -- Brief summary of the file
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    model_used TEXT,              -- Which LLM model generated this
    FOREIGN KEY (file_id) REFERENCES project_files(id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE INDEX IF NOT EXISTS idx_file_insights_project ON file_insights(project_id);
CREATE INDEX IF NOT EXISTS idx_file_insights_file ON file_insights(file_id);
