"""
Bulk PDF Importer Plugin

Phase 6.3: Plugin Framework (MVP)

Imports multiple PDF files from a directory into a Tamor project.
Optimized for batch PDF processing with text extraction.
"""

import logging
import os
import shutil
import uuid
from typing import Any, Dict, List

from plugins import ImporterPlugin, ImportItem, ImportResult
from utils.db import get_db
from services.file_parsing import extract_text_from_file

# Flask import (may not be available during testing)
try:
    from flask import current_app
except ImportError:
    current_app = None

logger = logging.getLogger(__name__)


class BulkPDFImporter(ImporterPlugin):
    """
    Import multiple PDFs from a directory.

    Scans a directory for PDF files and imports them into the target
    project, automatically triggering text extraction.
    """

    id = "bulk-pdf"
    name = "Bulk PDF Importer"
    description = "Import multiple PDFs from a directory"

    config_schema = {
        "path": {
            "type": "string",
            "required": True,
            "description": "Directory path containing PDF files",
        },
        "recursive": {
            "type": "boolean",
            "default": True,
            "description": "Scan subdirectories recursively",
        },
        "extract_text": {
            "type": "boolean",
            "default": True,
            "description": "Extract and cache text from PDFs after import",
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
        Discover all PDF files in the specified directory.

        Args:
            config: Plugin configuration with path, recursive

        Returns:
            List of ImportItem objects representing PDFs to import
        """
        path = config.get("path", "")
        recursive = config.get("recursive", True)

        if not os.path.isdir(path):
            logger.warning(f"Path is not a directory: {path}")
            return []

        items = []
        file_id_counter = 0

        if recursive:
            for root, dirs, files in os.walk(path):
                for filename in files:
                    if filename.lower().endswith(".pdf"):
                        file_path = os.path.join(root, filename)
                        item = self._create_import_item(
                            file_path, filename, file_id_counter
                        )
                        if item:
                            items.append(item)
                            file_id_counter += 1
        else:
            for filename in os.listdir(path):
                if filename.lower().endswith(".pdf"):
                    file_path = os.path.join(path, filename)
                    if os.path.isfile(file_path):
                        item = self._create_import_item(
                            file_path, filename, file_id_counter
                        )
                        if item:
                            items.append(item)
                            file_id_counter += 1

        logger.info(f"Found {len(items)} PDF files to import from {path}")
        return items

    def _create_import_item(
        self, file_path: str, filename: str, counter: int
    ) -> ImportItem:
        """Create an ImportItem from a PDF file path."""
        try:
            size = os.path.getsize(file_path)
        except OSError:
            size = None

        return ImportItem(
            id=f"pdf-{counter}",
            name=filename,
            path=file_path,
            mime_type="application/pdf",
            size_bytes=size,
            metadata={"original_path": file_path},
        )

    def import_item(
        self, item: ImportItem, project_id: int, user_id: int
    ) -> ImportResult:
        """
        Import a PDF file and optionally extract its text.

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
                    "application/pdf",
                    size_bytes,
                ),
            )
            file_id = cur.lastrowid
            conn.commit()

            # Extract and cache text
            text_result = None
            page_count = None
            try:
                result = extract_text_from_file(
                    full_path, "application/pdf", item.name
                )
                text = result.get("text", "")
                meta = result.get("meta", {})
                parser = result.get("parser", "")
                page_count = meta.get("page_count")

                # Cache the extracted text
                import json
                meta_json = json.dumps(meta) if meta else None
                cur.execute(
                    """
                    INSERT OR REPLACE INTO file_text_cache
                    (file_id, text, meta_json, parser)
                    VALUES (?, ?, ?, ?)
                    """,
                    (file_id, text, meta_json, parser),
                )
                conn.commit()

                text_result = {
                    "extracted": True,
                    "parser": parser,
                    "text_length": len(text),
                    "page_count": page_count,
                }
            except Exception as e:
                logger.warning(f"Failed to extract text from {item.name}: {e}")
                text_result = {"extracted": False, "error": str(e)}

            logger.info(f"Imported PDF {item.name} as file_id={file_id}")

            return ImportResult(
                success=True,
                file_id=file_id,
                metadata={
                    "source_path": item.path,
                    "stored_name": stored_name_rel,
                    "size_bytes": size_bytes,
                    "page_count": page_count,
                    "text_extraction": text_result,
                },
            )

        except Exception as e:
            logger.error(f"Failed to import PDF {item.name}: {e}")
            return ImportResult(
                success=False,
                error=str(e),
                metadata={"source_path": item.path},
            )
