# api/services/library/storage_service.py

"""
Library storage service for managing file storage operations.

Handles:
- Mount path configuration
- File hash computation for deduplication
- Path resolution (absolute vs relative to mount)
"""

import hashlib
from pathlib import Path
from typing import Optional

from utils.db import get_db


class LibraryStorageService:
    """Service for library file storage operations."""

    def __init__(self):
        self.mount_path = self._get_config("mount_path", "/mnt/library")

    def _get_config(self, key: str, default: str = None) -> str:
        """Get library config value from database."""
        conn = get_db()
        cur = conn.execute(
            "SELECT value FROM library_config WHERE key = ?",
            (key,),
        )
        row = cur.fetchone()
        return row["value"] if row else default

    def _set_config(self, key: str, value: str) -> None:
        """Set library config value."""
        conn = get_db()
        conn.execute(
            """
            INSERT INTO library_config (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = CURRENT_TIMESTAMP
            """,
            (key, value, value),
        )
        conn.commit()

    def get_mount_path(self) -> Path:
        """Get the configured library mount path."""
        return Path(self.mount_path)

    def is_mounted(self) -> bool:
        """Check if library storage is accessible."""
        mount = self.get_mount_path()
        return mount.exists() and mount.is_dir()

    def compute_file_hash(self, file_path: str) -> str:
        """Compute SHA-256 hash of a file for deduplication."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def find_by_hash(self, file_hash: str) -> Optional[dict]:
        """Check if a file with this hash already exists in library."""
        conn = get_db()
        cur = conn.execute(
            "SELECT * FROM library_files WHERE file_hash = ?",
            (file_hash,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def resolve_path(self, stored_path: str) -> Path:
        """
        Resolve a stored path to full filesystem path.

        stored_path can be:
        - Absolute: /mnt/library/books/file.pdf
        - Relative to mount: books/file.pdf
        """
        path = Path(stored_path)
        if path.is_absolute():
            return path
        return self.get_mount_path() / path

    def get_relative_path(self, absolute_path: str) -> str:
        """Convert absolute path to path relative to mount point."""
        abs_path = Path(absolute_path)
        mount = self.get_mount_path()
        try:
            return str(abs_path.relative_to(mount))
        except ValueError:
            # Path is not under mount point, store as-is
            return str(abs_path)
