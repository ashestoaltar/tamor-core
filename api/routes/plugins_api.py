"""
Plugin API Endpoints

Phase 6.3: Plugin Framework (MVP)

Provides REST API endpoints for managing plugins:
- List available plugins
- Get plugin details and config schema
- List items available for import
- Execute imports
- Manage project plugin configurations
"""

import json
import logging
import mimetypes
import os
import tempfile
import uuid
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from plugins import ImportItem

from plugins.registry import REGISTRY, load_all_plugins
from utils.auth import ensure_user
from utils.db import get_db

logger = logging.getLogger(__name__)

plugins_bp = Blueprint("plugins_api", __name__, url_prefix="/api")

# Load plugins on module import
load_all_plugins()


# ---------------------------------------------------------------------------
# Plugin Discovery
# ---------------------------------------------------------------------------


@plugins_bp.get("/plugins")
def list_plugins():
    """
    List all registered plugins.

    Returns:
        {
            "plugins": [
                {
                    "id": "local-folder",
                    "name": "Local Folder Importer",
                    "type": "importer",
                    "description": "...",
                    "config_schema": {...}
                },
                ...
            ]
        }
    """
    user_id, err = ensure_user()
    if err:
        return err

    plugins = REGISTRY.list_importers()
    return jsonify({"plugins": plugins})


@plugins_bp.get("/plugins/<plugin_id>")
def get_plugin(plugin_id: str):
    """
    Get details for a specific plugin.

    Returns plugin info including config schema.
    """
    user_id, err = ensure_user()
    if err:
        return err

    plugin = REGISTRY.get(plugin_id)
    if not plugin:
        return jsonify({"error": "plugin_not_found"}), 404

    return jsonify(plugin.get_info())


# ---------------------------------------------------------------------------
# Plugin Operations
# ---------------------------------------------------------------------------


@plugins_bp.post("/plugins/<plugin_id>/list")
def list_plugin_items(plugin_id: str):
    """
    List available items from a plugin.

    Request JSON:
        {
            "config": {
                "path": "/path/to/folder",
                "recursive": true,
                ...
            }
        }

    Returns:
        {
            "items": [
                {
                    "id": "file-0",
                    "name": "example.pdf",
                    "path": "/path/to/example.pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": 12345,
                    "metadata": {...}
                },
                ...
            ],
            "total": 42
        }
    """
    user_id, err = ensure_user()
    if err:
        return err

    plugin = REGISTRY.get(plugin_id)
    if not plugin:
        return jsonify({"error": "plugin_not_found"}), 404

    body = request.json or {}
    config = body.get("config", {})

    # Validate config
    if not plugin.validate_config(config):
        return jsonify({
            "error": "invalid_config",
            "details": "Configuration validation failed. Check path exists and is accessible.",
        }), 400

    try:
        items = plugin.list_items(config)

        # Convert ImportItem dataclasses to dicts
        items_data = []
        for item in items:
            items_data.append({
                "id": item.id,
                "name": item.name,
                "path": item.path,
                "mime_type": item.mime_type,
                "size_bytes": item.size_bytes,
                "metadata": item.metadata or {},
            })

        return jsonify({
            "items": items_data,
            "total": len(items_data),
        })

    except Exception as e:
        logger.error(f"Error listing items for plugin {plugin_id}: {e}")
        return jsonify({
            "error": "list_failed",
            "details": str(e),
        }), 500


