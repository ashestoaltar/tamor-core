-- Migration 005: Add transcripts table for media transcription (Phase 5.3)
-- Stores transcription results from audio/video files and URLs

CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    source_url TEXT,
    source_file_id INTEGER,
    title TEXT,
    duration_seconds REAL,
    transcript_text TEXT,
    segments_json TEXT,
    language TEXT,
    model_used TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (source_file_id) REFERENCES project_files(id)
);

CREATE INDEX IF NOT EXISTS idx_transcripts_project ON transcripts(project_id);
CREATE INDEX IF NOT EXISTS idx_transcripts_source ON transcripts(source_type);
