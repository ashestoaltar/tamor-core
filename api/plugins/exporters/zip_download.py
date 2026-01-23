"""
ZIP Download Exporter Plugin

Phase 6.3: Plugin Framework

Downloads all project files as a ZIP archive with optional
text cache and transcripts.
"""

import json
import logging
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict

from plugins import ExporterPlugin, ExportResult
from utils.db import get_db

# Flask import (may not be available during testing)
try:
    from flask import current_app
except ImportError:
    current_app = None

logger = logging.getLogger(__name__)


class ZipDownloadExporter(ExporterPlugin):
    """
    Download all project files as a ZIP archive.

    Creates a structured ZIP file containing:
    - manifest.json: File list and metadata
    - files/: Original uploaded files
    - transcripts/: Transcript text files (optional)
    - text/: Extracted text files (optional)
    """

    id = "zip-download"
    name = "ZIP Download"
    type = "exporter"
    description = "Download all project files as a ZIP archive"

    config_schema = {
        "include_text_cache": {
            "type": "boolean",
            "default": False,
            "description": "Include extracted text files",
        },
        "include_transcripts": {
            "type": "boolean",
            "default": True,
            "description": "Include transcripts as text files",
        },
    }

    def validate_config(self, config: Dict) -> bool:
        """Validate configuration."""
        # All config options are optional booleans with defaults
        return True

    def export_project(
        self, project_id: int, user_id: int, config: Dict
    ) -> ExportResult:
        """
        Export project as a ZIP archive.

        Args:
            project_id: Source project ID
            user_id: User performing the export
            config: Export configuration options

        Returns:
            ExportResult with path to generated ZIP file
        """
        include_text_cache = config.get("include_text_cache", False)
        include_transcripts = config.get("include_transcripts", True)

        conn = get_db()
        cur = conn.cursor()

        # Verify project access and get project name
        cur.execute(
            "SELECT id, name FROM projects WHERE id = ? AND user_id = ?",
            (project_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            return ExportResult(
                success=False,
                error="Project not found or access denied",
            )

        project_name = row[1] or f"project-{project_id}"
        # Sanitize project name for filesystem
        safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in project_name)
        safe_name = safe_name.strip()[:50] or "project"

        # Get upload root
        upload_root = self._get_upload_root()

        # Get project files
        cur.execute(
            """
            SELECT id, filename, stored_name, mime_type, size_bytes, created_at
            FROM project_files
            WHERE project_id = ? AND deleted_at IS NULL
            ORDER BY created_at
            """,
            (project_id,),
        )
        files = cur.fetchall()

        # Get transcripts if requested
        transcripts = []
        if include_transcripts:
            cur.execute(
                """
                SELECT id, title, text, created_at
                FROM transcripts
                WHERE project_id = ?
                ORDER BY created_at
                """,
                (project_id,),
            )
            transcripts = cur.fetchall()

        # Create temp directory for export
        export_dir = tempfile.mkdtemp(prefix="tamor_export_")
        export_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        zip_filename = f"{safe_name}-export-{export_timestamp}.zip"
        zip_path = os.path.join(export_dir, zip_filename)

        try:
            # Build manifest
            manifest = {
                "project_id": project_id,
                "project_name": project_name,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "files": [],
                "transcripts": [],
                "total_files": 0,
                "total_size_bytes": 0,
            }

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                archive_root = f"{safe_name}-export"

                # Add files
                for file_row in files:
                    file_id, filename, stored_name, mime_type, size_bytes, created_at = file_row

                    # Add to manifest
                    file_info = {
                        "id": file_id,
                        "filename": filename,
                        "mime_type": mime_type,
                        "size_bytes": size_bytes,
                        "created_at": created_at,
                    }
                    manifest["files"].append(file_info)
                    manifest["total_files"] += 1
                    manifest["total_size_bytes"] += size_bytes or 0

                    # Add actual file to ZIP
                    if stored_name:
                        source_path = os.path.join(upload_root, stored_name)
                        if os.path.exists(source_path):
                            archive_path = f"{archive_root}/files/{filename}"
                            zf.write(source_path, archive_path)

                    # Add text cache if requested
                    if include_text_cache:
                        cur.execute(
                            "SELECT text FROM file_text_cache WHERE file_id = ?",
                            (file_id,),
                        )
                        text_row = cur.fetchone()
                        if text_row and text_row[0]:
                            text_filename = f"{filename}.txt"
                            archive_path = f"{archive_root}/text/{text_filename}"
                            zf.writestr(archive_path, text_row[0])

                # Add transcripts
                if include_transcripts:
                    for transcript_row in transcripts:
                        t_id, title, text, created_at = transcript_row

                        # Add to manifest
                        transcript_info = {
                            "id": t_id,
                            "title": title,
                            "created_at": created_at,
                        }
                        manifest["transcripts"].append(transcript_info)

                        # Add transcript text file to ZIP
                        if text:
                            safe_title = "".join(
                                c if c.isalnum() or c in "-_ " else "_"
                                for c in (title or f"transcript-{t_id}")
                            )[:50]
                            text_filename = f"{safe_title}.txt"
                            archive_path = f"{archive_root}/transcripts/{text_filename}"
                            zf.writestr(archive_path, text)

                # Add manifest
                manifest_json = json.dumps(manifest, indent=2)
                zf.writestr(f"{archive_root}/manifest.json", manifest_json)

            # Get final ZIP size
            zip_size = os.path.getsize(zip_path)

            logger.info(
                f"Created ZIP export for project {project_id}: "
                f"{manifest['total_files']} files, {zip_size} bytes"
            )

            return ExportResult(
                success=True,
                export_path=zip_path,
                filename=zip_filename,
                mime_type="application/zip",
                size_bytes=zip_size,
                metadata={
                    "project_name": project_name,
                    "total_files": manifest["total_files"],
                    "total_transcripts": len(manifest["transcripts"]),
                    "original_size_bytes": manifest["total_size_bytes"],
                },
            )

        except Exception as e:
            logger.error(f"Failed to create ZIP export: {e}")
            # Clean up on error
            if os.path.exists(zip_path):
                os.remove(zip_path)
            return ExportResult(
                success=False,
                error=str(e),
            )

    def _get_upload_root(self) -> str:
        """Get the upload root directory."""
        if current_app:
            upload_root = current_app.config.get("UPLOAD_ROOT")
            if not upload_root:
                upload_root = os.path.join(current_app.root_path, "uploads")
        else:
            upload_root = os.environ.get(
                "TAMOR_UPLOAD_ROOT",
                os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    "uploads",
                ),
            )
        return upload_root