@plugins_bp.post("/plugins/<plugin_id>/import")
def import_plugin_items(plugin_id: str):
    """
    Import items using a plugin.

    Request JSON:
        {
            "project_id": 1,
            "config": {...},
            "item_ids": ["file-0", "file-1"]  // optional, import all if not specified
        }

    Returns:
        {
            "results": [
                {
                    "item_id": "file-0",
                    "success": true,
                    "file_id": 123,
                    "metadata": {...}
                },
                ...
            ],
            "summary": {
                "total": 10,
                "succeeded": 8,
                "failed": 2
            }
        }
    """
    user_id, err = ensure_user()
    if err:
        return err

    plugin = REGISTRY.get(plugin_id)
    if not plugin:
        return jsonify({"error": "plugin_not_found"}), 404

    body = request.json or {}
    project_id = body.get("project_id")
    config = body.get("config", {})
    item_ids = body.get("item_ids")  # Optional filter

    if not project_id:
        return jsonify({"error": "missing_project_id"}), 400

    # Verify project access
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "project_not_found"}), 404

    # Validate config
    if not plugin.validate_config(config):
        return jsonify({
            "error": "invalid_config",
            "details": "Configuration validation failed.",
        }), 400

    try:
        # List items
        all_items = plugin.list_items(config)

        # Filter to selected items if specified
        if item_ids:
            item_ids_set = set(item_ids)
            items_to_import = [i for i in all_items if i.id in item_ids_set]
        else:
            items_to_import = all_items

        if not items_to_import:
            return jsonify({
                "results": [],
                "summary": {"total": 0, "succeeded": 0, "failed": 0},
            })

        # Import each item
        results = []
        succeeded = 0
        failed = 0

        for item in items_to_import:
            result = plugin.import_item(item, project_id, user_id)

            result_data = {
                "item_id": item.id,
                "item_name": item.name,
                "success": result.success,
                "file_id": result.file_id,
                "error": result.error,
                "metadata": result.metadata or {},
            }
            results.append(result_data)

            if result.success:
                succeeded += 1

                # Record import in plugin_imports table
                try:
                    cur.execute(
                        """
                        INSERT INTO plugin_imports
                        (project_id, plugin_id, file_id, source_path, metadata_json)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            project_id,
                            plugin_id,
                            result.file_id,
                            item.path,
                            json.dumps(result.metadata) if result.metadata else None,
                        ),
                    )
                    conn.commit()
                except Exception as e:
                    logger.warning(f"Failed to record import: {e}")
            else:
                failed += 1

        return jsonify({
            "results": results,
            "summary": {
                "total": len(items_to_import),
                "succeeded": succeeded,
                "failed": failed,
            },
        })

    except Exception as e:
        logger.error(f"Error importing with plugin {plugin_id}: {e}")
        return jsonify({
            "error": "import_failed",
            "details": str(e),
        }), 500


# ---------------------------------------------------------------------------
# Upload and Import (Client-side files)
# ---------------------------------------------------------------------------


@plugins_bp.post("/plugins/<plugin_id>/upload-import")
def upload_and_import(plugin_id: str):
    """
    Upload files from client device and import them using a plugin.

    This endpoint accepts multipart form data with files uploaded from
    the user's device (phone, tablet, PC) and processes them through
    the specified plugin.

    Form data:
        project_id: Target project ID
        files: One or more files to upload and import

    Returns:
        {
            "results": [...],
            "summary": {"total": N, "succeeded": N, "failed": N}
        }
    """
    user_id, err = ensure_user()
    if err:
        return err

    plugin = REGISTRY.get(plugin_id)
    if not plugin:
        return jsonify({"error": "plugin_not_found"}), 404

    # Get project_id from form data
    project_id = request.form.get("project_id")
    if not project_id:
        return jsonify({"error": "missing_project_id"}), 400

    try:
        project_id = int(project_id)
    except ValueError:
        return jsonify({"error": "invalid_project_id"}), 400

    # Verify project access
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "project_not_found"}), 404

    # Get uploaded files
    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "no_files_uploaded"}), 400

    results = []
    succeeded = 0
    failed = 0

    # Create temp directory for uploaded files
    with tempfile.TemporaryDirectory() as temp_dir:
        for idx, uploaded_file in enumerate(files):
            if not uploaded_file or uploaded_file.filename == "":
                continue

            # Save to temp location
            filename = uploaded_file.filename
            temp_path = os.path.join(temp_dir, f"{uuid.uuid4().hex}_{filename}")
            uploaded_file.save(temp_path)

            # Get file info
            try:
                size_bytes = os.path.getsize(temp_path)
            except OSError:
                size_bytes = None

            mime_type = uploaded_file.mimetype or mimetypes.guess_type(filename)[0]

            # Create ImportItem
            item = ImportItem(
                id=f"upload-{idx}",
                name=filename,
                path=temp_path,
                mime_type=mime_type,
                size_bytes=size_bytes,
                metadata={"source": "client_upload", "original_filename": filename},
            )

            # Import using plugin
            result = plugin.import_item(item, project_id, user_id)

            result_data = {
                "item_id": item.id,
                "item_name": item.name,
                "success": result.success,
                "file_id": result.file_id,
                "error": result.error,
                "metadata": result.metadata or {},
            }
            results.append(result_data)

            if result.success:
                succeeded += 1

                # Record import in plugin_imports table
                try:
                    cur.execute(
                        """
                        INSERT INTO plugin_imports
                        (project_id, plugin_id, file_id, source_path, metadata_json)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            project_id,
                            plugin_id,
                            result.file_id,
                            f"upload://{filename}",
                            json.dumps(result.metadata) if result.metadata else None,
                        ),
                    )
                    conn.commit()
                except Exception as e:
                    logger.warning(f"Failed to record upload import: {e}")
            else:
                failed += 1

    return jsonify({
        "results": results,
        "summary": {
            "total": len(results),
            "succeeded": succeeded,
            "failed": failed,
        },
    })


