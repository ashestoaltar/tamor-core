"""
Local Folder Importer Plugin

Phase 6.3: Plugin Framework (MVP)

Imports all files from a local directory into a Tamor project.
Supports recursive scanning and extension filtering.
"""

import logging
import mimetypes
import os
import shutil
import uuid
from typing import Any, Dict, List

from plugins import ImporterPlugin, ImportItem, ImportResult
from utils.db import get_db

# Flask import (may not be available during testing)
try:
    from flask import current_app
except ImportError:
    current_app = None

logger = logging.getLogger(__name__)


class LocalFolderImporter(ImporterPlugin):
    """
    Import files from a local directory.

    Scans a specified directory and imports all matching files
    into the target Tamor project.
    """

    id = "local-folder"
    name = "Local Folder Importer"
    description = "Import all files from a local directory"

    config_schema = {
        "path": {
            "type": "string",
            "required": True,
            "description": "Directory path to import from",
        },
        "recursive": {
            "type": "boolean",
            "default": False,
            "description": "Scan subdirectories recursively",
        },
        "extensions": {
            "type": "array",
            "items": "string",
            "default": [],
            "description": "File extensions to include (empty = all files)",
        },
    }

    def validate_config(self, config: Dict) -> bool:
        """Validate configuration."""
        path = config.get("path")
        if not path:
            return False
        if not os.path.isdir(path):
            return False
        return True

    def list_items(self, config: Dict) -> List[ImportItem]:
        """
        Discover all importable files in the specified directory.

        Args:
            config: Plugin configuration with path, recursive, extensions

        Returns:
            List of ImportItem objects representing files to import
        """
        path = config.get("path", "")
        recursive = config.get("recursive", False)
        extensions = config.get("extensions", [])

        if not os.path.isdir(path):
            logger.warning(f"Path is not a directory: {path}")
            return []

        # Normalize extensions (ensure they start with .)
        normalized_extensions = []
        for ext in extensions:
            if ext and not ext.startswith("."):
                ext = "." + ext
            if ext:
                normalized_extensions.append(ext.lower())

        items = []
        file_id_counter = 0

        if recursive:
            for root, dirs, files in os.walk(path):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    item = self._create_import_item(
                        file_path, filename, file_id_counter, normalized_extensions
                    )
                    if item:
                        items.append(item)
                        file_id_counter += 1
        else:
            for filename in os.listdir(path):
                file_path = os.path.join(path, filename)
                if os.path.isfile(file_path):
                    item = self._create_import_item(
                        file_path, filename, file_id_counter, normalized_extensions
                    )
                    if item:
                        items.append(item)
                        file_id_counter += 1

        logger.info(f"Found {len(items)} files to import from {path}")
        return items

    def _create_import_item(
        self, file_path: str, filename: str, counter: int, extensions: List[str]
    ) -> ImportItem:
        """Create an ImportItem from a file path, applying extension filter."""
        ext = os.path.splitext(filename)[1].lower()

        # Filter by extension if specified
        if extensions and ext not in extensions:
            return None

        try:
            size = os.path.getsize(file_path)
        except OSError:
            size = None

        mime_type, _ = mimetypes.guess_type(filename)

        return ImportItem(
            id=f"file-{counter}",
            name=filename,
            path=file_path,
            mime_type=mime_type,
            size_bytes=size,
            metadata={"original_path": file_path},
        )

    def import_item(
        self, item: ImportItem, project_id: int, user_id: int
    ) -> ImportResult:
        """
        Import a single file into the project.

        Args:
            item: The ImportItem to import
            project_id: Target project ID
            user_id: User performing the import

        Returns:
            ImportResult with success status and file_id
        """
        try:
            # Get upload root from app config or environment
            upload_root = None
            if current_app:
                upload_root = current_app.config.get("UPLOAD_ROOT")
                if not upload_root:
                    upload_root = os.path.join(current_app.root_path, "uploads")
            else:
                # Fallback: use environment or default path
                upload_root = os.environ.get(
                    "TAMOR_UPLOAD_ROOT",
                    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
                )
            os.makedirs(upload_root, exist_ok=True)

            # Create project directory
            project_dir = os.path.join(upload_root, str(project_id))
            os.makedirs(project_dir, exist_ok=True)

            # Generate unique stored name
            stored_name = f"{uuid.uuid4().hex}_{item.name}"
            stored_name_rel = os.path.join(str(project_id), stored_name)
            full_path = os.path.join(upload_root, stored_name_rel)

            # Copy file to uploads directory
            shutil.copy2(item.path, full_path)

            # Get actual file size
            try:
                size_bytes = os.path.getsize(full_path)
            except OSError:
                size_bytes = item.size_bytes

            # Insert into database
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO project_files
                (project_id, user_id, filename, stored_name, mime_type, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    user_id,
                    item.name,
                    stored_name_rel,
                    item.mime_type or "",
                    size_bytes,
                ),
            )
            file_id = cur.lastrowid
            conn.commit()

            logger.info(f"Imported file {item.name} as file_id={file_id}")

            return ImportResult(
                success=True,
                file_id=file_id,
                metadata={
                    "source_path": item.path,
                    "stored_name": stored_name_rel,
                    "size_bytes": size_bytes,
                },
            )

        except Exception as e:
            logger.error(f"Failed to import {item.name}: {e}")
            return ImportResult(
                success=False,
                error=str(e),
                metadata={"source_path": item.path},
            )
