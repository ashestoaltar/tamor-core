# api/services/library/text_service.py

"""
Text extraction and caching for library files.

Reuses existing parsing infrastructure but stores in library-specific tables.
"""

import json
from typing import Any, Dict, Optional, Tuple

from services.file_parsing import clean_extracted_text, extract_text_from_file
from utils.db import get_db

from .library_service import LibraryService
from .storage_service import LibraryStorageService


class LibraryTextService:
    """Service for extracting and caching text from library files."""

    def __init__(self):
        self.storage = LibraryStorageService()
        self.library = LibraryService()

    def get_text(
        self, library_file_id: int, clean: bool = True
    ) -> Tuple[Optional[str], Optional[Dict]]:
        """
        Get extracted text for a library file.

        Args:
            library_file_id: ID of the library file
            clean: Whether to apply text cleanup (remove page numbers, merge lines)

        Returns:
            (text, metadata) or (None, None) if not available
        """
        # Check cache first
        cached = self._get_cached_text(library_file_id)
        if cached:
            text, meta = cached
            if clean and text:
                text = clean_extracted_text(text)
            return (text, meta)

        # Extract and cache
        result = self._extract_and_cache(library_file_id)
        if result and clean and result[0]:
            return (clean_extracted_text(result[0]), result[1])
        return result

    def _get_cached_text(self, library_file_id: int) -> Optional[Tuple[str, Dict]]:
        """Get text from cache if available."""
        conn = get_db()
        cur = conn.execute(
            """
            SELECT text_content, meta_json, parser
            FROM library_text_cache
            WHERE library_file_id = ?
            """,
            (library_file_id,),
        )
        row = cur.fetchone()

        if not row:
            return None

        meta = {}
        if row["meta_json"]:
            try:
                meta = json.loads(row["meta_json"])
            except json.JSONDecodeError:
                pass

        meta["parser"] = row["parser"]

        return (row["text_content"], meta)

    def _extract_and_cache(
        self, library_file_id: int
    ) -> Tuple[Optional[str], Optional[Dict]]:
        """Extract text from file and cache it."""
        # Get file info
        file = self.library.get_file(library_file_id)
        if not file:
            return (None, None)

        # Resolve full path
        full_path = self.storage.resolve_path(file["stored_path"])
        if not full_path.exists():
            return (None, None)

        # Extract using existing infrastructure
        result = extract_text_from_file(
            str(full_path),
            file.get("mime_type") or "",
            file.get("filename") or "",
        )

        text = result.get("text", "")
        meta = result.get("meta", {})
        parser = result.get("parser", "unknown")

        # Cache it
        meta_json = json.dumps(meta) if meta else None

        conn = get_db()
        conn.execute(
            """
            INSERT OR REPLACE INTO library_text_cache
            (library_file_id, text_content, meta_json, parser)
            VALUES (?, ?, ?, ?)
            """,
            (library_file_id, text, meta_json, parser),
        )
        conn.commit()

        meta["parser"] = parser
        return (text, meta)

    def invalidate_cache(self, library_file_id: int) -> bool:
        """Remove cached text for a file (forces re-extraction on next access)."""
        conn = get_db()
        cur = conn.execute(
            "DELETE FROM library_text_cache WHERE library_file_id = ?",
            (library_file_id,),
        )
        conn.commit()
        return cur.rowcount > 0

    def get_text_preview(
        self, library_file_id: int, max_chars: int = 500
    ) -> Optional[str]:
        """Get a short preview of the extracted text."""
        text, _ = self.get_text(library_file_id)
        if not text:
            return None

        if len(text) <= max_chars:
            return text

        return text[:max_chars] + "..."

    def is_parseable(self, library_file_id: int) -> bool:
        """Check if a file's text was successfully extracted (non-placeholder)."""
        text, meta = self.get_text(library_file_id)

        if not text:
            return False

        # Check for placeholder messages
        placeholder_prefixes = (
            "This file is not a plain-text type.",
            "This file is a PDF, but",
            "Error extracting text",
            "Error reading file",
        )

        return not any(text.startswith(p) for p in placeholder_prefixes)
