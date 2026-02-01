-- Migration: 012_reading_sessions
-- Phase 5.5: Integrated Reader
-- Created: 2026-02-01
--
-- Tracks reading progress across visual and audio modes.
-- Supports content from project files, library files, and transcripts.

-- Reading sessions table
CREATE TABLE IF NOT EXISTS reading_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,

    -- Content source (exactly one should be set)
    file_id INTEGER,              -- project_files reference
    library_file_id INTEGER,      -- library_files reference
    transcript_id INTEGER,        -- transcripts reference
    content_type TEXT NOT NULL,   -- 'file', 'library', 'transcript'

    -- Progress tracking
    position_char INTEGER DEFAULT 0,        -- visual reading position
    position_seconds REAL DEFAULT 0.0,      -- audio playback position
    total_chars INTEGER,                    -- total content length
    total_seconds REAL,                     -- total audio duration (if generated)

    -- Mode and settings
    mode TEXT DEFAULT 'visual',             -- 'visual', 'audio', 'both'
    status TEXT DEFAULT 'in_progress',      -- 'in_progress', 'completed', 'abandoned'
    tts_voice TEXT,                         -- e.g., 'en_US-lessac-medium'
    tts_speed REAL DEFAULT 1.0,             -- playback speed multiplier

    -- Bookmarks (JSON array of {char, label, created_at})
    bookmarks_json TEXT DEFAULT '[]',

    -- Timestamps
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_accessed TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,

    -- Stats
    total_reading_time_seconds INTEGER DEFAULT 0,

    -- Foreign keys
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES project_files(id) ON DELETE CASCADE,
    FOREIGN KEY (library_file_id) REFERENCES library_files(id) ON DELETE CASCADE,
    FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE,

    -- Ensure exactly one content source
    CHECK (
        (file_id IS NOT NULL AND library_file_id IS NULL AND transcript_id IS NULL) OR
        (file_id IS NULL AND library_file_id IS NOT NULL AND transcript_id IS NULL) OR
        (file_id IS NULL AND library_file_id IS NULL AND transcript_id IS NOT NULL)
    )
);

-- Indexes for reading_sessions
CREATE INDEX IF NOT EXISTS idx_reading_sessions_user ON reading_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_reading_sessions_file ON reading_sessions(file_id);
CREATE INDEX IF NOT EXISTS idx_reading_sessions_library ON reading_sessions(library_file_id);
CREATE INDEX IF NOT EXISTS idx_reading_sessions_transcript ON reading_sessions(transcript_id);
CREATE INDEX IF NOT EXISTS idx_reading_sessions_last_accessed ON reading_sessions(last_accessed DESC);
CREATE INDEX IF NOT EXISTS idx_reading_sessions_status ON reading_sessions(user_id, status);


-- Audio cache for pre-generated TTS chunks
CREATE TABLE IF NOT EXISTS reader_audio_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Content source (same pattern as reading_sessions)
    file_id INTEGER,
    library_file_id INTEGER,
    transcript_id INTEGER,
    content_type TEXT NOT NULL,

    -- Chunk identification
    chunk_index INTEGER NOT NULL,           -- sequential chunk number
    chunk_start_char INTEGER NOT NULL,      -- start position in source text
    chunk_end_char INTEGER NOT NULL,        -- end position in source text
    chunk_text TEXT,                        -- the text that was converted (for verification)

    -- Audio file info
    audio_path TEXT NOT NULL,               -- path to generated WAV file
    duration_seconds REAL,                  -- audio duration

    -- Generation settings (for cache invalidation)
    tts_voice TEXT NOT NULL,
    tts_speed REAL NOT NULL DEFAULT 1.0,

    -- Timestamps
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (file_id) REFERENCES project_files(id) ON DELETE CASCADE,
    FOREIGN KEY (library_file_id) REFERENCES library_files(id) ON DELETE CASCADE,
    FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE
);

-- Indexes for audio cache
CREATE INDEX IF NOT EXISTS idx_audio_cache_file ON reader_audio_cache(file_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_audio_cache_library ON reader_audio_cache(library_file_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_audio_cache_transcript ON reader_audio_cache(transcript_id, chunk_index);

-- Unique constraint: one cached chunk per content + chunk_index + voice + speed
CREATE UNIQUE INDEX IF NOT EXISTS idx_audio_cache_unique_file
    ON reader_audio_cache(file_id, chunk_index, tts_voice, tts_speed)
    WHERE file_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_audio_cache_unique_library
    ON reader_audio_cache(library_file_id, chunk_index, tts_voice, tts_speed)
    WHERE library_file_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_audio_cache_unique_transcript
    ON reader_audio_cache(transcript_id, chunk_index, tts_voice, tts_speed)
    WHERE transcript_id IS NOT NULL;
