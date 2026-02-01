# api/services/library/collection_service.py

"""
Library collection service for organizing files into named groups.

Collections are flat (no hierarchy) and files can belong to multiple collections.
Future: If hierarchical is needed, add parent_id to library_collections table.
"""

from typing import Any, Dict, List, Optional

from utils.db import get_db


class LibraryCollectionService:
    """Service for managing library collections."""

    # =========================================================================
    # COLLECTION CRUD
    # =========================================================================

    def create_collection(
        self,
        name: str,
        description: Optional[str] = None,
        color: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new collection.

        Args:
            name: Collection name (required)
            description: Optional description
            color: Hex color for UI display (default: #6366f1)

        Returns:
            Dict with 'id' and collection details
        """
        conn = get_db()
        cur = conn.execute(
            """
            INSERT INTO library_collections (name, description, color)
            VALUES (?, ?, COALESCE(?, '#6366f1'))
            """,
            (name, description, color),
        )
        conn.commit()

        collection_id = cur.lastrowid
        return self.get_collection(collection_id)

    def get_collection(self, collection_id: int) -> Optional[Dict[str, Any]]:
        """Get a collection by ID, including file count."""
        conn = get_db()
        cur = conn.execute(
            """
            SELECT
                c.*,
                COUNT(cf.library_file_id) as file_count
            FROM library_collections c
            LEFT JOIN library_collection_files cf ON c.id = cf.collection_id
            WHERE c.id = ?
            GROUP BY c.id
            """,
            (collection_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def list_collections(self) -> List[Dict[str, Any]]:
        """List all collections with file counts, sorted by name."""
        conn = get_db()
        cur = conn.execute(
            """
            SELECT
                c.*,
                COUNT(cf.library_file_id) as file_count
            FROM library_collections c
            LEFT JOIN library_collection_files cf ON c.id = cf.collection_id
            GROUP BY c.id
            ORDER BY c.name ASC
            """
        )
        return [dict(row) for row in cur.fetchall()]

    def update_collection(
        self,
        collection_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update a collection's properties.

        Returns updated collection or None if not found.
        """
        existing = self.get_collection(collection_id)
        if not existing:
            return None

        conn = get_db()

        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)

        if description is not None:
            updates.append("description = ?")
            params.append(description)

        if color is not None:
            updates.append("color = ?")
            params.append(color)

        if not updates:
            return existing

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(collection_id)

        conn.execute(
            f"UPDATE library_collections SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()

        return self.get_collection(collection_id)

    def delete_collection(self, collection_id: int) -> bool:
        """
        Delete a collection. Files remain in the library.

        Returns True if deleted, False if not found.
        """
        conn = get_db()
        cur = conn.execute(
            "DELETE FROM library_collections WHERE id = ?",
            (collection_id,),
        )
        conn.commit()
        return cur.rowcount > 0

    # =========================================================================
    # FILE MEMBERSHIP
    # =========================================================================

    def add_file(self, collection_id: int, library_file_id: int) -> bool:
        """
        Add a file to a collection.

        Returns True if added, False if already in collection or error.
        """
        conn = get_db()
        try:
            conn.execute(
                """
                INSERT INTO library_collection_files (collection_id, library_file_id)
                VALUES (?, ?)
                """,
                (collection_id, library_file_id),
            )
            conn.commit()
            return True
        except Exception:
            # Already exists or foreign key violation
            return False

    def add_files(self, collection_id: int, library_file_ids: List[int]) -> int:
        """
        Add multiple files to a collection.

        Returns count of files successfully added.
        """
        added = 0
        for file_id in library_file_ids:
            if self.add_file(collection_id, file_id):
                added += 1
        return added

    def remove_file(self, collection_id: int, library_file_id: int) -> bool:
        """
        Remove a file from a collection.

        Returns True if removed, False if not in collection.
        """
        conn = get_db()
        cur = conn.execute(
            """
            DELETE FROM library_collection_files
            WHERE collection_id = ? AND library_file_id = ?
            """,
            (collection_id, library_file_id),
        )
        conn.commit()
        return cur.rowcount > 0

    def get_files(
        self,
        collection_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get files in a collection with full file info.

        Returns list of library files with added_at timestamp.
        """
        conn = get_db()
        cur = conn.execute(
            """
            SELECT
                lf.*,
                cf.added_at as collection_added_at
            FROM library_files lf
            INNER JOIN library_collection_files cf ON lf.id = cf.library_file_id
            WHERE cf.collection_id = ?
            ORDER BY cf.added_at DESC
            LIMIT ? OFFSET ?
            """,
            (collection_id, limit, offset),
        )
        return [self._file_row_to_dict(row) for row in cur.fetchall()]

    def get_file_collections(self, library_file_id: int) -> List[Dict[str, Any]]:
        """
        Get all collections a file belongs to.

        Returns list of collection dicts (without file counts for efficiency).
        """
        conn = get_db()
        cur = conn.execute(
            """
            SELECT c.*
            FROM library_collections c
            INNER JOIN library_collection_files cf ON c.id = cf.collection_id
            WHERE cf.library_file_id = ?
            ORDER BY c.name ASC
            """,
            (library_file_id,),
        )
        return [dict(row) for row in cur.fetchall()]

    def get_collection_file_count(self, collection_id: int) -> int:
        """Get the number of files in a collection."""
        conn = get_db()
        cur = conn.execute(
            "SELECT COUNT(*) as count FROM library_collection_files WHERE collection_id = ?",
            (collection_id,),
        )
        return cur.fetchone()["count"]

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _file_row_to_dict(self, row) -> Dict[str, Any]:
        """Convert file row to dict with parsed metadata."""
        import json

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
