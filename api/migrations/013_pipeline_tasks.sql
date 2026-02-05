-- Migration 013: Pipeline Tasks for Planner Agent
-- Tracks multi-step writing projects orchestrated by the Planner

CREATE TABLE IF NOT EXISTS pipeline_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    task_type TEXT NOT NULL,              -- 'research', 'draft', 'review', 'revise'
    task_description TEXT NOT NULL,
    agent TEXT NOT NULL,                  -- 'researcher', 'writer', 'planner'
    status TEXT DEFAULT 'pending',        -- 'pending', 'active', 'waiting_review', 'complete'
    input_context TEXT,                   -- JSON: references to prior task outputs
    output_summary TEXT,                  -- Brief summary of what this task produced
    output_conversation_id INTEGER,
    sequence_order INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (output_conversation_id) REFERENCES conversations(id)
);

-- Index for efficient project task lookups
CREATE INDEX IF NOT EXISTS idx_pipeline_tasks_project_id ON pipeline_tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_tasks_status ON pipeline_tasks(status);
