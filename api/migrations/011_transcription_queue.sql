-- Migration 011: Transcription Queue for Library Files
-- Background transcription queue for audio/video files in library

CREATE TABLE IF NOT EXISTS transcription_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    library_file_id INTEGER NOT NULL,
    model TEXT NOT NULL DEFAULT 'base',
    language TEXT,
    priority INTEGER DEFAULT 5,
    status TEXT NOT NULL DEFAULT 'pending',
    queued_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,
    result_library_file_id INTEGER,
    processing_time_seconds INTEGER,
    error_message TEXT,
    FOREIGN KEY (library_file_id) REFERENCES library_files(id) ON DELETE CASCADE,
    FOREIGN KEY (result_library_file_id) REFERENCES library_files(id)
);

CREATE INDEX IF NOT EXISTS idx_transcription_queue_status ON transcription_queue(status);
CREATE INDEX IF NOT EXISTS idx_transcription_queue_file ON transcription_queue(library_file_id);
CREATE INDEX IF NOT EXISTS idx_transcription_queue_priority ON transcription_queue(priority, queued_at);
