# api/services/library/index_queue_service.py

"""
Background indexing queue for library files.

Allows files to be added to library quickly, with embedding generation
happening asynchronously in the background.
"""

from typing import Any, Dict, List

from utils.db import get_db

from .chunk_service import LibraryChunkService
from .library_service import LibraryService


class LibraryIndexQueueService:
    """Service for managing background indexing of library files."""

    def __init__(self):
        self.library = LibraryService()
        self.chunker = LibraryChunkService()

    def get_unindexed_files(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get library files that haven't been indexed yet.

        Returns files where last_indexed_at is NULL.
        """
        conn = get_db()
        cur = conn.execute(
            """
            SELECT * FROM library_files
            WHERE last_indexed_at IS NULL
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about the indexing queue."""
        conn = get_db()

        # Count unindexed
        cur = conn.execute(
            "SELECT COUNT(*) as count FROM library_files WHERE last_indexed_at IS NULL"
        )
        unindexed = cur.fetchone()["count"]

        # Count indexed
        cur = conn.execute(
            "SELECT COUNT(*) as count FROM library_files WHERE last_indexed_at IS NOT NULL"
        )
        indexed = cur.fetchone()["count"]

        # Oldest unindexed
        cur = conn.execute(
            """
            SELECT created_at FROM library_files
            WHERE last_indexed_at IS NULL
            ORDER BY created_at ASC LIMIT 1
            """
        )
        row = cur.fetchone()
        oldest_pending = row["created_at"] if row else None

        return {
            "unindexed": unindexed,
            "indexed": indexed,
            "total": unindexed + indexed,
            "oldest_pending": oldest_pending,
            "queue_empty": unindexed == 0,
        }

    def index_next(self, count: int = 1) -> Dict[str, Any]:
        """
        Index the next N files in the queue.

        Returns:
            {'processed': int, 'success': int, 'errors': int, 'details': [...]}
        """
        files = self.get_unindexed_files(limit=count)

        results = {"processed": 0, "success": 0, "errors": 0, "details": []}

        for file in files:
            results["processed"] += 1

            try:
                chunks = self.chunker.get_chunks(file["id"])
                results["success"] += 1
                results["details"].append(
                    {
                        "file_id": file["id"],
                        "filename": file["filename"],
                        "status": "indexed",
                        "chunks": len(chunks),
                    }
                )
            except Exception as e:
                results["errors"] += 1
                results["details"].append(
                    {
                        "file_id": file["id"],
                        "filename": file["filename"],
                        "status": "error",
                        "error": str(e),
                    }
                )

        return results

    def index_all(self, batch_size: int = 10) -> Dict[str, Any]:
        """
        Process entire queue in batches.

        Warning: This can take a long time for large queues!
        Consider using index_next() in a loop with progress tracking.
        """
        total_processed = 0
        total_success = 0
        total_errors = 0

        while True:
            result = self.index_next(count=batch_size)

            if result["processed"] == 0:
                break

            total_processed += result["processed"]
            total_success += result["success"]
            total_errors += result["errors"]

        return {
            "processed": total_processed,
            "success": total_success,
            "errors": total_errors,
            "queue_empty": True,
        }

    def reindex_all(self, batch_size: int = 10) -> Dict[str, Any]:
        """
        Force reindex of all library files.

        Clears last_indexed_at and processes everything.
        """
        conn = get_db()

        # Clear all indexed timestamps
        conn.execute("UPDATE library_files SET last_indexed_at = NULL")
        conn.commit()

        # Now process queue
        return self.index_all(batch_size=batch_size)

    def mark_for_reindex(self, file_ids: List[int]) -> int:
        """Mark specific files for reindexing."""
        if not file_ids:
            return 0

        conn = get_db()
        placeholders = ",".join("?" * len(file_ids))
        cur = conn.execute(
            f"UPDATE library_files SET last_indexed_at = NULL WHERE id IN ({placeholders})",
            file_ids,
        )
        conn.commit()
        return cur.rowcount
