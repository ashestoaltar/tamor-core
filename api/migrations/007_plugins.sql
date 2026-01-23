-- Migration 007: Plugin Framework (Phase 6.3)
-- Adds tables for tracking plugin configurations and import history

-- Track which plugins are enabled per project with their configuration
CREATE TABLE IF NOT EXISTS project_plugins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    plugin_id TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    config_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(project_id, plugin_id)
);

-- Track imported items for provenance and history
CREATE TABLE IF NOT EXISTS plugin_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    plugin_id TEXT NOT NULL,
    file_id INTEGER,
    source_path TEXT,
    imported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES project_files(id) ON DELETE SET NULL
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_project_plugins_project ON project_plugins(project_id);
CREATE INDEX IF NOT EXISTS idx_plugin_imports_project ON plugin_imports(project_id);
CREATE INDEX IF NOT EXISTS idx_plugin_imports_plugin ON plugin_imports(plugin_id);
CREATE INDEX IF NOT EXISTS idx_plugin_imports_file ON plugin_imports(file_id);
