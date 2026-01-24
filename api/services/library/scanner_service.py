# api/services/library/scanner_service.py

"""
Directory scanner for library ingest.

Recursively scans configured paths, applies include/exclude patterns,
and yields files eligible for library import.
"""

import fnmatch
import json
import mimetypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from utils.db import get_db

from .storage_service import LibraryStorageService


@dataclass
class ScannedFile:
    """Represents a file discovered during scanning."""

    path: str
    filename: str
    size_bytes: int
    modified_at: datetime
    mime_type: Optional[str]
    relative_path: str  # Path relative to scan root


class LibraryScannerService:
    """Service for scanning directories to discover files for library import."""

    def __init__(self):
        self.storage = LibraryStorageService()

    def _get_config(self, key: str, default: str = None) -> str:
        """Get config from library_config table."""
        conn = get_db()
        cur = conn.execute(
            "SELECT value FROM library_config WHERE key = ?", (key,)
        )
        row = cur.fetchone()
        return row["value"] if row else default

    def _get_patterns(self, key: str) -> List[str]:
        """Get pattern list from config."""
        value = self._get_config(key, "[]")
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return []

    def get_include_patterns(self) -> List[str]:
        """Get file patterns to include."""
        return self._get_patterns("scan_patterns_include")

    def get_exclude_patterns(self) -> List[str]:
        """Get file/folder patterns to exclude."""
        return self._get_patterns("scan_patterns_exclude")

    def set_include_patterns(self, patterns: List[str]) -> None:
        """Update include patterns."""
        self._set_config("scan_patterns_include", json.dumps(patterns))

    def set_exclude_patterns(self, patterns: List[str]) -> None:
        """Update exclude patterns."""
        self._set_config("scan_patterns_exclude", json.dumps(patterns))

    def _set_config(self, key: str, value: str) -> None:
        """Set config value."""
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

    def _matches_patterns(self, name: str, patterns: List[str]) -> bool:
        """Check if name matches any of the glob patterns."""
        for pattern in patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
        return False

    def _should_include_file(self, filename: str) -> bool:
        """Check if file matches include patterns."""
        include = self.get_include_patterns()
        if not include:
            return True  # No include patterns = include all
        return self._matches_patterns(filename.lower(), [p.lower() for p in include])

    def _should_exclude(self, name: str) -> bool:
        """Check if file/folder should be excluded."""
        exclude = self.get_exclude_patterns()
        return self._matches_patterns(name, exclude)

    def _guess_mime_type(self, filename: str) -> Optional[str]:
        """Guess MIME type from filename."""
        mime, _ = mimetypes.guess_type(filename)
        return mime

    def scan_directory(
        self,
        root_path: str = None,
        recursive: bool = True,
        max_files: int = None,
    ) -> Generator[ScannedFile, None, None]:
        """
        Scan a directory for files to import.

        Args:
            root_path: Directory to scan (default: configured mount_path)
            recursive: Whether to scan subdirectories
            max_files: Maximum files to yield (for testing/limiting)

        Yields:
            ScannedFile objects for each matching file
        """
        if root_path is None:
            root_path = self.storage.get_mount_path()

        root = Path(root_path)

        if not root.exists():
            raise FileNotFoundError(f"Scan path does not exist: {root_path}")

        if not root.is_dir():
            raise NotADirectoryError(f"Scan path is not a directory: {root_path}")

        file_count = 0

        if recursive:
            walker = root.rglob("*")
        else:
            walker = root.glob("*")

        for path in walker:
            # Skip directories
            if path.is_dir():
                continue

            # Check excludes (apply to any part of path)
            skip = False
            for part in path.parts:
                if self._should_exclude(part):
                    skip = True
                    break
            if skip:
                continue

            # Check includes
            if not self._should_include_file(path.name):
                continue

            # Get file info
            try:
                stat = path.stat()
            except OSError:
                continue

            yield ScannedFile(
                path=str(path),
                filename=path.name,
                size_bytes=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                mime_type=self._guess_mime_type(path.name),
                relative_path=str(path.relative_to(root)),
            )

            file_count += 1
            if max_files and file_count >= max_files:
                return

    def scan_summary(self, root_path: str = None) -> Dict[str, Any]:
        """
        Quick scan to get summary statistics without full enumeration.

        Returns:
            {
                'root': str,
                'total_files': int,
                'total_bytes': int,
                'by_type': {'pdf': 10, 'epub': 5, ...},
                'sample_files': [...]  # First 10 files
            }
        """
        if root_path is None:
            root_path = str(self.storage.get_mount_path())

        total_files = 0
        total_bytes = 0
        by_type = {}
        sample_files = []

        for scanned in self.scan_directory(root_path, recursive=True):
            total_files += 1
            total_bytes += scanned.size_bytes

            # Categorize by extension
            ext = Path(scanned.filename).suffix.lower().lstrip(".")
            if not ext:
                ext = "unknown"
            by_type[ext] = by_type.get(ext, 0) + 1

            # Collect samples
            if len(sample_files) < 10:
                sample_files.append(
                    {
                        "path": scanned.relative_path,
                        "size": scanned.size_bytes,
                        "type": ext,
                    }
                )

        return {
            "root": root_path,
            "total_files": total_files,
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 2),
            "by_type": by_type,
            "sample_files": sample_files,
        }

    def find_new_files(
        self, root_path: str = None
    ) -> Generator[ScannedFile, None, None]:
        """
        Scan and yield only files not already in the library.

        Checks by stored_path to avoid re-importing existing files.
        """
        conn = get_db()

        for scanned in self.scan_directory(root_path):
            # Check if already in library
            cur = conn.execute(
                "SELECT id FROM library_files WHERE stored_path = ?",
                (scanned.path,),
            )
            if cur.fetchone():
                continue  # Already imported

            yield scanned

    def count_new_files(self, root_path: str = None) -> int:
        """Count files in scan path not yet in library."""
        count = 0
        for _ in self.find_new_files(root_path):
            count += 1
        return count
