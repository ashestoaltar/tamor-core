"""
Reader Service

Phase 5.5: Integrated Reader.

Provides:
- Content retrieval from project files, library files, and transcripts
- Reading session management with progress tracking
- Bookmark support
- TTS audio generation integration
- Reading statistics

Works with tts_service.py for audio synthesis.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.db import get_db

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ReaderContent:
    """Content prepared for the reader."""
    content_type: str  # 'file', 'library', 'transcript'
    content_id: int
    title: str
    text: str
    total_chars: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    # For transcripts with timed segments
    segments: Optional[List[Dict]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReadingSession:
    """A reading session with progress tracking."""
    id: int
    user_id: int
    content_type: str
    content_id: int
    position_char: int
    position_seconds: float
    total_chars: Optional[int]
    total_seconds: Optional[float]
    mode: str  # 'visual', 'audio', 'both'
    status: str  # 'in_progress', 'completed', 'abandoned'
    tts_voice: Optional[str]
    tts_speed: float
    bookmarks: List[Dict]
    started_at: str
    last_accessed: str
    completed_at: Optional[str]
    total_reading_time_seconds: int
    # Populated when fetching with content
    title: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if not self.total_chars or self.total_chars == 0:
            return 0.0
        return min(100.0, (self.position_char / self.total_chars) * 100)


# =============================================================================
# Content Retrieval
# =============================================================================

def get_content_for_reader(
    content_type: str,
    content_id: int,
    user_id: int,
) -> Optional[ReaderContent]:
    """
    Get content for reading.

    Args:
        content_type: 'file', 'library', or 'transcript'
        content_id: ID of the content
        user_id: User requesting access (for permission check)

    Returns:
        ReaderContent or None if not found/not accessible
    """
    if content_type == "file":
        return _get_file_content(content_id, user_id)
    elif content_type == "library":
        return _get_library_content(content_id, user_id)
    elif content_type == "transcript":
        return _get_transcript_content(content_id, user_id)
    else:
        logger.warning(f"Unknown content type: {content_type}")
        return None


def _get_file_content(file_id: int, user_id: int) -> Optional[ReaderContent]:
    """Get project file content with access verification."""
    conn = get_db()

    # Get file with user verification
    cur = conn.execute(
        """
        SELECT pf.*, p.name as project_name
        FROM project_files pf
        JOIN projects p ON pf.project_id = p.id
        WHERE pf.id = ? AND p.user_id = ?
        """,
        (file_id, user_id),
    )
    file_row = cur.fetchone()

    if not file_row:
        return None

    # Get cached text
    cur = conn.execute(
        "SELECT text, meta_json, parser FROM file_text_cache WHERE file_id = ?",
        (file_id,),
    )
    cache_row = cur.fetchone()

    if not cache_row or not cache_row["text"]:
        # Text not cached - would need to extract
        # For now, return None (extraction should happen elsewhere)
        logger.warning(f"No cached text for project file {file_id}")
        return None

    text = cache_row["text"]
    meta = {}
    if cache_row["meta_json"]:
        try:
            meta = json.loads(cache_row["meta_json"])
        except json.JSONDecodeError:
            pass

    return ReaderContent(
        content_type="file",
        content_id=file_id,
        title=file_row["filename"],
        text=text,
        total_chars=len(text),
        metadata={
            "project_id": file_row["project_id"],
            "project_name": file_row["project_name"],
            "mime_type": file_row["mime_type"],
            "parser": cache_row["parser"],
            **meta,
        },
    )


def _get_library_content(library_file_id: int, user_id: int) -> Optional[ReaderContent]:
    """Get library file content (library is shared, no user restriction)."""
    conn = get_db()

    # Get file info
    cur = conn.execute(
        "SELECT * FROM library_files WHERE id = ?",
        (library_file_id,),
    )
    file_row = cur.fetchone()

    if not file_row:
        return None

    # Get cached text
    cur = conn.execute(
        "SELECT text_content, meta_json, parser FROM library_text_cache WHERE library_file_id = ?",
        (library_file_id,),
    )
    cache_row = cur.fetchone()

    if not cache_row or not cache_row["text_content"]:
        # Try to extract text using LibraryTextService
        try:
            from services.library.text_service import LibraryTextService
            text_service = LibraryTextService()
            text, meta = text_service.get_text(library_file_id)
            if not text:
                return None
        except Exception as e:
            logger.error(f"Failed to get library text: {e}")
            return None
    else:
        text = cache_row["text_content"]
        meta = {}
        if cache_row["meta_json"]:
            try:
                meta = json.loads(cache_row["meta_json"])
            except json.JSONDecodeError:
                pass

    # Parse file metadata
    file_meta = {}
    if file_row["metadata_json"]:
        try:
            file_meta = json.loads(file_row["metadata_json"])
        except json.JSONDecodeError:
            pass

    return ReaderContent(
        content_type="library",
        content_id=library_file_id,
        title=file_row["filename"],
        text=text,
        total_chars=len(text),
        metadata={
            "mime_type": file_row["mime_type"],
            "stored_path": file_row["stored_path"],
            "source_type": file_row["source_type"],
            **file_meta,
            **meta,
        },
    )


def _get_transcript_content(transcript_id: int, user_id: int) -> Optional[ReaderContent]:
    """Get transcript content with access verification."""
    conn = get_db()

    # Get transcript with user verification
    cur = conn.execute(
        """
        SELECT t.*, p.name as project_name
        FROM transcripts t
        JOIN projects p ON t.project_id = p.id
        WHERE t.id = ? AND p.user_id = ?
        """,
        (transcript_id, user_id),
    )
    row = cur.fetchone()

    if not row:
        return None

    text = row["transcript_text"] or ""

    # Parse segments
    segments = None
    if row["segments_json"]:
        try:
            segments = json.loads(row["segments_json"])
        except json.JSONDecodeError:
            pass

    return ReaderContent(
        content_type="transcript",
        content_id=transcript_id,
        title=row["title"] or "Untitled Transcript",
        text=text,
        total_chars=len(text),
        metadata={
            "project_id": row["project_id"],
            "project_name": row["project_name"],
            "source_type": row["source_type"],
            "source_url": row["source_url"],
            "duration_seconds": row["duration_seconds"],
            "language": row["language"],
            "model_used": row["model_used"],
        },
        segments=segments,
    )


# =============================================================================
# Session Management
# =============================================================================

def get_or_create_session(
    user_id: int,
    content_type: str,
    content_id: int,
    mode: str = "visual",
) -> Optional[ReadingSession]:
    """
    Get an existing incomplete session or create a new one.

    Args:
        user_id: User ID
        content_type: 'file', 'library', or 'transcript'
        content_id: Content ID
        mode: Reading mode ('visual', 'audio', 'both')

    Returns:
        ReadingSession or None if content not accessible
    """
    conn = get_db()

    # Build the query based on content type
    if content_type == "file":
        id_column = "file_id"
    elif content_type == "library":
        id_column = "library_file_id"
    elif content_type == "transcript":
        id_column = "transcript_id"
    else:
        return None

    # Look for existing incomplete session
    cur = conn.execute(
        f"""
        SELECT * FROM reading_sessions
        WHERE user_id = ? AND {id_column} = ? AND status = 'in_progress'
        ORDER BY last_accessed DESC
        LIMIT 1
        """,
        (user_id, content_id),
    )
    row = cur.fetchone()

    if row:
        return _row_to_session(row)

    # Get content to verify access and get total_chars
    content = get_content_for_reader(content_type, content_id, user_id)
    if not content:
        return None

    # Create new session
    cur = conn.execute(
        f"""
        INSERT INTO reading_sessions (
            user_id, {id_column}, content_type,
            total_chars, mode
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, content_id, content_type, content.total_chars, mode),
    )
    conn.commit()

    return get_session(cur.lastrowid, user_id)


