"""
Audio Transcript Importer Plugin

Phase 6.3: Plugin Framework (MVP)

Imports audio/video files from a directory and transcribes them
using the existing transcript_service (faster-whisper).
"""

import logging
import mimetypes
import os
from typing import Any, Dict, List

from plugins import ImporterPlugin, ImportItem, ImportResult
from services.transcript_service import (
    transcribe_file,
    get_transcript_service_status,
)

logger = logging.getLogger(__name__)

# Audio/video extensions we can transcribe
AUDIO_VIDEO_EXTENSIONS = {
    ".mp3",
    ".mp4",
    ".m4a",
    ".wav",
    ".webm",
    ".ogg",
    ".flac",
    ".aac",
    ".wma",
    ".avi",
    ".mkv",
    ".mov",
    ".wmv",
}


class AudioTranscriptImporter(ImporterPlugin):
    """
    Import and transcribe audio/video files.

    Scans a directory for audio/video files and transcribes them
    using faster-whisper. The transcripts are stored in the
    transcripts table and linked to the project.
    """

    id = "audio-transcript"
    name = "Audio Transcript Importer"
    description = "Import audio/video files and transcribe them"

    config_schema = {
        "path": {
            "type": "string",
            "required": True,
            "description": "Directory path containing audio/video files",
        },
        "recursive": {
            "type": "boolean",
            "default": False,
            "description": "Scan subdirectories recursively",
        },
        "language": {
            "type": "string",
            "default": "",
            "description": "Language code (e.g., 'en', 'es') - auto-detected if empty",
        },
        "model": {
            "type": "string",
            "default": "base",
            "description": "Whisper model (tiny, base, small, medium, large-v2)",
        },
    }

    def validate_config(self, config: Dict) -> bool:
        """Validate configuration."""
        path = config.get("path")
        if not path:
            return False
        if not os.path.isdir(path):
            return False

        # Check if transcription service is available
        status = get_transcript_service_status()
        if not status.get("whisper_available"):
            logger.warning("faster-whisper not available for transcription")
            # Still allow validation to pass - error will be shown at import time
            return True

        return True

    def list_items(self, config: Dict) -> List[ImportItem]:
        """
        Discover all audio/video files in the specified directory.

        Args:
            config: Plugin configuration with path, recursive

        Returns:
            List of ImportItem objects representing files to transcribe
        """
        path = config.get("path", "")
        recursive = config.get("recursive", False)

        if not os.path.isdir(path):
            logger.warning(f"Path is not a directory: {path}")
            return []

        items = []
        file_id_counter = 0

        if recursive:
            for root, dirs, files in os.walk(path):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    item = self._create_import_item(file_path, filename, file_id_counter)
                    if item:
                        items.append(item)
                        file_id_counter += 1
        else:
            for filename in os.listdir(path):
                file_path = os.path.join(path, filename)
                if os.path.isfile(file_path):
                    item = self._create_import_item(file_path, filename, file_id_counter)
                    if item:
                        items.append(item)
                        file_id_counter += 1

        logger.info(f"Found {len(items)} audio/video files to transcribe from {path}")
        return items

    def _create_import_item(
        self, file_path: str, filename: str, counter: int
    ) -> ImportItem:
        """Create an ImportItem if the file is an audio/video file."""
        ext = os.path.splitext(filename)[1].lower()

        if ext not in AUDIO_VIDEO_EXTENSIONS:
            return None

        try:
            size = os.path.getsize(file_path)
        except OSError:
            size = None

        mime_type, _ = mimetypes.guess_type(filename)

        return ImportItem(
            id=f"audio-{counter}",
            name=filename,
            path=file_path,
            mime_type=mime_type,
            size_bytes=size,
            metadata={"original_path": file_path, "extension": ext},
        )

    def import_item(
        self, item: ImportItem, project_id: int, user_id: int
    ) -> ImportResult:
        """
        Transcribe an audio/video file and save the transcript.

        Args:
            item: The ImportItem to transcribe
            project_id: Target project ID
            user_id: User performing the import

        Returns:
            ImportResult with success status and transcript info
        """
        # Check service availability
        status = get_transcript_service_status()
        if not status.get("whisper_available"):
            return ImportResult(
                success=False,
                error="faster-whisper is not installed. Install with: pip install faster-whisper",
                metadata={"source_path": item.path},
            )

        try:
            # Use the existing transcript service
            result = transcribe_file(
                file_path=item.path,
                project_id=project_id,
                filename=item.name,
                save_transcript=True,
            )

            if result.get("error"):
                return ImportResult(
                    success=False,
                    error=result["error"],
                    metadata={"source_path": item.path},
                )

            transcript_id = result.get("transcript_id")
            logger.info(
                f"Transcribed {item.name}, transcript_id={transcript_id}"
            )

            return ImportResult(
                success=True,
                file_id=None,  # Transcripts don't create files, they go to transcripts table
                metadata={
                    "source_path": item.path,
                    "transcript_id": transcript_id,
                    "duration_seconds": result.get("duration_seconds"),
                    "language": result.get("language"),
                    "model_used": result.get("model_used"),
                    "text_preview": (result.get("text") or "")[:200],
                },
            )

        except Exception as e:
            logger.error(f"Failed to transcribe {item.name}: {e}")
            return ImportResult(
                success=False,
                error=str(e),
                metadata={"source_path": item.path},
            )
