"""
Reader API Routes

Phase 5.5: Integrated Reader.

Provides REST endpoints for:
- Content retrieval for reading
- Reading session management
- Bookmark management
- TTS audio generation and playback
- Reading statistics
"""

import os
from pathlib import Path

from flask import Blueprint, g, jsonify, request, send_file, abort

from services.reader_service import (
    get_content_for_reader,
    get_or_create_session,
    get_session,
    update_session_progress,
    complete_session,
    abandon_session,
    get_recent_sessions,
    add_bookmark,
    remove_bookmark,
    generate_audio_for_session,
    get_chunk_for_position,
    get_reading_stats,
    update_session_voice,
)
from services.tts_service import (
    get_piper_status,
    get_available_voices,
    get_cache_stats,
    clear_cache,
    CACHE_DIR,
)

reader_bp = Blueprint("reader", __name__, url_prefix="/api/reader")


def get_user_id():
    """Get current user ID from request context."""
    # Check for user in g (set by auth middleware)
    if hasattr(g, "user_id") and g.user_id:
        return g.user_id
    # Fallback to header or default
    return request.headers.get("X-User-Id", 1, type=int)


# =============================================================================
# Content
# =============================================================================

@reader_bp.get("/content/<content_type>/<int:content_id>")
def get_content(content_type: str, content_id: int):
    """
    Get content prepared for reading.

    Returns content with title, text, total_chars, and metadata.
    """
    if content_type not in ("file", "library", "transcript"):
        return jsonify({"error": "Invalid content_type"}), 400

    user_id = get_user_id()
    content = get_content_for_reader(content_type, content_id, user_id)

    if not content:
        return jsonify({"error": "Content not found or not accessible"}), 404

    return jsonify(content.to_dict())


# =============================================================================
# Sessions
# =============================================================================

@reader_bp.post("/session")
def create_session():
    """
    Create or get existing reading session.

    Body:
        content_type: 'file', 'library', or 'transcript'
        content_id: int
        mode: 'visual', 'audio', or 'both' (default: 'visual')

    Returns existing incomplete session if one exists.
    """
    data = request.get_json() or {}

    content_type = data.get("content_type")
    content_id = data.get("content_id")
    mode = data.get("mode", "visual")

    if not content_type or content_id is None:
        return jsonify({"error": "content_type and content_id required"}), 400

    if content_type not in ("file", "library", "transcript"):
        return jsonify({"error": "Invalid content_type"}), 400

    if mode not in ("visual", "audio", "both"):
        return jsonify({"error": "Invalid mode"}), 400

    user_id = get_user_id()
    session = get_or_create_session(user_id, content_type, content_id, mode)

    if not session:
        return jsonify({"error": "Content not accessible"}), 404

    return jsonify(session.to_dict()), 201


@reader_bp.get("/session/<int:session_id>")
def get_session_route(session_id: int):
    """Get a reading session by ID."""
    user_id = get_user_id()
    session = get_session(session_id, user_id)

    if not session:
        return jsonify({"error": "Session not found"}), 404

    # Include content info
    content = get_content_for_reader(
        session.content_type, session.content_id, user_id
    )

    result = session.to_dict()
    if content:
        result["content_title"] = content.title
        result["content_preview"] = content.text[:500] if content.text else None

    return jsonify(result)


@reader_bp.patch("/session/<int:session_id>/progress")
def update_progress(session_id: int):
    """
    Update session reading progress.

    Body:
        position_char: int (character position)
        position_seconds: float (audio position)
        reading_time_delta: int (seconds to add to total)
    """
    data = request.get_json() or {}
    user_id = get_user_id()

    session = update_session_progress(
        session_id,
        user_id,
        position_char=data.get("position_char"),
        position_seconds=data.get("position_seconds"),
        reading_time_delta=data.get("reading_time_delta"),
    )

    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify({
        "id": session.id,
        "position_char": session.position_char,
        "position_seconds": session.position_seconds,
        "total_reading_time_seconds": session.total_reading_time_seconds,
        "progress_percent": session.progress_percent,
    })


@reader_bp.post("/session/<int:session_id>/complete")
def complete_session_route(session_id: int):
    """Mark a reading session as completed."""
    user_id = get_user_id()
    session = complete_session(session_id, user_id)

    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify(session.to_dict())


@reader_bp.post("/session/<int:session_id>/abandon")
def abandon_session_route(session_id: int):
    """Mark a reading session as abandoned."""
    user_id = get_user_id()
    session = abandon_session(session_id, user_id)

    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify(session.to_dict())


@reader_bp.get("/sessions")
def list_sessions():
    """
    List recent reading sessions.

    Query params:
        limit: int (default 10)
        include_completed: bool (default false)
    """
    user_id = get_user_id()
    limit = request.args.get("limit", 10, type=int)
    include_completed = request.args.get("include_completed", "false").lower() == "true"

    sessions = get_recent_sessions(user_id, limit, include_completed)

    return jsonify({
        "sessions": [s.to_dict() for s in sessions],
        "count": len(sessions),
    })