def get_session(session_id: int, user_id: int) -> Optional[ReadingSession]:
    """Get a reading session by ID."""
    conn = get_db()
    cur = conn.execute(
        "SELECT * FROM reading_sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    )
    row = cur.fetchone()
    return _row_to_session(row) if row else None


def update_session_progress(
    session_id: int,
    user_id: int,
    position_char: int = None,
    position_seconds: float = None,
    reading_time_delta: int = None,
) -> Optional[ReadingSession]:
    """
    Update session progress.

    Args:
        session_id: Session ID
        user_id: User ID
        position_char: New character position
        position_seconds: New audio position (seconds)
        reading_time_delta: Seconds to add to total reading time

    Returns:
        Updated session or None
    """
    session = get_session(session_id, user_id)
    if not session:
        return None

    conn = get_db()
    updates = ["last_accessed = CURRENT_TIMESTAMP"]
    params = []

    if position_char is not None:
        updates.append("position_char = ?")
        params.append(position_char)

    if position_seconds is not None:
        updates.append("position_seconds = ?")
        params.append(position_seconds)

    if reading_time_delta is not None and reading_time_delta > 0:
        updates.append("total_reading_time_seconds = total_reading_time_seconds + ?")
        params.append(reading_time_delta)

    params.extend([session_id, user_id])

    conn.execute(
        f"""
        UPDATE reading_sessions
        SET {', '.join(updates)}
        WHERE id = ? AND user_id = ?
        """,
        params,
    )
    conn.commit()

    return get_session(session_id, user_id)


def complete_session(session_id: int, user_id: int) -> Optional[ReadingSession]:
    """Mark a session as completed."""
    session = get_session(session_id, user_id)
    if not session:
        return None

    conn = get_db()
    conn.execute(
        """
        UPDATE reading_sessions
        SET status = 'completed',
            completed_at = CURRENT_TIMESTAMP,
            last_accessed = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        """,
        (session_id, user_id),
    )
    conn.commit()

    return get_session(session_id, user_id)


def abandon_session(session_id: int, user_id: int) -> Optional[ReadingSession]:
    """Mark a session as abandoned."""
    session = get_session(session_id, user_id)
    if not session:
        return None

    conn = get_db()
    conn.execute(
        """
        UPDATE reading_sessions
        SET status = 'abandoned', last_accessed = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        """,
        (session_id, user_id),
    )
    conn.commit()

    return get_session(session_id, user_id)


def get_recent_sessions(
    user_id: int,
    limit: int = 10,
    include_completed: bool = False,
) -> List[ReadingSession]:
    """
    Get recent reading sessions for a user.

    Args:
        user_id: User ID
        limit: Maximum sessions to return
        include_completed: Include completed sessions

    Returns:
        List of ReadingSession
    """
    conn = get_db()

    status_filter = "" if include_completed else "AND status = 'in_progress'"

    cur = conn.execute(
        f"""
        SELECT * FROM reading_sessions
        WHERE user_id = ? {status_filter}
        ORDER BY last_accessed DESC
        LIMIT ?
        """,
        (user_id, limit),
    )

    sessions = [_row_to_session(row) for row in cur.fetchall()]

    # Enrich with titles
    for session in sessions:
        content = get_content_for_reader(
            session.content_type, session.content_id, user_id
        )
        if content:
            session.title = content.title

    return sessions


def _row_to_session(row) -> ReadingSession:
    """Convert database row to ReadingSession."""
    # Determine content_id from the appropriate column
    if row["file_id"]:
        content_id = row["file_id"]
    elif row["library_file_id"]:
        content_id = row["library_file_id"]
    else:
        content_id = row["transcript_id"]

    # Parse bookmarks
    bookmarks = []
    if row["bookmarks_json"]:
        try:
            bookmarks = json.loads(row["bookmarks_json"])
        except json.JSONDecodeError:
            pass

    return ReadingSession(
        id=row["id"],
        user_id=row["user_id"],
        content_type=row["content_type"],
        content_id=content_id,
        position_char=row["position_char"] or 0,
        position_seconds=row["position_seconds"] or 0.0,
        total_chars=row["total_chars"],
        total_seconds=row["total_seconds"],
        mode=row["mode"] or "visual",
        status=row["status"] or "in_progress",
        tts_voice=row["tts_voice"],
        tts_speed=row["tts_speed"] or 1.0,
        bookmarks=bookmarks,
        started_at=row["started_at"],
        last_accessed=row["last_accessed"],
        completed_at=row["completed_at"],
        total_reading_time_seconds=row["total_reading_time_seconds"] or 0,
    )


# =============================================================================
# Bookmarks
# =============================================================================

def add_bookmark(
    session_id: int,
    user_id: int,
    position_char: int,
    label: str = None,
) -> Optional[ReadingSession]:
    """
    Add a bookmark to a session.

    Args:
        session_id: Session ID
        user_id: User ID
        position_char: Character position for the bookmark
        label: Optional label for the bookmark

    Returns:
        Updated session or None
    """
    session = get_session(session_id, user_id)
    if not session:
        return None

    bookmarks = session.bookmarks.copy()
    bookmarks.append({
        "char": position_char,
        "label": label or f"Bookmark {len(bookmarks) + 1}",
        "created_at": datetime.now().isoformat(),
    })

    conn = get_db()
    conn.execute(
        """
        UPDATE reading_sessions
        SET bookmarks_json = ?, last_accessed = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        """,
        (json.dumps(bookmarks), session_id, user_id),
    )
    conn.commit()

    return get_session(session_id, user_id)


def remove_bookmark(
    session_id: int,
    user_id: int,
    bookmark_index: int,
) -> Optional[ReadingSession]:
    """
    Remove a bookmark from a session.

    Args:
        session_id: Session ID
        user_id: User ID
        bookmark_index: Index of bookmark to remove (0-based)

    Returns:
        Updated session or None
    """
    session = get_session(session_id, user_id)
    if not session:
        return None

    bookmarks = session.bookmarks.copy()

    if 0 <= bookmark_index < len(bookmarks):
        bookmarks.pop(bookmark_index)

        conn = get_db()
        conn.execute(
            """
            UPDATE reading_sessions
            SET bookmarks_json = ?, last_accessed = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (json.dumps(bookmarks), session_id, user_id),
        )
        conn.commit()

    return get_session(session_id, user_id)


# =============================================================================
# TTS Integration
# =============================================================================

def generate_audio_for_session(
    session_id: int,
    user_id: int,
    start_chunk: int = 0,
    num_chunks: int = 3,
) -> Dict[str, Any]:
    """
    Generate TTS audio for a reading session.

    Args:
        session_id: Session ID
        user_id: User ID
        start_chunk: Starting chunk index
        num_chunks: Number of chunks to generate

    Returns:
        Dict with chunks, audio info, or error
    """
    from services.tts_service import (
        chunk_text,
        synthesize_chunk,
        get_piper_status,
        DEFAULT_VOICE,
        DEFAULT_CHUNK_SIZE,
    )

    # Check TTS status
    status = get_piper_status()
    if not status["ready"]:
        return {"error": "TTS service not ready", "status": status}

    # Get session
    session = get_session(session_id, user_id)
    if not session:
        return {"error": "Session not found"}

    # Get content
    content = get_content_for_reader(
        session.content_type, session.content_id, user_id
    )
    if not content:
        return {"error": "Content not accessible"}

    # Get voice settings from session
    voice = session.tts_voice or DEFAULT_VOICE
    speed = session.tts_speed or 1.0

    # Chunk the text
    chunks = chunk_text(content.text, DEFAULT_CHUNK_SIZE, respect_sentences=True)

    if not chunks:
        return {"error": "No text to synthesize"}

    # Get requested chunk range
    end_chunk = min(start_chunk + num_chunks, len(chunks))
    requested_chunks = chunks[start_chunk:end_chunk]

    if not requested_chunks:
        return {"error": f"No chunks in range {start_chunk}-{end_chunk}"}

    # Synthesize each chunk
    results = []
    total_duration = 0.0

    for chunk in requested_chunks:
        audio_result = synthesize_chunk(chunk["text"], voice, speed)

        result = {
            "index": chunk["index"],
            "start_char": chunk["start_char"],
            "end_char": chunk["end_char"],
        }

        if audio_result.get("error"):
            result["error"] = audio_result["error"]
        else:
            result["audio_path"] = audio_result["path"]
            result["duration"] = audio_result.get("duration", 0)
            result["cached"] = audio_result.get("cached", False)
            total_duration += result["duration"]

        results.append(result)

    # Cache audio info in reader_audio_cache table
    _cache_audio_chunks(session, results, voice, speed, content.text)

    return {
        "session_id": session_id,
        "voice": voice,
        "speed": speed,
        "total_chunks": len(chunks),
        "generated_chunks": results,
        "start_chunk": start_chunk,
        "end_chunk": end_chunk,
        "total_duration": round(total_duration, 2),
    }


def _cache_audio_chunks(
    session: ReadingSession,
    chunks: List[Dict],
    voice: str,
    speed: float,
    full_text: str,
) -> None:
    """Cache audio chunk info in database."""
    conn = get_db()

    # Determine the content column
    if session.content_type == "file":
        id_column = "file_id"
    elif session.content_type == "library":
        id_column = "library_file_id"
    else:
        id_column = "transcript_id"

    for chunk in chunks:
        if chunk.get("error"):
            continue

        # Get chunk text
        chunk_text = full_text[chunk["start_char"]:chunk["end_char"]]

        try:
            conn.execute(
                f"""
                INSERT OR REPLACE INTO reader_audio_cache (
                    {id_column}, content_type, chunk_index,
                    chunk_start_char, chunk_end_char, chunk_text,
                    audio_path, duration_seconds, tts_voice, tts_speed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.content_id,
                    session.content_type,
                    chunk["index"],
                    chunk["start_char"],
                    chunk["end_char"],
                    chunk_text[:500],  # Store first 500 chars for verification
                    chunk["audio_path"],
                    chunk["duration"],
                    voice,
                    speed,
                ),
            )
        except Exception as e:
            logger.warning(f"Failed to cache audio chunk: {e}")

    conn.commit()


def get_chunk_for_position(
    session_id: int,
    user_id: int,
    char_position: int,
) -> Optional[Dict[str, Any]]:
    """
    Find which chunk contains a character position.

    Args:
        session_id: Session ID
        user_id: User ID
        char_position: Character position in text

    Returns:
        Dict with chunk info including cached audio if available
    """
    from services.tts_service import chunk_text, DEFAULT_CHUNK_SIZE

    session = get_session(session_id, user_id)
    if not session:
        return None

    content = get_content_for_reader(
        session.content_type, session.content_id, user_id
    )
    if not content:
        return None

    # Generate chunks
    chunks = chunk_text(content.text, DEFAULT_CHUNK_SIZE, respect_sentences=True)

    # Find the chunk containing this position
    for chunk in chunks:
        if chunk["start_char"] <= char_position < chunk["end_char"]:
            # Check for cached audio
            cached_audio = _get_cached_audio_for_chunk(
                session, chunk["index"],
                session.tts_voice, session.tts_speed
            )

            return {
                "index": chunk["index"],
                "start_char": chunk["start_char"],
                "end_char": chunk["end_char"],
                "text": chunk["text"],
                "has_audio": cached_audio is not None,
                "audio": cached_audio,
            }

    return None


def _get_cached_audio_for_chunk(
    session: ReadingSession,
    chunk_index: int,
    voice: str,
    speed: float,
) -> Optional[Dict[str, Any]]:
    """Get cached audio for a specific chunk."""
    conn = get_db()

    # Determine the content column
    if session.content_type == "file":
        id_column = "file_id"
    elif session.content_type == "library":
        id_column = "library_file_id"
    else:
        id_column = "transcript_id"

    cur = conn.execute(
        f"""
        SELECT audio_path, duration_seconds
        FROM reader_audio_cache
        WHERE {id_column} = ? AND chunk_index = ?
          AND tts_voice = ? AND tts_speed = ?
        """,
        (session.content_id, chunk_index, voice or "", speed or 1.0),
    )
    row = cur.fetchone()

    if row:
        return {
            "path": row["audio_path"],
            "duration": row["duration_seconds"],
        }
    return None


# =============================================================================
# Statistics
# =============================================================================

def get_reading_stats(user_id: int) -> Dict[str, Any]:
    """
    Get reading statistics for a user.

    Returns:
        Dict with total sessions, completed, reading time, by content type
    """
    conn = get_db()

    # Overall stats
    cur = conn.execute(
        """
        SELECT
            COUNT(*) as total_sessions,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
            COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress,
            COUNT(CASE WHEN status = 'abandoned' THEN 1 END) as abandoned,
            COALESCE(SUM(total_reading_time_seconds), 0) as total_reading_seconds
        FROM reading_sessions
        WHERE user_id = ?
        """,
        (user_id,),
    )
    stats = dict(cur.fetchone())

    # By content type
    cur = conn.execute(
        """
        SELECT
            content_type,
            COUNT(*) as count,
            COALESCE(SUM(total_reading_time_seconds), 0) as reading_seconds
        FROM reading_sessions
        WHERE user_id = ?
        GROUP BY content_type
        """,
        (user_id,),
    )
    by_type = {
        row["content_type"]: {
            "count": row["count"],
            "reading_seconds": row["reading_seconds"],
        }
        for row in cur.fetchall()
    }

    # Format reading time
    total_seconds = stats["total_reading_seconds"]
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    stats["total_reading_time_formatted"] = f"{hours}h {minutes}m"
    stats["by_content_type"] = by_type

    return stats


def update_session_voice(
    session_id: int,
    user_id: int,
    voice: str,
    speed: float = None,
) -> Optional[ReadingSession]:
    """
    Update TTS settings for a session.

    Args:
        session_id: Session ID
        user_id: User ID
        voice: Voice model name
        speed: Playback speed multiplier

    Returns:
        Updated session or None
    """
    session = get_session(session_id, user_id)
    if not session:
        return None

    conn = get_db()
    updates = ["tts_voice = ?", "last_accessed = CURRENT_TIMESTAMP"]
    params = [voice]

    if speed is not None:
        updates.append("tts_speed = ?")
        params.append(speed)

    params.extend([session_id, user_id])

    conn.execute(
        f"""
        UPDATE reading_sessions
        SET {', '.join(updates)}
        WHERE id = ? AND user_id = ?
        """,
        params,
    )
    conn.commit()

    return get_session(session_id, user_id)
