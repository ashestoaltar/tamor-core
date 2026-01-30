"""
Markdown Export Plugin

Phase 6.4: Plugin Framework Expansion

Exports project conversations and notes as formatted markdown files.
"""

import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from plugins import ExporterPlugin, ExportResult
from utils.db import get_db

logger = logging.getLogger(__name__)


class MarkdownExporter(ExporterPlugin):
    """
    Export project data as formatted Markdown.

    Creates a comprehensive markdown file containing:
    - Project metadata
    - Project notes
    - All conversations with messages
    - GHM/Profile status if applicable
    """

    id = "markdown-export"
    name = "Markdown Export"
    type = "exporter"
    description = "Export project conversations and notes as formatted markdown"

    config_schema = {
        "include_system_messages": {
            "type": "boolean",
            "default": False,
            "description": "Include system messages in export",
        },
        "include_metadata": {
            "type": "boolean",
            "default": True,
            "description": "Include timestamps and message counts",
        },
        "include_notes": {
            "type": "boolean",
            "default": True,
            "description": "Include project notes section",
        },
        "single_file": {
            "type": "boolean",
            "default": True,
            "description": "Export as single file (vs one per conversation)",
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
        Export project data as Markdown.

        Args:
            project_id: Source project ID
            user_id: User performing the export
            config: Export configuration options

        Returns:
            ExportResult with path to generated markdown file
        """
        include_system = config.get("include_system_messages", False)
        include_metadata = config.get("include_metadata", True)
        include_notes = config.get("include_notes", True)

        conn = get_db()
        cur = conn.cursor()

        # Get project details
        cur.execute(
            """
            SELECT id, name, created_at, notes, hermeneutic_mode, profile
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

        project = {
            "id": row[0],
            "name": row[1] or f"Project {row[0]}",
            "created_at": row[2],
            "notes": row[3],
            "hermeneutic_mode": row[4],
            "profile": row[5],
        }

        # Get conversations
        cur.execute(
            """
            SELECT id, title, created_at
            FROM conversations
            WHERE project_id = ?
            ORDER BY created_at
            """,
            (project_id,),
        )
        conversations = [
            {"id": r[0], "title": r[1], "created_at": r[2]}
            for r in cur.fetchall()
        ]

        # Get messages for each conversation
        messages_by_conv: Dict[int, List[Dict]] = {}
        for conv in conversations:
            cur.execute(
                """
                SELECT role, content, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at
                """,
                (conv["id"],),
            )
            messages_by_conv[conv["id"]] = [
                {"role": r[0], "content": r[1], "created_at": r[2]}
                for r in cur.fetchall()
            ]

        # Build markdown content
        lines = []

        # Project header
        lines.append(f"# {project['name']}")
        lines.append("")

        if include_metadata:
            lines.append(f"**Exported:** {datetime.now(timezone.utc).isoformat()}")
            lines.append(f"**Conversations:** {len(conversations)}")

            # GHM status
            if project.get("hermeneutic_mode") == "ghm":
                profile = project.get("profile") or "None"
                lines.append(f"**Hermeneutic Mode:** GHM (Profile: {profile})")

            lines.append("")

        lines.append("---")
        lines.append("")

        # Notes section
        if include_notes and project.get("notes"):
            lines.append("## Project Notes")
            lines.append("")
            lines.append(project["notes"])
            lines.append("")
            lines.append("---")
            lines.append("")

        # Conversations
        if conversations:
            lines.append("## Conversations")
            lines.append("")

            for conv in conversations:
                conv_id = conv["id"]
                conv_title = conv.get("title") or "Untitled Conversation"
                conv_messages = messages_by_conv.get(conv_id, [])

                # Conversation header
                lines.append(f"### {conv_title}")
                lines.append("")

                if include_metadata:
                    lines.append(f"**Created:** {conv.get('created_at', '')}")
                    lines.append(f"**Messages:** {len(conv_messages)}")
                    lines.append("")

                # Messages
                for msg in conv_messages:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")

                    # Skip system messages unless requested
                    if role == "system" and not include_system:
                        continue

                    # Format role
                    if role == "user":
                        lines.append("**User:**")
                    elif role == "assistant":
                        lines.append("**Tamor:**")
                    else:
                        lines.append(f"**{role.title()}:**")

                    lines.append("")
                    lines.append(content)
                    lines.append("")

                lines.append("---")
                lines.append("")
        else:
            lines.append("*No conversations in this project.*")
            lines.append("")

        # Join all lines
        markdown_content = "\n".join(lines)

        # Create temp file
        export_dir = tempfile.mkdtemp(prefix="tamor_export_")
        safe_name = "".join(
            c if c.isalnum() or c in "-_ " else "_"
            for c in project["name"]
        )
        safe_name = safe_name.strip()[:50] or "project"
        export_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        md_filename = f"{safe_name}-export-{export_timestamp}.md"
        md_path = os.path.join(export_dir, md_filename)

        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            md_size = os.path.getsize(md_path)

            total_messages = sum(len(m) for m in messages_by_conv.values())
            logger.info(
                f"Created Markdown export for project {project_id}: "
                f"{len(conversations)} conversations, "
                f"{total_messages} messages, "
                f"{md_size} bytes"
            )

            return ExportResult(
                success=True,
                export_path=md_path,
                filename=md_filename,
                mime_type="text/markdown",
                size_bytes=md_size,
                metadata={
                    "project_name": project["name"],
                    "total_conversations": len(conversations),
                    "total_messages": total_messages,
                },
            )

        except Exception as e:
            logger.error(f"Failed to create Markdown export: {e}")
            if os.path.exists(md_path):
                os.remove(md_path)
            return ExportResult(
                success=False,
                error=str(e),
            )
