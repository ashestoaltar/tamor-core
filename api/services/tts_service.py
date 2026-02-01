"""
TTS Service

Phase 5.5: Integrated Reader.

Provides text-to-speech synthesis using Piper TTS:
- Local, offline TTS with natural voices
- Audio caching to avoid re-synthesis
- Chunked synthesis for long texts
- Sentence-aware text splitting

Piper TTS: https://github.com/rhasspy/piper
"""

import hashlib
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Configuration
# Use /mnt/library for NAS-based voice models (already downloaded during testing)
VOICES_DIR = Path(os.environ.get("TTS_VOICES_DIR", "/mnt/library/piper_voices"))
# Use local data directory for cache
CACHE_DIR = Path(os.environ.get("TTS_CACHE_DIR", "/home/tamor/tamor-core/api/data/tts/cache"))

DEFAULT_VOICE = "en_US-lessac-medium"
DEFAULT_CHUNK_SIZE = 1000  # characters
DEFAULT_SPEED = 1.0

# Piper sample rate (fixed at 22050 Hz for most models)
SAMPLE_RATE = 22050


def ensure_directories() -> None:
    """Create TTS directories if they don't exist."""
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_available_voices() -> List[Dict[str, Any]]:
    """
    List available voice models.

    Returns:
        List of dicts with voice info: name, path, has_config
    """
    ensure_directories()
    voices = []

    for onnx_file in VOICES_DIR.glob("*.onnx"):
        name = onnx_file.stem  # e.g., "en_US-lessac-medium"
        config_file = onnx_file.with_suffix(".onnx.json")

        voices.append({
            "name": name,
            "path": str(onnx_file),
            "has_config": config_file.exists(),
            "size_mb": round(onnx_file.stat().st_size / 1024 / 1024, 1),
        })

    return sorted(voices, key=lambda v: v["name"])


def get_voice_path(voice_name: str = None) -> Optional[Path]:
    """
    Get path to voice model file.

    Args:
        voice_name: Voice name (e.g., "en_US-lessac-medium")

    Returns:
        Path to .onnx file, or None if not found
    """
    voice_name = voice_name or DEFAULT_VOICE
    model_path = VOICES_DIR / f"{voice_name}.onnx"

    if model_path.exists():
        return model_path
    return None


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    respect_sentences: bool = True,
) -> List[Dict[str, Any]]:
    """
    Split text into chunks for synthesis.

    Args:
        text: Full text to split
        chunk_size: Target characters per chunk
        respect_sentences: Try to break at sentence boundaries

    Returns:
        List of dicts with: text, start_char, end_char, index
    """
    if not text or not text.strip():
        return []

    text = text.strip()
    chunks = []

    if respect_sentences:
        # Split into sentences first
        # Match sentence-ending punctuation followed by space or end
        sentence_pattern = r'(?<=[.!?])\s+'
        sentences = re.split(sentence_pattern, text)

        current_chunk = ""
        chunk_start = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Would adding this sentence exceed chunk size?
            test_chunk = f"{current_chunk} {sentence}".strip() if current_chunk else sentence

            if len(test_chunk) > chunk_size and current_chunk:
                # Save current chunk, start new one
                chunks.append({
                    "text": current_chunk,
                    "start_char": chunk_start,
                    "end_char": chunk_start + len(current_chunk),
                    "index": len(chunks),
                })
                current_chunk = sentence
                chunk_start = chunk_start + len(chunks[-1]["text"]) + 1
            else:
                current_chunk = test_chunk

        # Don't forget the last chunk
        if current_chunk:
            chunks.append({
                "text": current_chunk,
                "start_char": chunk_start,
                "end_char": chunk_start + len(current_chunk),
                "index": len(chunks),
            })
    else:
        # Simple character-based chunking
        for i in range(0, len(text), chunk_size):
            chunk_text = text[i:i + chunk_size]
            chunks.append({
                "text": chunk_text,
                "start_char": i,
                "end_char": i + len(chunk_text),
                "index": len(chunks),
            })

    # Recalculate positions based on original text
    pos = 0
    for chunk in chunks:
        # Find this chunk's text in the original
        idx = text.find(chunk["text"], pos)
        if idx >= 0:
            chunk["start_char"] = idx
            chunk["end_char"] = idx + len(chunk["text"])
            pos = chunk["end_char"]

    return chunks