# ---------------------------------------------------------------------------
# Project Plugin Configuration
# ---------------------------------------------------------------------------


@plugins_bp.get("/projects/<int:project_id>/plugins")
def list_project_plugins(project_id: int):
    """
    List plugins enabled for a project.

    Returns configured plugins with their settings.
    """
    user_id, err = ensure_user()
    if err:
        return err

    # Verify project access
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "project_not_found"}), 404

    # Get configured plugins
    cur.execute(
        """
        SELECT plugin_id, enabled, config_json, created_at
        FROM project_plugins
        WHERE project_id = ?
        """,
        (project_id,),
    )
    rows = cur.fetchall()

    plugins = []
    for row in rows:
        config = None
        if row[2]:
            try:
                config = json.loads(row[2])
            except json.JSONDecodeError:
                config = {}

        # Get plugin info if still registered
        plugin = REGISTRY.get(row[0])
        plugin_info = plugin.get_info() if plugin else {"id": row[0], "name": row[0]}

        plugins.append({
            "plugin_id": row[0],
            "enabled": bool(row[1]),
            "config": config,
            "created_at": row[3],
            "plugin_info": plugin_info,
        })

    return jsonify({"plugins": plugins})


@plugins_bp.put("/projects/<int:project_id>/plugins/<plugin_id>")
def configure_project_plugin(project_id: int, plugin_id: str):
    """
    Enable or configure a plugin for a project.

    Request JSON:
        {
            "enabled": true,
            "config": {
                "path": "/default/path",
                ...
            }
        }
    """
    user_id, err = ensure_user()
    if err:
        return err

    # Verify project access
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "project_not_found"}), 404

    # Verify plugin exists
    plugin = REGISTRY.get(plugin_id)
    if not plugin:
        return jsonify({"error": "plugin_not_found"}), 404

    body = request.json or {}
    enabled = body.get("enabled", True)
    config = body.get("config", {})
    config_json = json.dumps(config) if config else None

    # Upsert configuration
    cur.execute(
        """
        INSERT INTO project_plugins (project_id, plugin_id, enabled, config_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(project_id, plugin_id)
        DO UPDATE SET enabled = excluded.enabled, config_json = excluded.config_json
        """,
        (project_id, plugin_id, 1 if enabled else 0, config_json),
    )
    conn.commit()

    return jsonify({
        "success": True,
        "plugin_id": plugin_id,
        "enabled": enabled,
        "config": config,
    })


@plugins_bp.delete("/projects/<int:project_id>/plugins/<plugin_id>")
def disable_project_plugin(project_id: int, plugin_id: str):
    """
    Disable/remove a plugin configuration from a project.
    """
    user_id, err = ensure_user()
    if err:
        return err

    # Verify project access
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "project_not_found"}), 404

    # Delete configuration
    cur.execute(
        "DELETE FROM project_plugins WHERE project_id = ? AND plugin_id = ?",
        (project_id, plugin_id),
    )
    conn.commit()

    return jsonify({"success": True, "deleted": cur.rowcount > 0})


# ---------------------------------------------------------------------------
# Import History
# ---------------------------------------------------------------------------


@plugins_bp.get("/projects/<int:project_id>/plugin-imports")
def list_project_imports(project_id: int):
    """
    List import history for a project.

    Query params:
        plugin_id: Filter by plugin
        limit: Max results (default 100)
    """
    user_id, err = ensure_user()
    if err:
        return err

    # Verify project access
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "project_not_found"}), 404

    plugin_filter = request.args.get("plugin_id")
    limit = min(int(request.args.get("limit", 100)), 500)

    query = """
        SELECT pi.id, pi.plugin_id, pi.file_id, pi.source_path,
               pi.imported_at, pi.metadata_json, pf.filename
        FROM plugin_imports pi
        LEFT JOIN project_files pf ON pi.file_id = pf.id
        WHERE pi.project_id = ?
    """
    params = [project_id]

    if plugin_filter:
        query += " AND pi.plugin_id = ?"
        params.append(plugin_filter)

    query += " ORDER BY pi.imported_at DESC LIMIT ?"
    params.append(limit)

    cur.execute(query, params)
    rows = cur.fetchall()

    imports = []
    for row in rows:
        metadata = None
        if row[5]:
            try:
                metadata = json.loads(row[5])
            except json.JSONDecodeError:
                metadata = {}

        imports.append({
            "id": row[0],
            "plugin_id": row[1],
            "file_id": row[2],
            "source_path": row[3],
            "imported_at": row[4],
            "metadata": metadata,
            "filename": row[6],
        })

    return jsonify({"imports": imports, "total": len(imports)})
