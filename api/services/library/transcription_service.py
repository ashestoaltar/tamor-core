"""
Transcription queue service for library audio/video files.

Manages background transcription using faster-whisper.
Transcripts are stored as library files linked to source media.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from utils.db import get_db
from .library_service import LibraryService
from .storage_service import LibraryStorageService


# Available whisper models (speed vs accuracy tradeoff)
WHISPER_MODELS = {
    'tiny': {'speed': 'fastest', 'accuracy': 'lowest', 'vram': '~1GB'},
    'base': {'speed': 'fast', 'accuracy': 'good', 'vram': '~1GB'},
    'small': {'speed': 'medium', 'accuracy': 'better', 'vram': '~2GB'},
    'medium': {'speed': 'slow', 'accuracy': 'high', 'vram': '~5GB'},
    'large-v2': {'speed': 'slowest', 'accuracy': 'best', 'vram': '~10GB'},
}

# Audio/video mime types we can transcribe
TRANSCRIBABLE_TYPES = [
    'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav',
    'audio/mp4', 'audio/m4a', 'audio/x-m4a', 'audio/ogg',
    'video/mp4', 'video/mpeg', 'video/webm', 'video/x-matroska'
]


class TranscriptionQueueService:
    def __init__(self):
        self.library = LibraryService()
        self.storage = LibraryStorageService()

    def is_transcribable(self, mime_type: str) -> bool:
        """Check if a mime type can be transcribed."""
        if not mime_type:
            return False
        return any(mime_type.startswith(t.split('/')[0]) for t in TRANSCRIBABLE_TYPES)

    def get_default_model(self) -> str:
        """Get the default transcription model from config."""
        conn = get_db()
        cur = conn.execute(
            "SELECT value FROM library_config WHERE key = 'default_transcription_model'"
        )
        row = cur.fetchone()
        return row['value'] if row else 'base'

    # =========================================================================
    # QUEUE MANAGEMENT
    # =========================================================================

    def add_to_queue(
        self,
        library_file_id: int,
        model: str = None,
        language: str = None,
        priority: int = 5
    ) -> Dict[str, Any]:
        """
        Add a library file to the transcription queue.

        Args:
            library_file_id: Library file to transcribe
            model: Whisper model (tiny/base/small/medium/large-v2)
            language: Language code or None for auto-detect
            priority: 1 (highest) to 10 (lowest), default 5

        Returns:
            {'id': queue_id, 'status': 'queued' | 'already_queued' | 'already_transcribed' | 'error'}
        """
        # Verify file exists and is transcribable
        file = self.library.get_file(library_file_id)
        if not file:
            return {'id': None, 'status': 'error', 'error': 'File not found'}

        if not self.is_transcribable(file.get('mime_type', '')):
            return {'id': None, 'status': 'error', 'error': 'File type not transcribable'}

        # Check if already has a transcript
        existing_transcript = self.library.get_transcript_for_source(library_file_id)
        if existing_transcript:
            return {
                'id': None,
                'status': 'already_transcribed',
                'transcript_id': existing_transcript['id']
            }

        # Check if already in queue
        conn = get_db()
        cur = conn.execute(
            "SELECT id, status FROM transcription_queue WHERE library_file_id = ?",
            (library_file_id,)
        )
        existing = cur.fetchone()
        if existing:
            return {
                'id': existing['id'],
                'status': 'already_queued',
                'queue_status': existing['status']
            }

        # Add to queue
        model = model or self.get_default_model()

        cur = conn.execute(
            """
            INSERT INTO transcription_queue
            (library_file_id, model, language, priority, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (library_file_id, model, language, priority)
        )
        conn.commit()

        return {'id': cur.lastrowid, 'status': 'queued'}

    def remove_from_queue(self, queue_id: int) -> bool:
        """Remove an item from the queue (only if pending)."""
        conn = get_db()
        cur = conn.execute(
            "DELETE FROM transcription_queue WHERE id = ? AND status = 'pending'",
            (queue_id,)
        )
        conn.commit()
        return cur.rowcount > 0

    def get_queue_item(self, queue_id: int) -> Optional[Dict[str, Any]]:
        """Get a queue item by ID."""
        conn = get_db()
        cur = conn.execute(
            """
            SELECT tq.*, lf.filename, lf.mime_type
            FROM transcription_queue tq
            JOIN library_files lf ON tq.library_file_id = lf.id
            WHERE tq.id = ?
            """,
            (queue_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def list_queue(
        self,
        status: str = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List queue items.

        Args:
            status: Filter by status (pending/processing/completed/failed)
            limit: Max items to return
        """
        conn = get_db()

        if status:
            cur = conn.execute(
                """
                SELECT tq.*, lf.filename, lf.mime_type
                FROM transcription_queue tq
                JOIN library_files lf ON tq.library_file_id = lf.id
                WHERE tq.status = ?
                ORDER BY tq.priority ASC, tq.queued_at ASC
                LIMIT ?
                """,
                (status, limit)
            )
        else:
            cur = conn.execute(
                """
                SELECT tq.*, lf.filename, lf.mime_type
                FROM transcription_queue tq
                JOIN library_files lf ON tq.library_file_id = lf.id
                ORDER BY
                    CASE tq.status
                        WHEN 'processing' THEN 0
                        WHEN 'pending' THEN 1
                        ELSE 2
                    END,
                    tq.priority ASC,
                    tq.queued_at ASC
                LIMIT ?
                """,
                (limit,)
            )

        return [dict(row) for row in cur.fetchall()]

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        conn = get_db()

        cur = conn.execute("""
            SELECT
                status,
                COUNT(*) as count
            FROM transcription_queue
            GROUP BY status
        """)

        by_status = {row['status']: row['count'] for row in cur.fetchall()}

        # Get total processing time for completed items
        cur = conn.execute("""
            SELECT
                SUM(processing_time_seconds) as total_time,
                AVG(processing_time_seconds) as avg_time
            FROM transcription_queue
            WHERE status = 'completed' AND processing_time_seconds IS NOT NULL
        """)
        timing = cur.fetchone()

        return {
            'pending': by_status.get('pending', 0),
            'processing': by_status.get('processing', 0),
            'completed': by_status.get('completed', 0),
            'failed': by_status.get('failed', 0),
            'total': sum(by_status.values()),
            'total_processing_seconds': timing['total_time'] or 0,
            'avg_processing_seconds': round(timing['avg_time'] or 0, 1)
        }

    def update_priority(self, queue_id: int, priority: int) -> bool:
        """Update priority of a queued item."""
        conn = get_db()
        cur = conn.execute(
            "UPDATE transcription_queue SET priority = ? WHERE id = ? AND status = 'pending'",
            (priority, queue_id)
        )
        conn.commit()
        return cur.rowcount > 0

    # =========================================================================
    # QUEUE CANDIDATES
    # =========================================================================

    def find_transcribable_files(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Find library files that can be transcribed but haven't been.

        Returns files that:
        - Are audio/video
        - Don't have a transcript
        - Aren't already in queue
        """
        conn = get_db()

        # Build mime type conditions
        mime_conditions = " OR ".join([f"lf.mime_type LIKE '{t.split('/')[0]}%'" for t in ['audio/', 'video/']])

        cur = conn.execute(f"""
            SELECT lf.*
            FROM library_files lf
            WHERE ({mime_conditions})
            AND lf.id NOT IN (
                SELECT library_file_id FROM transcription_queue
            )
            AND lf.id NOT IN (
                SELECT source_library_file_id FROM library_files
                WHERE source_library_file_id IS NOT NULL
            )
            ORDER BY lf.created_at DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cur.fetchall()]

    def queue_all_pending(self, model: str = None) -> Dict[str, Any]:
        """
        Add all transcribable files to the queue.

        Returns:
            {'added': int, 'skipped': int}
        """
        files = self.find_transcribable_files(limit=500)

        added = 0
        skipped = 0

        for file in files:
            result = self.add_to_queue(file['id'], model=model)
            if result['status'] == 'queued':
                added += 1
            else:
                skipped += 1

        return {'added': added, 'skipped': skipped}

    # =========================================================================
    # PROCESSING (called by worker)
    # =========================================================================

    def get_next_pending(self) -> Optional[Dict[str, Any]]:
        """Get the next item to process (highest priority, oldest)."""
        conn = get_db()
        cur = conn.execute(
            """
            SELECT tq.*, lf.filename, lf.stored_path, lf.mime_type
            FROM transcription_queue tq
            JOIN library_files lf ON tq.library_file_id = lf.id
            WHERE tq.status = 'pending'
            ORDER BY tq.priority ASC, tq.queued_at ASC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def mark_processing(self, queue_id: int) -> bool:
        """Mark a queue item as processing."""
        conn = get_db()
        cur = conn.execute(
            """
            UPDATE transcription_queue
            SET status = 'processing', started_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'pending'
            """,
            (queue_id,)
        )
        conn.commit()
        return cur.rowcount > 0

    def mark_completed(
        self,
        queue_id: int,
        result_library_file_id: int,
        processing_time: int
    ) -> bool:
        """Mark a queue item as completed."""
        conn = get_db()
        cur = conn.execute(
            """
            UPDATE transcription_queue
            SET status = 'completed',
                completed_at = CURRENT_TIMESTAMP,
                result_library_file_id = ?,
                processing_time_seconds = ?
            WHERE id = ?
            """,
            (result_library_file_id, processing_time, queue_id)
        )
        conn.commit()
        return cur.rowcount > 0

    def mark_failed(self, queue_id: int, error_message: str) -> bool:
        """Mark a queue item as failed."""
        conn = get_db()
        cur = conn.execute(
            """
            UPDATE transcription_queue
            SET status = 'failed',
                completed_at = CURRENT_TIMESTAMP,
                error_message = ?
            WHERE id = ?
            """,
            (error_message, queue_id)
        )
        conn.commit()
        return cur.rowcount > 0

    def retry_failed(self, queue_id: int) -> bool:
        """Reset a failed item to pending for retry."""
        conn = get_db()
        cur = conn.execute(
            """
            UPDATE transcription_queue
            SET status = 'pending',
                started_at = NULL,
                completed_at = NULL,
                error_message = NULL
            WHERE id = ? AND status = 'failed'
            """,
            (queue_id,)
        )
        conn.commit()
        return cur.rowcount > 0
