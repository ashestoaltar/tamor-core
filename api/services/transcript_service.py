"""
Transcript Service

Phase 5.3: Media & Transcript Integration.

Provides:
- YouTube/URL audio download via yt-dlp
- Audio/video transcription via faster-whisper
- Transcript storage and retrieval

Supports: YouTube, direct audio/video URLs, uploaded files.
"""

import json
import logging
import os
import tempfile
import uuid
from typing import Any, Dict, List, Optional

from utils.db import get_db

logger = logging.getLogger(__name__)

# Whisper model to use (tiny, base, small, medium, large-v2, large-v3)
# Smaller = faster, larger = more accurate
DEFAULT_WHISPER_MODEL = "base"

# Check for faster-whisper availability
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    WhisperModel = None
    logger.warning("faster-whisper not installed - transcription disabled")

# Check for yt-dlp availability
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False
    yt_dlp = None
    logger.warning("yt-dlp not installed - URL download disabled")


# Singleton whisper model (lazy loaded)
_whisper_model = None
_whisper_model_name = None


def _get_whisper_model(model_name: str = None):
    """Get or create whisper model (singleton for efficiency)."""
    global _whisper_model, _whisper_model_name

    if not WHISPER_AVAILABLE:
        return None

    model_name = model_name or DEFAULT_WHISPER_MODEL

    if _whisper_model is None or _whisper_model_name != model_name:
        logger.info(f"Loading Whisper model: {model_name}")
        # Use CUDA if available, else CPU
        _whisper_model = WhisperModel(model_name, device="auto", compute_type="auto")
        _whisper_model_name = model_name

    return _whisper_model


# ---------------------------------------------------------------------------
# YouTube/URL Download
# ---------------------------------------------------------------------------

