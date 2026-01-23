"""
JSON Export Plugin

Phase 6.3: Plugin Framework

Exports structured project data as a JSON file including
files, transcripts, insights, and notes.
"""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict

from plugins import ExporterPlugin, ExportResult
from utils.db import get_db

logger = logging.getLogger(__name__)


class JsonExporter(ExporterPlugin):
    """
    Export structured project data as JSON.

    Creates a comprehensive JSON file containing:
    - Project metadata
    - File information with optional extracted text
    - Transcripts with segments
    - Auto-generated insights
    - Project notes
    """

    id = "json-export"
    name = "JSON Export"
    type = "exporter"
    description = "Export structured project data as JSON"

    config_schema = {
        "include_file_text": {
            "type": "boolean",
            "default": True,
            "description": "Include extracted text content",
        },
        "include_insights": {
            "type": "boolean",
            "default": True,
            "description": "Include auto-generated insights",
        },
        "include_transcripts": {
            "type": "boolean",
            "default": True,
            "description": "Include transcripts",
        },
        "include_notes": {
            "type": "boolean",
            "default": True,
            "description": "Include project notes",
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
        Export project data as JSON.

        Args:
            project_id: Source project ID
            user_id: User performing the export
            config: Export configuration options

        Returns:
            ExportResult with path to generated JSON file
        """
        include_file_text = config.get("include_file_text", True)
        include_insights = config.get("include_insights", True)
        include_transcripts = config.get("include_transcripts", True)
        include_notes = config.get("include_notes", True)

        conn = get_db()
        cur = conn.cursor()

        # Verify project access and get project details
        cur.execute(
            """
            SELECT id, name, created_at, notes
            FROM projects
            WHERE id = ? AND user_id = ?
            """,
            (project_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            return ExportResult(
                success=False,
                error="Project not found or access denied",
            )

        project_name = row[1] or f"project-{project_id}"
        project_created_at = row[2]
        project_notes = row[3] if include_notes else None

        # Sanitize project name for filename
        safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in project_name)
        safe_name = safe_name.strip()[:50] or "project"

        # Build export data structure
        export_data = {
            "version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "project": {
                "id": project_id,
                "name": project_name,
                "created_at": project_created_at,
            },
            "files": [],
            "transcripts": [],
        }

        if include_notes and project_notes:
            export_data["project"]["notes"] = project_notes

        # Get project files
        cur.execute(
            """
            SELECT id, filename, mime_type, size_bytes, created_at
            FROM project_files
            WHERE project_id = ? AND deleted_at IS NULL
            ORDER BY created_at
            """,
            (project_id,),
        )
        files = cur.fetchall()

        for file_row in files:
            file_id, filename, mime_type, size_bytes, created_at = file_row

            file_data = {
                "id": file_id,
                "filename": filename,
                "mime_type": mime_type,
                "size_bytes": size_bytes,
                "created_at": created_at,
            }

            # Add extracted text if requested
            if include_file_text:
                cur.execute(
                    "SELECT text FROM file_text_cache WHERE file_id = ?",
                    (file_id,),
                )
                text_row = cur.fetchone()
                if text_row:
                    file_data["text"] = text_row[0]

            # Add insights if requested
            if include_insights:
                cur.execute(
                    """
                    SELECT type, data_json, created_at
                    FROM file_insights
                    WHERE file_id = ?
                    ORDER BY type
                    """,
                    (file_id,),
                )
                insight_rows = cur.fetchall()
                if insight_rows:
                    insights = {}
                    for insight_type, data_json, i_created_at in insight_rows:
                        try:
                            insights[insight_type] = json.loads(data_json) if data_json else None
                        except json.JSONDecodeError:
                            insights[insight_type] = data_json
                    file_data["insights"] = insights

            export_data["files"].append(file_data)

        # Get transcripts if requested
        if include_transcripts:
            cur.execute(
                """
                SELECT id, title, text, segments_json, created_at
                FROM transcripts
                WHERE project_id = ?
                ORDER BY created_at
                """,
                (project_id,),
            )
            transcripts = cur.fetchall()

            for t_row in transcripts:
                t_id, title, text, segments_json, t_created_at = t_row

                transcript_data = {
                    "id": t_id,
                    "title": title,
                    "text": text,
                    "created_at": t_created_at,
                }

                # Parse segments if available
                if segments_json:
                    try:
                        transcript_data["segments"] = json.loads(segments_json)
                    except json.JSONDecodeError:
                        pass

                export_data["transcripts"].append(transcript_data)

        # Create temp directory for export
        export_dir = tempfile.mkdtemp(prefix="tamor_export_")
        export_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        json_filename = f"{safe_name}-export-{export_timestamp}.json"
        json_path = os.path.join(export_dir, json_filename)

        try:
            # Write JSON file
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            # Get file size
            json_size = os.path.getsize(json_path)

            logger.info(
                f"Created JSON export for project {project_id}: "
                f"{len(export_data['files'])} files, "
                f"{len(export_data['transcripts'])} transcripts, "
                f"{json_size} bytes"
            )

            return ExportResult(
                success=True,
                export_path=json_path,
                filename=json_filename,
                mime_type="application/json",
                size_bytes=json_size,
                metadata={
                    "project_name": project_name,
                    "total_files": len(export_data["files"]),
                    "total_transcripts": len(export_data["transcripts"]),
                },
            )

        except Exception as e:
            logger.error(f"Failed to create JSON export: {e}")
            # Clean up on error
            if os.path.exists(json_path):
                os.remove(json_path)
            return ExportResult(
                success=False,
                error=str(e),
            )
