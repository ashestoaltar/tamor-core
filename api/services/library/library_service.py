# api/services/library/library_service.py

"""
Core library service for CRUD operations on library files.

Handles:
- Adding files to the library with deduplication
- Querying and listing library files
- Metadata updates and tagging
- File deletion with cascade cleanup
- Library statistics
"""

import json
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.db import get_db

from .storage_service import LibraryStorageService


class LibraryService:
    """Service for managing library files."""

    def __init__(self):
        self.storage = LibraryStorageService()

    # =========================================================================
    # CREATE
    # =========================================================================

    def add_file(
        self,
        file_path: str,
        source_type: str = "manual",
        metadata: Dict[str, Any] = None,
        check_duplicate: bool = True,
    ) -> Dict[str, Any]:
        """
        Add a file to the library.

        Args:
            file_path: Absolute path to the file
            source_type: 'manual' | 'scan' | 'transcription'
            metadata: Optional dict with tags, author, title, etc.
            check_duplicate: If True, check hash and skip if exists

        Returns:
            Dict with 'id', 'status' ('created' | 'duplicate'), 'file'
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Compute hash for deduplication
        file_hash = self.storage.compute_file_hash(file_path)

        # Check for duplicate
        if check_duplicate:
            existing = self.storage.find_by_hash(file_hash)
            if existing:
                return {"id": existing["id"], "status": "duplicate", "file": existing}

        # Get file info
        filename = path.name
        size_bytes = path.stat().st_size
        mime_type, _ = mimetypes.guess_type(filename)
        stored_path = self.storage.get_relative_path(file_path)

        # Serialize metadata
        metadata_json = json.dumps(metadata) if metadata else None

        # Insert into database
        conn = get_db()
        cur = conn.execute(
            """
            INSERT INTO library_files
            (filename, stored_path, file_hash, mime_type, size_bytes, source_type, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                filename,
                stored_path,
                file_hash,
                mime_type,
                size_bytes,
                source_type,
                metadata_json,
            ),
        )
        conn.commit()

        file_id = cur.lastrowid

        return {"id": file_id, "status": "created", "file": self.get_file(file_id)}

    def add_transcript(
        self,
        file_path: str,
        source_library_file_id: int,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Add a transcript file linked to its source audio/video.
        """
        result = self.add_file(
            file_path,
            source_type="transcription",
            metadata=metadata,
            check_duplicate=False,  # Transcripts regenerated = different hash
        )

        if result["status"] == "created":
            # Link to source
            conn = get_db()
            conn.execute(
                "UPDATE library_files SET source_library_file_id = ? WHERE id = ?",
                (source_library_file_id, result["id"]),
            )
            conn.commit()

        return result

    # =========================================================================
    # READ
    # =========================================================================

    def get_file(self, file_id: int) -> Optional[Dict[str, Any]]:
        """Get a library file by ID."""
        conn = get_db()
        cur = conn.execute(
            "SELECT * FROM library_files WHERE id = ?",
            (file_id,),
        )
        row = cur.fetchone()
        if not row:
            return None

        return self._row_to_dict(row)

    def get_file_by_path(self, stored_path: str) -> Optional[Dict[str, Any]]:
        """Get a library file by its stored path."""
        conn = get_db()
        cur = conn.execute(
            "SELECT * FROM library_files WHERE stored_path = ?",
            (stored_path,),
        )
        row = cur.fetchone()
        return self._row_to_dict(row) if row else None

    def list_files(
        self,
        limit: int = 100,
        offset: int = 0,
        mime_type: str = None,
        source_type: str = None,
        search: str = None,
    ) -> Dict[str, Any]:
        """
        List library files with optional filtering.

        Returns:
            {
                'files': [...],
                'total': int,
                'limit': int,
                'offset': int
            }
        """
        conn = get_db()

        # Build query
        where_clauses = []
        params = []

        if mime_type:
            where_clauses.append("mime_type LIKE ?")
            params.append(f"{mime_type}%")

        if source_type:
            where_clauses.append("source_type = ?")
            params.append(source_type)

        if search:
            where_clauses.append("(filename LIKE ? OR metadata_json LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Get total count
        cur = conn.execute(
            f"SELECT COUNT(*) as count FROM library_files WHERE {where_sql}",
            params,
        )
        total = cur.fetchone()["count"]

        # Get files
        cur = conn.execute(
            f"""
            SELECT * FROM library_files
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        )

        files = [self._row_to_dict(row) for row in cur.fetchall()]

        return {
            "files": files,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_transcript_for_source(self, source_file_id: int) -> Optional[Dict[str, Any]]:
        """Get transcript file for a source audio/video file."""
        conn = get_db()
        cur = conn.execute(
            """
            SELECT * FROM library_files
            WHERE source_library_file_id = ? AND source_type = 'transcription'
            ORDER BY created_at DESC LIMIT 1
            """,
            (source_file_id,),
        )
        row = cur.fetchone()
        return self._row_to_dict(row) if row else None

    # =========================================================================
    # UPDATE
    # =========================================================================

    def update_metadata(self, file_id: int, metadata: Dict[str, Any]) -> bool:
        """Update metadata for a library file (merges with existing)."""
        existing = self.get_file(file_id)
        if not existing:
            return False

        # Merge metadata
        current_meta = existing.get("metadata") or {}
        current_meta.update(metadata)

        conn = get_db()
        conn.execute(
            """
            UPDATE library_files
            SET metadata_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (json.dumps(current_meta), file_id),
        )
        conn.commit()
        return True

    def set_tags(self, file_id: int, tags: List[str]) -> bool:
        """Set tags for a library file."""
        return self.update_metadata(file_id, {"tags": tags})

    def mark_indexed(self, file_id: int) -> bool:
        """Mark a file as indexed (embeddings generated)."""
        conn = get_db()
        cur = conn.execute(
            """
            UPDATE library_files
            SET last_indexed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (file_id,),
        )
        conn.commit()
        return cur.rowcount > 0

    # =========================================================================
    # DELETE
    # =========================================================================

    def delete_file(self, file_id: int, delete_from_disk: bool = False) -> bool:
        """
        Remove a file from the library.

        Args:
            file_id: Library file ID
            delete_from_disk: If True, also delete the physical file

        Returns:
            True if deleted, False if not found
        """
        file = self.get_file(file_id)
        if not file:
            return False

        conn = get_db()

        # Delete chunks first (foreign key)
        conn.execute(
            "DELETE FROM library_chunks WHERE library_file_id = ?", (file_id,)
        )

        # Delete text cache
        conn.execute(
            "DELETE FROM library_text_cache WHERE library_file_id = ?", (file_id,)
        )

        # Delete project references
        conn.execute(
            "DELETE FROM project_library_refs WHERE library_file_id = ?", (file_id,)
        )

        # Delete the file record
        conn.execute("DELETE FROM library_files WHERE id = ?", (file_id,))

        conn.commit()

        # Optionally delete from disk
        if delete_from_disk:
            full_path = self.storage.resolve_path(file["stored_path"])
            if full_path.exists():
                full_path.unlink()

        return True

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert database row to dict with parsed metadata."""
        if not row:
            return None

        d = dict(row)

        # Parse metadata JSON
        if d.get("metadata_json"):
            try:
                d["metadata"] = json.loads(d["metadata_json"])
            except json.JSONDecodeError:
                d["metadata"] = {}
        else:
            d["metadata"] = {}

        # Remove raw JSON field
        d.pop("metadata_json", None)

        return d

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get library statistics."""
        conn = get_db()

        # Total files and size
        cur = conn.execute(
            """
            SELECT
                COUNT(*) as file_count,
                COALESCE(SUM(size_bytes), 0) as total_bytes
            FROM library_files
        """
        )
        totals = cur.fetchone()

        # By mime type
        cur = conn.execute(
            """
            SELECT
                CASE
                    WHEN mime_type LIKE 'application/pdf' THEN 'pdf'
                    WHEN mime_type LIKE 'application/epub%' THEN 'epub'
                    WHEN mime_type LIKE 'audio/%' THEN 'audio'
                    WHEN mime_type LIKE 'video/%' THEN 'video'
                    WHEN mime_type LIKE 'text/%' THEN 'text'
                    ELSE 'other'
                END as category,
                COUNT(*) as count
            FROM library_files
            GROUP BY category
        """
        )
        by_type = {row["category"]: row["count"] for row in cur.fetchall()}

        # Indexed vs not
        cur = conn.execute(
            """
            SELECT
                COUNT(CASE WHEN last_indexed_at IS NOT NULL THEN 1 END) as indexed,
                COUNT(CASE WHEN last_indexed_at IS NULL THEN 1 END) as not_indexed
            FROM library_files
        """
        )
        indexing = cur.fetchone()

        return {
            "file_count": totals["file_count"],
            "total_bytes": totals["total_bytes"],
            "total_mb": round(totals["total_bytes"] / (1024 * 1024), 2),
            "by_type": by_type,
            "indexed": indexing["indexed"],
            "not_indexed": indexing["not_indexed"],
            "mount_path": str(self.storage.get_mount_path()),
            "is_mounted": self.storage.is_mounted(),
        }
