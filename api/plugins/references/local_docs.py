"""
Local Docs Reference Plugin

Phase 6.3: Plugin Framework

Reference files from a local folder without importing them.
Provides read-only indexing and on-demand text extraction.
"""

import logging
import mimetypes
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from plugins import ReferencePlugin, ReferenceItem, ReferenceResult, FetchResult

logger = logging.getLogger(__name__)

# Supported text extraction extensions
TEXT_EXTENSIONS = {".txt", ".md", ".rst", ".py", ".js", ".ts", ".json", ".xml", ".html", ".css"}
BINARY_DOC_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt"}


class LocalDocsReference(ReferencePlugin):
    """
    Reference files from a local folder without importing.

    Key behaviors:
    - Read-only indexing (list files + basic metadata)
    - On-demand text extraction only when fetch_item called
    - Clear provenance: "Referenced, not imported"
    - No files copied to uploads folder
    """

    id = "local-docs"
    name = "Local Docs Folder"
    type = "reference"
    description = "Reference files from a local folder without importing"

    config_schema = {
        "path": {
            "type": "string",
            "required": True,
            "description": "Directory path to reference",
        },
        "recursive": {
            "type": "boolean",
            "default": True,
            "description": "Include subdirectories",
        },
        "extensions": {
            "type": "array",
            "items": "string",
            "default": [".md", ".txt", ".rst", ".pdf", ".docx"],
            "description": "File extensions to include",
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

    def list_items(self, config: Dict) -> ReferenceResult:
        """
        List available files in the specified directory.

        Args:
            config: Plugin configuration with path, recursive, extensions

        Returns:
            ReferenceResult with list of available files
        """
        path = config.get("path", "")
        recursive = config.get("recursive", True)
        extensions = config.get("extensions", [".md", ".txt", ".rst", ".pdf", ".docx"])

        if not os.path.isdir(path):
            return ReferenceResult(
                success=False,
                error=f"Path is not a directory: {path}",
            )

        # Normalize extensions
        normalized_extensions = set()
        for ext in extensions:
            if ext and not ext.startswith("."):
                ext = "." + ext
            if ext:
                normalized_extensions.add(ext.lower())

        items = []
        file_counter = 0

        try:
            if recursive:
                for root, dirs, files in os.walk(path):
                    # Skip hidden directories
                    dirs[:] = [d for d in dirs if not d.startswith(".")]

                    for filename in files:
                        if filename.startswith("."):
                            continue
                        file_path = os.path.join(root, filename)
                        item = self._create_reference_item(
                            file_path, filename, root, path, file_counter, normalized_extensions
                        )
                        if item:
                            items.append(item)
                            file_counter += 1
            else:
                for filename in os.listdir(path):
                    if filename.startswith("."):
                        continue
                    file_path = os.path.join(path, filename)
                    if os.path.isfile(file_path):
                        item = self._create_reference_item(
                            file_path, filename, path, path, file_counter, normalized_extensions
                        )
                        if item:
                            items.append(item)
                            file_counter += 1

            logger.info(f"Found {len(items)} reference files in {path}")

            return ReferenceResult(
                success=True,
                items=items,
                total=len(items),
                metadata={"source_path": path, "recursive": recursive},
            )

        except PermissionError as e:
            logger.error(f"Permission denied accessing {path}: {e}")
            return ReferenceResult(
                success=False,
                error=f"Permission denied: {e}",
            )
        except Exception as e:
            logger.error(f"Error listing files in {path}: {e}")
            return ReferenceResult(
                success=False,
                error=str(e),
            )

    def _create_reference_item(
        self,
        file_path: str,
        filename: str,
        current_dir: str,
        base_path: str,
        counter: int,
        extensions: set,
    ) -> Optional[ReferenceItem]:
        """Create a ReferenceItem from a file path."""
        ext = os.path.splitext(filename)[1].lower()

        # Filter by extension if specified
        if extensions and ext not in extensions:
            return None

        try:
            stat = os.stat(file_path)
            size = stat.st_size
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        except OSError:
            size = None
            mtime = None

        mime_type, _ = mimetypes.guess_type(filename)

        # Calculate relative path from base
        rel_path = os.path.relpath(file_path, base_path)

        # Generate content preview for text files
        preview = None
        if ext in TEXT_EXTENSIONS and size and size < 100000:  # Only for small text files
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    preview = f.read(500)
                    if len(preview) == 500:
                        preview = preview[:497] + "..."
            except Exception:
                pass

        return ReferenceItem(
            id=f"ref-{counter}",
            title=filename,
            path=file_path,
            content_preview=preview,
            mime_type=mime_type,
            size_bytes=size,
            metadata={
                "relative_path": rel_path,
                "extension": ext,
                "modified_at": mtime.isoformat() if mtime else None,
            },
        )

    def fetch_item(self, item_id: str, config: Dict) -> FetchResult:
        """
        Fetch full content of a specific file.

        For text files, returns the full text content.
        For binary files (PDF, DOCX), attempts basic text extraction.

        Args:
            item_id: Identifier of the item to fetch
            config: Plugin configuration

        Returns:
            FetchResult with full content
        """
        # First, list items to find the one with matching ID
        list_result = self.list_items(config)
        if not list_result.success:
            return FetchResult(
                success=False,
                error=list_result.error,
            )

        # Find the item
        item = None
        for ref_item in list_result.items:
            if ref_item.id == item_id:
                item = ref_item
                break

        if not item:
            return FetchResult(
                success=False,
                error=f"Item not found: {item_id}",
            )

        file_path = item.path
        ext = os.path.splitext(file_path)[1].lower()

        try:
            content = None

            # Handle text files
            if ext in TEXT_EXTENSIONS:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

            # Handle PDF files
            elif ext == ".pdf":
                content = self._extract_pdf_text(file_path)

            # Handle DOCX files
            elif ext == ".docx":
                content = self._extract_docx_text(file_path)

            # For other files, just indicate they exist
            else:
                content = f"[Binary file: {item.title}]\nSize: {item.size_bytes} bytes\nType: {item.mime_type}"

            return FetchResult(
                success=True,
                content=content,
                title=item.title,
                url=f"file://{file_path}",
                fetched_at=datetime.now(timezone.utc).isoformat(),
                metadata={
                    "source": "local_docs",
                    "path": file_path,
                    "mime_type": item.mime_type,
                    "size_bytes": item.size_bytes,
                },
            )

        except Exception as e:
            logger.error(f"Error fetching {file_path}: {e}")
            return FetchResult(
                success=False,
                error=str(e),
            )

    def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text from PDF file."""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            doc.close()
            return "\n\n".join(text_parts)
        except ImportError:
            return "[PDF text extraction requires PyMuPDF. Install with: pip install pymupdf]"
        except Exception as e:
            return f"[Error extracting PDF text: {e}]"

    def _extract_docx_text(self, file_path: str) -> str:
        """Extract text from DOCX file."""
        try:
            from docx import Document
            doc = Document(file_path)
            text_parts = []
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text)
            return "\n\n".join(text_parts)
        except ImportError:
            return "[DOCX text extraction requires python-docx. Install with: pip install python-docx]"
        except Exception as e:
            return f"[Error extracting DOCX text: {e}]"
