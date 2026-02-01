# api/services/library/ia_import_service.py

"""
Internet Archive import service.

Bridge between ia_harvester provenance tracking and Tamor's library system.
Imports downloaded IA items into the main library while preserving provenance.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.db import get_db

from .ingest_service import LibraryIngestService
from .scanner_service import ScannedFile


class IAImportService:
    """Service for importing Internet Archive items into Tamor's library."""

    def __init__(self):
        self.ingest = LibraryIngestService()

    def get_pending_items(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get IA items downloaded but not yet imported to library.

        Returns:
            List of ia_items records pending import
        """
        conn = get_db()
        query = """
            SELECT *
            FROM ia_items
            WHERE local_path IS NOT NULL
              AND imported_to_library = 0
            ORDER BY download_date DESC
        """
        if limit:
            query += f" LIMIT {limit}"

        cur = conn.execute(query)
        return [dict(row) for row in cur.fetchall()]

    def import_item(self, ia_item_id: int, auto_index: bool = True) -> Dict[str, Any]:
        """
        Import a single IA item into the library.

        Args:
            ia_item_id: ID from ia_items table
            auto_index: Generate embeddings during import

        Returns:
            {'status': 'imported'|'error'|'not_found', 'library_file_id': int?}
        """
        conn = get_db()

        # Get IA item
        cur = conn.execute(
            "SELECT * FROM ia_items WHERE id = ?",
            (ia_item_id,)
        )
        row = cur.fetchone()
        if not row:
            return {"status": "not_found", "error": "IA item not found"}

        item = dict(row)

        if not item.get("local_path"):
            return {"status": "error", "error": "No local file path"}

        local_path = Path(item["local_path"])
        if not local_path.exists():
            return {"status": "error", "error": f"File not found: {local_path}"}

        # Build rich metadata from IA provenance
        metadata = {
            "source": "internet_archive",
            "ia_identifier": item["identifier"],
            "ia_source_url": item["source_url"],
            "ia_download_date": item["download_date"],
            "title": item.get("title"),
            "author": item.get("creator"),
            "date": item.get("date"),
            "subject": item.get("subject"),
            "description": item.get("description"),
            "collection": item.get("collection"),
            "public_domain": bool(item.get("public_domain", 1)),
        }

        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}

        # Create ScannedFile for ingest
        scanned = ScannedFile(
            path=str(local_path),
            filename=local_path.name,
            size_bytes=local_path.stat().st_size,
            modified_at=datetime.fromtimestamp(local_path.stat().st_mtime),
            mime_type=self.ingest.scanner._guess_mime_type(local_path.name),
            relative_path=str(local_path),
        )

        # Ingest via standard pipeline (includes OCR if needed)
        result = self.ingest.ingest_file(scanned, auto_index=auto_index, metadata=metadata)

        if result["status"] in ("created", "duplicate"):
            # Mark as imported in ia_items
            conn.execute(
                """
                UPDATE ia_items
                SET imported_to_library = 1, library_file_id = ?
                WHERE id = ?
                """,
                (result["id"], ia_item_id)
            )
            conn.commit()

            return {
                "status": "imported",
                "library_file_id": result["id"],
                "was_duplicate": result["status"] == "duplicate",
                "title": item.get("title"),
            }

        return {
            "status": "error",
            "error": result.get("error", "Unknown ingest error"),
        }

    def import_all_pending(
        self,
        auto_index: bool = True,
        limit: int = None,
    ) -> Dict[str, Any]:
        """
        Import all pending IA items into the library.

        Args:
            auto_index: Generate embeddings during import
            limit: Maximum items to import (None = all)

        Returns:
            {'imported': int, 'duplicates': int, 'errors': int, 'error_details': list}
        """
        pending = self.get_pending_items(limit=limit)

        results = {
            "total": len(pending),
            "imported": 0,
            "duplicates": 0,
            "errors": 0,
            "error_details": [],
        }

        for item in pending:
            print(f"Importing: {item['identifier']} - {item.get('title', 'Untitled')[:50]}")

            result = self.import_item(item["id"], auto_index=auto_index)

            if result["status"] == "imported":
                if result.get("was_duplicate"):
                    results["duplicates"] += 1
                else:
                    results["imported"] += 1
            else:
                results["errors"] += 1
                results["error_details"].append({
                    "identifier": item["identifier"],
                    "error": result.get("error"),
                })

        return results

    def get_import_stats(self) -> Dict[str, Any]:
        """Get statistics about IA imports."""
        conn = get_db()

        # Check if ia_items table exists
        cur = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='ia_items'
        """)
        if not cur.fetchone():
            return {
                "table_exists": False,
                "total_items": 0,
                "downloaded": 0,
                "imported": 0,
                "pending": 0,
            }

        cur = conn.execute("SELECT COUNT(*) FROM ia_items")
        total = cur.fetchone()[0]

        cur = conn.execute(
            "SELECT COUNT(*) FROM ia_items WHERE local_path IS NOT NULL"
        )
        downloaded = cur.fetchone()[0]

        cur = conn.execute(
            "SELECT COUNT(*) FROM ia_items WHERE imported_to_library = 1"
        )
        imported = cur.fetchone()[0]

        cur = conn.execute(
            "SELECT SUM(file_size) FROM ia_items WHERE local_path IS NOT NULL"
        )
        total_bytes = cur.fetchone()[0] or 0

        return {
            "table_exists": True,
            "total_items": total,
            "downloaded": downloaded,
            "imported": imported,
            "pending": downloaded - imported,
            "total_size_mb": round(total_bytes / (1024 * 1024), 2),
        }

    def search_ia_items(
        self,
        query: str = None,
        imported_only: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search IA items in the database.

        Args:
            query: Search term (searches title, creator, subject)
            imported_only: Only return items imported to library
            limit: Maximum results

        Returns:
            List of matching ia_items records
        """
        conn = get_db()

        sql = "SELECT * FROM ia_items WHERE 1=1"
        params = []

        if query:
            sql += """ AND (
                title LIKE ? OR
                creator LIKE ? OR
                subject LIKE ? OR
                identifier LIKE ?
            )"""
            like_query = f"%{query}%"
            params.extend([like_query, like_query, like_query, like_query])

        if imported_only:
            sql += " AND imported_to_library = 1"

        sql += f" ORDER BY download_date DESC LIMIT {limit}"

        cur = conn.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]