# =============================================================================
# Bookmarks
# =============================================================================

@reader_bp.post("/session/<int:session_id>/bookmark")
def add_bookmark_route(session_id: int):
    """
    Add a bookmark to a session.

    Body:
        position_char: int (required)
        label: str (optional)
    """
    data = request.get_json() or {}
    user_id = get_user_id()

    position_char = data.get("position_char")
    if position_char is None:
        return jsonify({"error": "position_char required"}), 400

    label = data.get("label")

    session = add_bookmark(session_id, user_id, position_char, label)

    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify({
        "bookmarks": session.bookmarks,
        "count": len(session.bookmarks),
    }), 201


@reader_bp.delete("/session/<int:session_id>/bookmark/<int:index>")
def remove_bookmark_route(session_id: int, index: int):
    """Remove a bookmark from a session by index."""
    user_id = get_user_id()
    session = remove_bookmark(session_id, user_id, index)

    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify({
        "bookmarks": session.bookmarks,
        "count": len(session.bookmarks),
    })


# =============================================================================
# Audio
# =============================================================================

@reader_bp.post("/session/<int:session_id>/audio")
def generate_audio(session_id: int):
    """
    Generate TTS audio for session.

    Body:
        start_chunk: int (default 0)
        num_chunks: int (default 3)

    Returns list of generated chunks with audio paths.
    """
    data = request.get_json() or {}
    user_id = get_user_id()

    start_chunk = data.get("start_chunk", 0)
    num_chunks = data.get("num_chunks", 3)

    result = generate_audio_for_session(
        session_id, user_id, start_chunk, num_chunks
    )

    if result.get("error"):
        return jsonify(result), 400

    return jsonify(result)


@reader_bp.get("/session/<int:session_id>/chunk")
def get_chunk(session_id: int):
    """
    Get chunk info for a character position.

    Query params:
        position: int (character position)

    Returns chunk info including cached audio if available.
    """
    user_id = get_user_id()
    position = request.args.get("position", 0, type=int)

    chunk = get_chunk_for_position(session_id, user_id, position)

    if not chunk:
        return jsonify({"error": "Chunk not found"}), 404

    return jsonify(chunk)


@reader_bp.get("/audio/<path:audio_path>")
def serve_audio(audio_path: str):
    """
    Serve audio file from cache.

    Security: Only serves files from the TTS cache directory.
    """
    # Ensure cache directory exists
    if not CACHE_DIR.exists():
        abort(404)

    # Resolve the full path
    # audio_path should be just the filename (e.g., "abc123.wav")
    full_path = CACHE_DIR / Path(audio_path).name

    # Security check: ensure the resolved path is within CACHE_DIR
    try:
        full_path = full_path.resolve()
        CACHE_DIR.resolve()
        if not str(full_path).startswith(str(CACHE_DIR.resolve())):
            abort(403)
    except Exception:
        abort(403)

    if not full_path.exists():
        abort(404)

    if not full_path.suffix == ".wav":
        abort(403)

    return send_file(
        full_path,
        mimetype="audio/wav",
        as_attachment=False,
    )


@reader_bp.patch("/session/<int:session_id>/settings")
def update_session_settings(session_id: int):
    """
    Update TTS settings for a session.

    Body:
        tts_voice: str (voice model name)
        tts_speed: float (playback speed)
    """
    data = request.get_json() or {}
    user_id = get_user_id()

    voice = data.get("tts_voice")
    speed = data.get("tts_speed")

    if not voice and speed is None:
        return jsonify({"error": "tts_voice or tts_speed required"}), 400

    session = update_session_voice(session_id, user_id, voice, speed)

    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify({
        "tts_voice": session.tts_voice,
        "tts_speed": session.tts_speed,
    })


# =============================================================================
# TTS
# =============================================================================

@reader_bp.get("/tts/status")
def tts_status():
    """Get Piper TTS status including availability and voices."""
    status = get_piper_status()
    return jsonify(status)


@reader_bp.get("/tts/voices")
def tts_voices():
    """List available TTS voice models."""
    voices = get_available_voices()
    return jsonify({
        "voices": voices,
        "count": len(voices),
    })


@reader_bp.get("/tts/cache")
def tts_cache_stats():
    """Get TTS cache statistics."""
    stats = get_cache_stats()
    return jsonify(stats)


@reader_bp.delete("/tts/cache")
def clear_tts_cache():
    """
    Clear TTS cache.

    Query params:
        older_than_days: int (only clear files older than N days)
    """
    older_than_days = request.args.get("older_than_days", type=int)
    result = clear_cache(older_than_days)
    return jsonify(result)


# =============================================================================
# Stats
# =============================================================================

@reader_bp.get("/stats")
def reading_stats():
    """Get reading statistics for current user."""
    user_id = get_user_id()
    stats = get_reading_stats(user_id)
    return jsonify(stats)
