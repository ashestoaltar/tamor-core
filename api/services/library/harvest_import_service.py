"""
Harvest import service.

Imports pre-processed packages from the harvesting cluster into
Tamor's library. Packages contain pre-chunked text with pre-generated
embeddings, so import is lightweight — just database inserts.
"""

import base64
import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.db import get_db

from .collection_service import LibraryCollectionService
from .library_service import LibraryService

# Expected package format version
SUPPORTED_FORMAT_VERSIONS = ["1.0"]

# NAS paths
HARVEST_READY_DIR = "/mnt/library/harvest/ready"
HARVEST_IMPORTED_DIR = "/mnt/library/harvest/ready/imported"


class HarvestImportService:
    """Service for importing pre-processed harvest packages."""

    def __init__(self):
        self.library = LibraryService()
        self.collections = LibraryCollectionService()
        self._collection_id_cache = {}

    def list_pending(self) -> List[Dict[str, Any]]:
        """List package files in the ready directory waiting for import."""
        if not os.path.isdir(HARVEST_READY_DIR):
            return []

        packages = []
        for filename in sorted(os.listdir(HARVEST_READY_DIR)):
            if not filename.endswith(".json"):
                continue

            filepath = os.path.join(HARVEST_READY_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                is_batch = data.get("batch", False)

                if is_batch:
                    packages.append({
                        "filename": filename,
                        "path": filepath,
                        "batch": True,
                        "package_count": data.get("package_count", 0),
                        "batch_name": data.get("batch_name"),
                        "created_at": data.get("created_at"),
                    })
                else:
                    packages.append({
                        "filename": filename,
                        "path": filepath,
                        "batch": False,
                        "source": data.get("source", {}).get("name"),
                        "title": data.get("file", {}).get("title"),
                        "chunk_count": data.get("processing", {}).get("chunk_count", 0),
                        "created_at": data.get("processing", {}).get("processed_at"),
                    })
            except (json.JSONDecodeError, KeyError):
                packages.append({
                    "filename": filename,
                    "path": filepath,
                    "error": "Invalid package format",
                })

        return packages

    def import_package(self, package_path: str) -> Dict[str, Any]:
        """
        Import a single package file (may contain one package or a batch).

        Returns:
            {
                'imported': int,
                'skipped': int,
                'errors': int,
                'details': [...]
            }
        """
        with open(package_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        is_batch = data.get("batch", False)

        if is_batch:
            packages = data.get("packages", [])
        else:
            packages = [data]

        result = {"imported": 0, "skipped": 0, "errors": 0, "details": []}

        for pkg in packages:
            detail = self._import_single_package(pkg)
            result["details"].append(detail)

            if detail["status"] == "imported":
                result["imported"] += 1
            elif detail["status"] == "duplicate":
                result["skipped"] += 1
            else:
                result["errors"] += 1

        # Move to imported directory on success
        if result["errors"] == 0:
            self._move_to_imported(package_path)

        return result

    def import_all_pending(self) -> Dict[str, Any]:
        """Import all pending packages from the ready directory."""
        pending = self.list_pending()
        total_result = {
            "files_processed": 0,
            "imported": 0,
            "skipped": 0,
            "errors": 0,
        }

        for pkg_info in pending:
            if "error" in pkg_info:
                total_result["errors"] += 1
                continue

            result = self.import_package(pkg_info["path"])
            total_result["files_processed"] += 1
            total_result["imported"] += result["imported"]
            total_result["skipped"] += result["skipped"]
            total_result["errors"] += result["errors"]

        return total_result

    def _import_single_package(self, package: Dict) -> Dict[str, Any]:
        """
        Import a single package dict into the library.

        Creates a library_files record and inserts pre-built chunks
        with embeddings into library_chunks.
        """
        try:
            # Validate format
            version = package.get("format_version")
            if version not in SUPPORTED_FORMAT_VERSIONS:
                return {
                    "status": "error",
                    "error": f"Unsupported format version: {version}",
                }

            file_info = package.get("file", {})
            source_info = package.get("source", {})
            processing_info = package.get("processing", {})
            chunks = package.get("chunks", [])

            filename = file_info.get("filename", "unknown")
            content_hash = file_info.get("content_hash")

            # Check for duplicate by content hash
            if content_hash:
                conn = get_db()
                existing = conn.execute(
                    "SELECT id FROM library_files WHERE file_hash = ?",
                    (content_hash,),
                ).fetchone()
                if existing:
                    return {
                        "status": "duplicate",
                        "filename": filename,
                        "existing_id": existing["id"],
                    }

            # Build metadata JSON
            metadata = file_info.get("metadata", {})
            metadata["harvest_source"] = source_info.get("name")
            metadata["harvest_teacher"] = source_info.get("teacher")
            metadata["harvest_content_type"] = source_info.get("content_type")
            metadata["harvest_url"] = source_info.get("url")
            metadata["harvest_copyright"] = source_info.get("copyright_note")
            metadata["harvest_processed_at"] = processing_info.get("processed_at")
            metadata["harvest_processor"] = processing_info.get("processor_host")
            # Remove None values
            metadata = {k: v for k, v in metadata.items() if v is not None}

            # Determine stored_path
            stored_path = file_info.get("stored_path", "")
            if not stored_path:
                # Generate a stored path from source name
                source_slug = (
                    source_info.get("name", "unknown")
                    .lower()
                    .replace(" ", "-")
                )
                stored_path = f"harvest/{source_slug}/{filename}"

            # Insert library_files record
            conn = get_db()
            cur = conn.execute(
                """
                INSERT INTO library_files
                (filename, stored_path, file_hash, mime_type, size_bytes,
                 source_type, metadata_json, text_content, text_extracted_at,
                 last_indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    filename,
                    stored_path,
                    content_hash,
                    file_info.get("mime_type", "text/plain"),
                    file_info.get("text_length", 0),
                    "harvest",
                    json.dumps(metadata),
                    None,  # text_content stored in chunks, not here
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),  # Already indexed
                ),
            )
            file_id = cur.lastrowid

            # Insert chunks with embeddings
            for chunk in chunks:
                embedding_b64 = chunk.get("embedding")
                embedding_blob = (
                    base64.b64decode(embedding_b64)
                    if embedding_b64
                    else None
                )

                conn.execute(
                    """
                    INSERT INTO library_chunks
                    (library_file_id, chunk_index, content, embedding,
                     start_offset, page)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        file_id,
                        chunk.get("index", 0),
                        chunk.get("content", ""),
                        embedding_blob,
                        chunk.get("start_offset", 0),
                        chunk.get("page"),
                    ),
                )

            conn.commit()

            # Auto-assign collection if specified
            collection_name = source_info.get("collection")
            if collection_name:
                self._assign_collection(file_id, collection_name)

            return {
                "status": "imported",
                "filename": filename,
                "file_id": file_id,
                "chunk_count": len(chunks),
            }

        except Exception as e:
            return {
                "status": "error",
                "filename": file_info.get("filename", "unknown"),
                "error": str(e),
            }

    def _assign_collection(self, file_id: int, collection_name: str) -> None:
        """Assign a file to a collection by name."""
        if collection_name not in self._collection_id_cache:
            conn = get_db()
            row = conn.execute(
                "SELECT id FROM library_collections WHERE name = ?",
                (collection_name,),
            ).fetchone()
            self._collection_id_cache[collection_name] = (
                row["id"] if row else None
            )

        collection_id = self._collection_id_cache.get(collection_name)
        if collection_id:
            self.collections.add_file(collection_id, file_id)

    def _move_to_imported(self, package_path: str) -> None:
        """Move an imported package file to the imported subdirectory."""
        os.makedirs(HARVEST_IMPORTED_DIR, exist_ok=True)
        dest = os.path.join(
            HARVEST_IMPORTED_DIR, os.path.basename(package_path)
        )
        shutil.move(package_path, dest)
