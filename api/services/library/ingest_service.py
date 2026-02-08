# api/services/library/ingest_service.py

"""
Library ingest service.

Handles batch importing of files discovered by the scanner.
Supports progress tracking and incremental sync.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from utils.db import get_db

from .chunk_service import LibraryChunkService
from .collection_service import LibraryCollectionService
from .library_service import LibraryService
from .ocr_service import LibraryOCRService
from .scanner_service import LibraryScannerService, ScannedFile


@dataclass
class IngestProgress:
    """Tracks progress of an ingest operation."""

    total: int = 0
    processed: int = 0
    created: int = 0
    duplicates: int = 0
    errors: int = 0
    current_file: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    error_details: List[Dict] = field(default_factory=list)

    @property
    def percent_complete(self) -> float:
        if self.total == 0:
            return 0
        return round((self.processed / self.total) * 100, 1)

    @property
    def elapsed_seconds(self) -> float:
        return (datetime.now() - self.started_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "processed": self.processed,
            "created": self.created,
            "duplicates": self.duplicates,
            "errors": self.errors,
            "percent_complete": self.percent_complete,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "current_file": self.current_file,
            "error_details": self.error_details[-10:],  # Last 10 errors
        }


class LibraryIngestService:
    """Service for batch importing files into the library."""

    # Source-based collection rules: path prefix → collection name
    # Collection must already exist in the database.
    SOURCE_COLLECTION_RULES = [
        ("religious/119/", "119 Ministries"),
        ("religious/billcloud", "Bill Cloud"),
        ("religious/wildbranch", "WildBranch Ministries"),
        ("religious/barkingfox", "Barking Fox (Albert McCarn)"),
        ("religious/davidwilber", "David Wilber"),
        ("religious/torahmatters", "Torah Matters"),
        ("religious/torahapologetics", "Torah Apologetics (Jonathan Brown)"),
        ("religious/torahresource", "TorahResource"),
        ("religious/lionlamb", "Lion & Lamb"),
        ("religious/gods-purpose", "Gods Purpose for America"),
        ("religious/jewish-christian-origins", "Jewish-Christian Origins"),
        ("harvest/torah-class", "Torah Class"),
        ("oll/", "Online Library of Liberty"),
        ("internet_archive", "Internet Archive"),
        ("founders-online", "Founders Online"),
    ]

    def __init__(self):
        self.library = LibraryService()
        self.scanner = LibraryScannerService()
        self.chunker = LibraryChunkService()
        self.ocr = LibraryOCRService()
        self.collections = LibraryCollectionService()

        # Track active ingest operations
        self._active_ingests: Dict[str, IngestProgress] = {}

        # Cache collection name → id lookups
        self._collection_id_cache: Dict[str, Optional[int]] = {}

    def ingest_file(
        self,
        scanned_file: ScannedFile,
        auto_index: bool = True,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Import a single scanned file into the library.

        Args:
            scanned_file: File discovered by scanner
            auto_index: If True, generate chunks/embeddings immediately
            metadata: Optional metadata to attach

        Returns:
            {'id': int, 'status': 'created'|'duplicate'|'error', 'error': str?}
        """
        try:
            # Build metadata
            file_metadata = metadata or {}
            file_metadata["source_path"] = scanned_file.relative_path
            file_metadata["imported_at"] = datetime.now().isoformat()

            # Add to library
            result = self.library.add_file(
                file_path=scanned_file.path,
                source_type="scan",
                metadata=file_metadata,
                check_duplicate=True,
            )

            # Auto-assign to source collection
            if result["status"] == "created":
                self._auto_assign_collections(result["id"], scanned_file.relative_path)

            # Auto-index if requested and file was created
            if auto_index and result["status"] == "created":
                try:
                    self.chunker.get_chunks(result["id"])
                except Exception as e:
                    # Indexing failure shouldn't fail the import
                    result["index_error"] = str(e)

                # Check if OCR is needed (scanned PDF with no/little text)
                if self.ocr.is_ocr_available():
                    ocr_result = self.ocr.process_if_needed(result["id"])
                    if ocr_result["ocr_run"] and ocr_result.get("result", {}).get("success"):
                        # Re-index after OCR
                        try:
                            self.chunker.reindex_file(result["id"])
                            result["ocr_applied"] = True
                        except Exception as e:
                            result["ocr_reindex_error"] = str(e)

            return result

        except Exception as e:
            return {"id": None, "status": "error", "error": str(e)}

    def ingest_directory(
        self,
        path: str = None,
        auto_index: bool = True,
        new_only: bool = True,
        progress_callback: Callable[[IngestProgress], None] = None,
    ) -> IngestProgress:
        """
        Import all eligible files from a directory.

        Args:
            path: Directory to scan (default: configured mount_path)
            auto_index: Generate embeddings during import
            new_only: Skip files already in library
            progress_callback: Called after each file with progress

        Returns:
            Final IngestProgress with results
        """
        progress = IngestProgress()

        # Get files to process
        if new_only:
            files = list(self.scanner.find_new_files(path))
        else:
            files = list(self.scanner.scan_directory(path))

        progress.total = len(files)

        for scanned in files:
            progress.current_file = scanned.filename

            result = self.ingest_file(scanned, auto_index=auto_index)

            progress.processed += 1

            if result["status"] == "created":
                progress.created += 1
            elif result["status"] == "duplicate":
                progress.duplicates += 1
            elif result["status"] == "error":
                progress.errors += 1
                progress.error_details.append(
                    {
                        "file": scanned.path,
                        "error": result.get("error", "Unknown error"),
                    }
                )

            if progress_callback:
                progress_callback(progress)

        progress.current_file = ""
        return progress

    def start_background_ingest(
        self,
        ingest_id: str,
        path: str = None,
        auto_index: bool = True,
        new_only: bool = True,
    ) -> Dict[str, Any]:
        """
        Start a background ingest operation.

        The actual background execution would need a task queue (Celery, etc.)
        or threading. For now, this provides the interface and tracking.

        Returns:
            {'ingest_id': str, 'status': 'started', 'total': int}
        """
        # Count files to process
        if new_only:
            total = self.scanner.count_new_files(path)
        else:
            total = sum(1 for _ in self.scanner.scan_directory(path))

        # Initialize progress tracking
        progress = IngestProgress(total=total)
        self._active_ingests[ingest_id] = progress

        # TODO: In production, dispatch to background worker
        # For now, caller can use ingest_directory() synchronously
        # or implement their own threading

        return {"ingest_id": ingest_id, "status": "started", "total": total}

    def get_ingest_progress(self, ingest_id: str) -> Optional[Dict[str, Any]]:
        """Get progress for an active ingest operation."""
        progress = self._active_ingests.get(ingest_id)
        if not progress:
            return None
        return progress.to_dict()

    def ingest_batch(
        self,
        file_paths: List[str],
        auto_index: bool = True,
        progress_callback: Callable[[IngestProgress], None] = None,
    ) -> IngestProgress:
        """
        Import a specific list of files.

        Args:
            file_paths: List of absolute file paths to import
            auto_index: Generate embeddings during import
            progress_callback: Called after each file

        Returns:
            Final IngestProgress
        """
        progress = IngestProgress(total=len(file_paths))

        for file_path in file_paths:
            path = Path(file_path)
            progress.current_file = path.name

            if not path.exists():
                progress.processed += 1
                progress.errors += 1
                progress.error_details.append(
                    {"file": file_path, "error": "File not found"}
                )
                continue

            # Create ScannedFile manually
            scanned = ScannedFile(
                path=str(path),
                filename=path.name,
                size_bytes=path.stat().st_size,
                modified_at=datetime.fromtimestamp(path.stat().st_mtime),
                mime_type=self.scanner._guess_mime_type(path.name),
                relative_path=str(path),
            )

            result = self.ingest_file(scanned, auto_index=auto_index)

            progress.processed += 1

            if result["status"] == "created":
                progress.created += 1
            elif result["status"] == "duplicate":
                progress.duplicates += 1
            elif result["status"] == "error":
                progress.errors += 1
                progress.error_details.append(
                    {"file": file_path, "error": result.get("error")}
                )

            if progress_callback:
                progress_callback(progress)

        progress.current_file = ""
        return progress

    def sync_library(
        self,
        path: str = None,
        remove_missing: bool = False,
    ) -> Dict[str, Any]:
        """
        Synchronize library with filesystem.

        - Adds new files
        - Optionally removes records for deleted files

        Args:
            path: Directory to sync (default: mount_path)
            remove_missing: If True, delete records for files no longer on disk

        Returns:
            {'added': int, 'removed': int, 'unchanged': int}
        """
        result = {"added": 0, "removed": 0, "unchanged": 0, "errors": 0}

        # Add new files
        for scanned in self.scanner.find_new_files(path):
            res = self.ingest_file(scanned, auto_index=True)
            if res["status"] == "created":
                result["added"] += 1
            elif res["status"] == "error":
                result["errors"] += 1

        # Check for removed files
        if remove_missing:
            conn = get_db()
            cur = conn.execute("SELECT id, stored_path FROM library_files")

            for row in cur.fetchall():
                file_path = Path(row["stored_path"])

                # Try relative to mount path
                if not file_path.is_absolute():
                    file_path = self.scanner.storage.resolve_path(row["stored_path"])

                if not file_path.exists():
                    # File is gone - remove from library
                    self.library.delete_file(row["id"], delete_from_disk=False)
                    result["removed"] += 1
                else:
                    result["unchanged"] += 1

        return result

    # =========================================================================
    # COLLECTION AUTO-ASSIGNMENT
    # =========================================================================

    def _get_collection_id(self, name: str) -> Optional[int]:
        """Look up collection ID by name, with caching."""
        if name not in self._collection_id_cache:
            conn = get_db()
            row = conn.execute(
                "SELECT id FROM library_collections WHERE name = ?", (name,)
            ).fetchone()
            self._collection_id_cache[name] = row["id"] if row else None
        return self._collection_id_cache[name]

    def _auto_assign_collections(self, file_id: int, stored_path: str) -> None:
        """
        Auto-assign a newly ingested file to source-based collections
        based on its stored path.
        """
        for prefix, collection_name in self.SOURCE_COLLECTION_RULES:
            if stored_path.startswith(prefix):
                collection_id = self._get_collection_id(collection_name)
                if collection_id:
                    self.collections.add_file(collection_id, file_id)
                break  # First match wins (most specific prefix listed first)