def get_cache_key(text: str, voice: str, speed: float) -> str:
    """
    Generate cache key for audio.

    Uses hash of text content + voice + speed to create filesystem-safe key.
    """
    content = f"{text}|{voice}|{speed}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def get_cached_audio(
    text: str,
    voice: str = None,
    speed: float = None,
) -> Optional[Dict[str, Any]]:
    """
    Check if audio is cached.

    Returns:
        Dict with path, duration if cached, None otherwise
    """
    voice = voice or DEFAULT_VOICE
    speed = speed or DEFAULT_SPEED

    cache_key = get_cache_key(text, voice, speed)
    cache_path = CACHE_DIR / f"{cache_key}.wav"

    if cache_path.exists():
        duration = get_audio_duration(cache_path)
        return {
            "path": str(cache_path),
            "duration": duration,
            "cached": True,
        }
    return None


def get_audio_duration(audio_path: Path) -> float:
    """
    Get duration of WAV file in seconds.

    Assumes 16-bit mono WAV at SAMPLE_RATE Hz.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        return 0.0

    file_size = audio_path.stat().st_size
    # WAV header is 44 bytes, then 2 bytes per sample
    data_size = file_size - 44
    duration = data_size / (SAMPLE_RATE * 2)
    return round(max(0, duration), 2)


def synthesize_chunk(
    text: str,
    voice: str = None,
    speed: float = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """
    Synthesize audio for a text chunk.

    Args:
        text: Text to synthesize
        voice: Voice model name
        speed: Playback speed multiplier (not yet supported by Piper)
        use_cache: Whether to use/store cached audio

    Returns:
        Dict with path, duration, cached, or error
    """
    voice = voice or DEFAULT_VOICE
    speed = speed or DEFAULT_SPEED

    if not text or not text.strip():
        return {"error": "Empty text"}

    text = text.strip()

    # Check cache first
    if use_cache:
        cached = get_cached_audio(text, voice, speed)
        if cached:
            return cached

    # Get voice model path
    model_path = get_voice_path(voice)
    if not model_path:
        return {"error": f"Voice model not found: {voice}"}

    # Ensure cache directory exists
    ensure_directories()

    # Generate to temp file first, then move to cache
    cache_key = get_cache_key(text, voice, speed)
    cache_path = CACHE_DIR / f"{cache_key}.wav"

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        # Run Piper
        # Note: Piper reads from stdin, writes to output file
        cmd = [
            "piper",
            "--model", str(model_path),
            "--output_file", tmp_path,
        ]

        result = subprocess.run(
            cmd,
            input=text,
            capture_output=True,
            text=True,
            timeout=60,  # 60 second timeout per chunk
        )

        if result.returncode != 0:
            logger.error(f"Piper failed: {result.stderr}")
            return {"error": f"Piper synthesis failed: {result.stderr}"}

        if not os.path.exists(tmp_path):
            return {"error": "Piper did not create output file"}

        # Move to cache location
        shutil.move(tmp_path, cache_path)

        duration = get_audio_duration(cache_path)

        return {
            "path": str(cache_path),
            "duration": duration,
            "cached": False,
        }

    except subprocess.TimeoutExpired:
        logger.error(f"Piper timed out synthesizing text ({len(text)} chars)")
        return {"error": "Synthesis timed out"}
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        return {"error": str(e)}
    finally:
        # Clean up temp file if it exists
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass


def synthesize_text(
    text: str,
    voice: str = None,
    speed: float = None,
    chunk_size: int = None,
) -> Dict[str, Any]:
    """
    Synthesize audio for full text, chunking as needed.

    Args:
        text: Full text to synthesize
        voice: Voice model name
        speed: Playback speed
        chunk_size: Characters per chunk

    Returns:
        Dict with chunks (list of synthesis results), total_duration, or error
    """
    voice = voice or DEFAULT_VOICE
    speed = speed or DEFAULT_SPEED
    chunk_size = chunk_size or DEFAULT_CHUNK_SIZE

    if not text or not text.strip():
        return {"error": "Empty text"}

    # Split into chunks
    chunks = chunk_text(text, chunk_size, respect_sentences=True)

    if not chunks:
        return {"error": "No chunks generated"}

    results = []
    total_duration = 0.0
    errors = []

    for chunk in chunks:
        result = synthesize_chunk(chunk["text"], voice, speed)

        if result.get("error"):
            errors.append(f"Chunk {chunk['index']}: {result['error']}")
            results.append({
                "index": chunk["index"],
                "start_char": chunk["start_char"],
                "end_char": chunk["end_char"],
                "error": result["error"],
            })
        else:
            total_duration += result.get("duration", 0)
            results.append({
                "index": chunk["index"],
                "start_char": chunk["start_char"],
                "end_char": chunk["end_char"],
                "path": result["path"],
                "duration": result.get("duration", 0),
                "cached": result.get("cached", False),
            })

    return {
        "chunks": results,
        "total_duration": round(total_duration, 2),
        "chunk_count": len(chunks),
        "errors": errors if errors else None,
        "voice": voice,
        "speed": speed,
    }


def clear_cache(older_than_days: int = None) -> Dict[str, Any]:
    """
    Clear cached audio files.

    Args:
        older_than_days: Only clear files older than N days (None = clear all)

    Returns:
        Dict with files_deleted, bytes_freed
    """
    if not CACHE_DIR.exists():
        return {"files_deleted": 0, "bytes_freed": 0}

    files_deleted = 0
    bytes_freed = 0
    cutoff = None

    if older_than_days is not None:
        cutoff = datetime.now() - timedelta(days=older_than_days)

    for wav_file in CACHE_DIR.glob("*.wav"):
        should_delete = True

        if cutoff:
            mtime = datetime.fromtimestamp(wav_file.stat().st_mtime)
            should_delete = mtime < cutoff

        if should_delete:
            try:
                size = wav_file.stat().st_size
                wav_file.unlink()
                files_deleted += 1
                bytes_freed += size
            except Exception as e:
                logger.warning(f"Failed to delete {wav_file}: {e}")

    return {
        "files_deleted": files_deleted,
        "bytes_freed": bytes_freed,
        "bytes_freed_mb": round(bytes_freed / 1024 / 1024, 2),
    }


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns:
        Dict with file_count, total_bytes, oldest_file, newest_file
    """
    if not CACHE_DIR.exists():
        return {
            "file_count": 0,
            "total_bytes": 0,
            "total_mb": 0,
        }

    wav_files = list(CACHE_DIR.glob("*.wav"))

    if not wav_files:
        return {
            "file_count": 0,
            "total_bytes": 0,
            "total_mb": 0,
        }

    total_bytes = sum(f.stat().st_size for f in wav_files)
    mtimes = [f.stat().st_mtime for f in wav_files]

    return {
        "file_count": len(wav_files),
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / 1024 / 1024, 2),
        "oldest_file": datetime.fromtimestamp(min(mtimes)).isoformat(),
        "newest_file": datetime.fromtimestamp(max(mtimes)).isoformat(),
    }


def check_piper_installed() -> bool:
    """Check if Piper TTS is installed and available."""
    try:
        result = subprocess.run(
            ["piper", "--help"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def get_piper_status() -> Dict[str, Any]:
    """
    Get full status of Piper TTS service.

    Returns:
        Dict with piper_installed, voices, cache_stats, ready
    """
    piper_installed = check_piper_installed()
    voices = get_available_voices() if piper_installed else []
    cache_stats = get_cache_stats()

    # Check if default voice is available
    default_voice_available = any(v["name"] == DEFAULT_VOICE for v in voices)

    return {
        "piper_installed": piper_installed,
        "default_voice": DEFAULT_VOICE,
        "default_voice_available": default_voice_available,
        "voices_dir": str(VOICES_DIR),
        "cache_dir": str(CACHE_DIR),
        "voices_count": len(voices),
        "voices": voices,
        "cache": cache_stats,
        "ready": piper_installed and default_voice_available,
    }