def download_audio_from_url(
    url: str,
    output_dir: str,
) -> Dict[str, Any]:
    """
    Download audio from YouTube or other supported URL.

    Args:
        url: YouTube URL or other video URL
        output_dir: Directory to save audio file

    Returns:
        Dict with 'audio_path', 'title', 'duration', or 'error'
    """
    if not YTDLP_AVAILABLE:
        return {"error": "yt-dlp not installed"}

    # Generate unique filename
    file_id = str(uuid.uuid4())[:8]
    output_template = os.path.join(output_dir, f"{file_id}_%(title).50s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Find the downloaded file
            if info is None:
                return {"error": "Failed to extract video info"}

            title = info.get("title", "Unknown")
            duration = info.get("duration", 0)

            # Get the actual output path (with mp3 extension after conversion)
            base_path = ydl.prepare_filename(info)
            # Remove original extension and add mp3
            audio_path = os.path.splitext(base_path)[0] + ".mp3"

            if not os.path.exists(audio_path):
                # Try finding any mp3 in output_dir with our file_id
                for f in os.listdir(output_dir):
                    if f.startswith(file_id) and f.endswith(".mp3"):
                        audio_path = os.path.join(output_dir, f)
                        break

            if not os.path.exists(audio_path):
                return {"error": "Audio file not found after download"}

            return {
                "audio_path": audio_path,
                "title": title,
                "duration": duration,
                "source_url": url,
            }

    except Exception as e:
        logger.error(f"Failed to download audio from {url}: {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

def transcribe_audio(
    audio_path: str,
    model_name: str = None,
    language: str = None,
) -> Dict[str, Any]:
    """
    Transcribe audio file using faster-whisper.

    Args:
        audio_path: Path to audio file
        model_name: Whisper model (tiny, base, small, medium, large-v2, large-v3)
        language: Optional language code (auto-detected if not specified)

    Returns:
        Dict with 'text', 'segments', 'language', 'duration', or 'error'
    """
    if not WHISPER_AVAILABLE:
        return {"error": "faster-whisper not installed"}

    if not os.path.exists(audio_path):
        return {"error": f"Audio file not found: {audio_path}"}

    model = _get_whisper_model(model_name)
    if model is None:
        return {"error": "Failed to load Whisper model"}

    try:
        # Transcribe
        segments_iter, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=True,  # Filter out silence
        )

        # Collect segments
        segments = []
        full_text_parts = []

        for segment in segments_iter:
            segments.append({
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip(),
            })
            full_text_parts.append(segment.text.strip())

        full_text = " ".join(full_text_parts)

        return {
            "text": full_text,
            "segments": segments,
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration": round(info.duration, 2),
            "model_used": model_name or DEFAULT_WHISPER_MODEL,
        }

    except Exception as e:
        logger.error(f"Transcription failed for {audio_path}: {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Combined Operations
# ---------------------------------------------------------------------------

def transcribe_url(
    url: str,
    project_id: int,
    model_name: str = None,
    language: str = None,
    save_transcript: bool = True,
) -> Dict[str, Any]:
    """
    Download and transcribe audio from URL.

    Args:
        url: YouTube or media URL
        project_id: Project to associate transcript with
        model_name: Whisper model to use
        language: Optional language hint
        save_transcript: Whether to save to database

    Returns:
        Dict with transcript data or error
    """
    # Create temp directory for download
    with tempfile.TemporaryDirectory() as temp_dir:
        # Download audio
        download_result = download_audio_from_url(url, temp_dir)
        if download_result.get("error"):
            return download_result

        audio_path = download_result["audio_path"]
        title = download_result.get("title", "Unknown")
        source_duration = download_result.get("duration")

        # Transcribe
        transcript_result = transcribe_audio(audio_path, model_name, language)
        if transcript_result.get("error"):
            return transcript_result

        # Combine results
        result = {
            "title": title,
            "source_url": url,
            "source_type": "url",
            "duration_seconds": transcript_result.get("duration") or source_duration,
            "text": transcript_result["text"],
            "segments": transcript_result["segments"],
            "language": transcript_result["language"],
            "model_used": transcript_result["model_used"],
        }

        # Save to database if requested
        if save_transcript:
            transcript_id = save_transcript_to_db(project_id, result)
            result["transcript_id"] = transcript_id

        return result


def transcribe_file(
    file_path: str,
    project_id: int,
    file_id: int = None,
    filename: str = None,
    model_name: str = None,
    language: str = None,
    save_transcript: bool = True,
) -> Dict[str, Any]:
    """
    Transcribe an audio/video file.

    Args:
        file_path: Path to audio/video file
        project_id: Project to associate transcript with
        file_id: Optional source file ID
        filename: Original filename
        model_name: Whisper model to use
        language: Optional language hint
        save_transcript: Whether to save to database

    Returns:
        Dict with transcript data or error
    """
    # Transcribe directly (ffmpeg handles format conversion internally)
    transcript_result = transcribe_audio(file_path, model_name, language)
    if transcript_result.get("error"):
        return transcript_result

    result = {
        "title": filename or os.path.basename(file_path),
        "source_type": "file",
        "source_file_id": file_id,
        "duration_seconds": transcript_result.get("duration"),
        "text": transcript_result["text"],
        "segments": transcript_result["segments"],
        "language": transcript_result["language"],
        "model_used": transcript_result["model_used"],
    }

    if save_transcript:
        transcript_id = save_transcript_to_db(project_id, result)
        result["transcript_id"] = transcript_id

    return result


# ---------------------------------------------------------------------------
# Database Operations
# ---------------------------------------------------------------------------

def save_transcript_to_db(project_id: int, result: Dict[str, Any]) -> int:
    """Save transcript to database. Returns transcript ID."""
    conn = get_db()
    cur = conn.execute(
        """
        INSERT INTO transcripts (
            project_id, source_type, source_url, source_file_id,
            title, duration_seconds, transcript_text, segments_json,
            language, model_used
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            result.get("source_type"),
            result.get("source_url"),
            result.get("source_file_id"),
            result.get("title"),
            result.get("duration_seconds"),
            result.get("text"),
            json.dumps(result.get("segments", [])),
            result.get("language"),
            result.get("model_used"),
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_transcript(transcript_id: int, project_id: int = None) -> Optional[Dict[str, Any]]:
    """Get transcript by ID."""
    conn = get_db()
    query = "SELECT * FROM transcripts WHERE id = ?"
    params = [transcript_id]

    if project_id:
        query += " AND project_id = ?"
        params.append(project_id)

    cur = conn.execute(query, params)
    row = cur.fetchone()

    if not row:
        return None

    segments = []
    if row["segments_json"]:
        try:
            segments = json.loads(row["segments_json"])
        except json.JSONDecodeError:
            pass

    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "source_type": row["source_type"],
        "source_url": row["source_url"],
        "source_file_id": row["source_file_id"],
        "title": row["title"],
        "duration_seconds": row["duration_seconds"],
        "text": row["transcript_text"],
        "segments": segments,
        "language": row["language"],
        "model_used": row["model_used"],
        "created_at": row["created_at"],
    }


def get_project_transcripts(project_id: int) -> List[Dict[str, Any]]:
    """Get all transcripts for a project."""
    conn = get_db()
    cur = conn.execute(
        """
        SELECT id, source_type, source_url, title, duration_seconds,
               language, model_used, created_at
        FROM transcripts
        WHERE project_id = ?
        ORDER BY created_at DESC
        """,
        (project_id,),
    )

    transcripts = []
    for row in cur.fetchall():
        transcripts.append({
            "id": row["id"],
            "source_type": row["source_type"],
            "source_url": row["source_url"],
            "title": row["title"],
            "duration_seconds": row["duration_seconds"],
            "language": row["language"],
            "model_used": row["model_used"],
            "created_at": row["created_at"],
        })

    return transcripts


def delete_transcript(transcript_id: int, project_id: int) -> bool:
    """Delete a transcript. Returns True if deleted."""
    conn = get_db()
    cur = conn.execute(
        "DELETE FROM transcripts WHERE id = ? AND project_id = ?",
        (transcript_id, project_id),
    )
    conn.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Status Check
# ---------------------------------------------------------------------------

def get_transcript_service_status() -> Dict[str, Any]:
    """Check status of transcript service dependencies."""
    return {
        "whisper_available": WHISPER_AVAILABLE,
        "ytdlp_available": YTDLP_AVAILABLE,
        "default_model": DEFAULT_WHISPER_MODEL,
        "ready": WHISPER_AVAILABLE,  # Core functionality
    }
