# api/services/library/reference_service.py

"""
Service for managing project references to library files.

Projects don't contain files - they reference library items.
This is the bridge between projects and the global library.
"""

from typing import Any, Dict, List

from utils.db import get_db


class LibraryReferenceService:
    """
    Manages the relationship between projects and library files.

    A project can reference any number of library files.
    A library file can be referenced by any number of projects.
    """

    def add_reference(
        self,
        project_id: int,
        library_file_id: int,
        user_id: int = None,
        notes: str = None,
    ) -> Dict[str, Any]:
        """
        Add a library file reference to a project.

        Returns:
            {'id': ref_id, 'status': 'created' | 'exists'}
        """
        conn = get_db()

        # Check if reference already exists
        cur = conn.execute(
            """
            SELECT id FROM project_library_refs
            WHERE project_id = ? AND library_file_id = ?
            """,
            (project_id, library_file_id),
        )
        existing = cur.fetchone()

        if existing:
            return {"id": existing["id"], "status": "exists"}

        # Create reference
        cur = conn.execute(
            """
            INSERT INTO project_library_refs
            (project_id, library_file_id, added_by, notes)
            VALUES (?, ?, ?, ?)
            """,
            (project_id, library_file_id, user_id, notes),
        )
        conn.commit()

        return {"id": cur.lastrowid, "status": "created"}

    def remove_reference(self, project_id: int, library_file_id: int) -> bool:
        """Remove a library file reference from a project."""
        conn = get_db()
        cur = conn.execute(
            """
            DELETE FROM project_library_refs
            WHERE project_id = ? AND library_file_id = ?
            """,
            (project_id, library_file_id),
        )
        conn.commit()
        return cur.rowcount > 0

    def get_project_references(
        self,
        project_id: int,
        include_file_details: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get all library files referenced by a project.

        Args:
            project_id: The project ID
            include_file_details: If True, join with library_files for full info
        """
        conn = get_db()

        if include_file_details:
            cur = conn.execute(
                """
                SELECT
                    plr.id as ref_id,
                    plr.added_at,
                    plr.notes,
                    lf.*
                FROM project_library_refs plr
                JOIN library_files lf ON plr.library_file_id = lf.id
                WHERE plr.project_id = ?
                ORDER BY plr.added_at DESC
                """,
                (project_id,),
            )
        else:
            cur = conn.execute(
                """
                SELECT * FROM project_library_refs
                WHERE project_id = ?
                ORDER BY added_at DESC
                """,
                (project_id,),
            )

        return [dict(row) for row in cur.fetchall()]

    def get_file_references(self, library_file_id: int) -> List[Dict[str, Any]]:
        """
        Get all projects that reference a library file.

        Useful for knowing impact before deleting a library file.
        """
        conn = get_db()
        cur = conn.execute(
            """
            SELECT
                plr.*,
                p.name as project_name
            FROM project_library_refs plr
            JOIN projects p ON plr.project_id = p.id
            WHERE plr.library_file_id = ?
            ORDER BY plr.added_at DESC
            """,
            (library_file_id,),
        )
        return [dict(row) for row in cur.fetchall()]

    def update_reference_notes(
        self,
        project_id: int,
        library_file_id: int,
        notes: str,
    ) -> bool:
        """Update the notes on a project-library reference."""
        conn = get_db()
        cur = conn.execute(
            """
            UPDATE project_library_refs
            SET notes = ?
            WHERE project_id = ? AND library_file_id = ?
            """,
            (notes, project_id, library_file_id),
        )
        conn.commit()
        return cur.rowcount > 0

    def bulk_add_references(
        self,
        project_id: int,
        library_file_ids: List[int],
        user_id: int = None,
    ) -> Dict[str, Any]:
        """
        Add multiple library files to a project at once.

        Returns:
            {'added': int, 'skipped': int, 'ids': [...]}
        """
        added = 0
        skipped = 0
        ids = []

        for file_id in library_file_ids:
            result = self.add_reference(project_id, file_id, user_id)
            if result["status"] == "created":
                added += 1
            else:
                skipped += 1
            ids.append(result["id"])

        return {
            "added": added,
            "skipped": skipped,
            "ids": ids,
        }

    def is_referenced(self, library_file_id: int) -> bool:
        """Check if a library file is referenced by any project."""
        conn = get_db()
        cur = conn.execute(
            "SELECT 1 FROM project_library_refs WHERE library_file_id = ? LIMIT 1",
            (library_file_id,),
        )
        return cur.fetchone() is not None

    def get_reference_count(self, library_file_id: int) -> int:
        """Get number of projects referencing a library file."""
        conn = get_db()
        cur = conn.execute(
            "SELECT COUNT(*) as count FROM project_library_refs WHERE library_file_id = ?",
            (library_file_id,),
        )
        return cur.fetchone()["count"]
