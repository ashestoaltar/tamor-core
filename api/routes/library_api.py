# api/routes/library_api.py

"""
Library API endpoints.

Provides REST API for managing the global library and project references.
"""

from flask import Blueprint, jsonify, request

from services.library import (
    LibraryChunkService,
    LibraryIndexQueueService,
    LibraryIngestService,
    LibraryReferenceService,
    LibraryScannerService,
    LibraryService,
    LibraryTextService,
    ScannedFile,
)
from utils.auth import ensure_user
from utils.db import get_db

library_bp = Blueprint("library", __name__)

# Services
library_service = LibraryService()
reference_service = LibraryReferenceService()
text_service = LibraryTextService()
chunk_service = LibraryChunkService()
scanner_service = LibraryScannerService()
ingest_service = LibraryIngestService()
index_queue_service = LibraryIndexQueueService()


# =============================================================================
# LIBRARY FILES
# =============================================================================


@library_bp.get("/api/library")
def list_library_files():
    """
    List files in the library.

    Query params:
        limit: Max results (default 100)
        offset: Pagination offset
        mime_type: Filter by mime type prefix
        source_type: Filter by source type (manual|scan|transcription)
        search: Search filename and metadata
    """
    user_id, err = ensure_user()
    if err:
        return err

    limit = min(int(request.args.get("limit", 100)), 500)
    offset = int(request.args.get("offset", 0))
    mime_type = request.args.get("mime_type")
    source_type = request.args.get("source_type")
    search = request.args.get("search")

    result = library_service.list_files(
        limit=limit,
        offset=offset,
        mime_type=mime_type,
        source_type=source_type,
        search=search,
    )

    return jsonify(result)


@library_bp.get("/api/library/<int:file_id>")
def get_library_file(file_id: int):
    """Get details for a library file."""
    user_id, err = ensure_user()
    if err:
        return err

    file = library_service.get_file(file_id)
    if not file:
        return jsonify({"error": "not_found"}), 404

    # Include reference count
    file["reference_count"] = reference_service.get_reference_count(file_id)

    return jsonify({"file": file})


@library_bp.post("/api/library")
def add_to_library():
    """
    Add a file to the library.

    Body:
        file_path: Absolute path to file (must be accessible)
        metadata: Optional metadata dict (tags, title, author, etc.)
    """
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}
    file_path = data.get("file_path")
    metadata = data.get("metadata")

    if not file_path:
        return jsonify({"error": "file_path required"}), 400

    try:
        result = library_service.add_file(
            file_path=file_path, source_type="manual", metadata=metadata
        )
        return jsonify(result), 201 if result["status"] == "created" else 200
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@library_bp.patch("/api/library/<int:file_id>")
def update_library_file(file_id: int):
    """
    Update metadata for a library file.

    Body:
        metadata: Dict of metadata to merge
        tags: List of tags (shorthand for metadata.tags)
    """
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}

    file = library_service.get_file(file_id)
    if not file:
        return jsonify({"error": "not_found"}), 404

    if "tags" in data:
        library_service.set_tags(file_id, data["tags"])

    if "metadata" in data:
        library_service.update_metadata(file_id, data["metadata"])

    return jsonify({"file": library_service.get_file(file_id)})


@library_bp.delete("/api/library/<int:file_id>")
def delete_library_file(file_id: int):
    """
    Remove a file from the library.

    Query params:
        delete_disk: If 'true', also delete from filesystem
    """
    user_id, err = ensure_user()
    if err:
        return err

    file = library_service.get_file(file_id)
    if not file:
        return jsonify({"error": "not_found"}), 404

    # Check for references
    refs = reference_service.get_file_references(file_id)
    if refs:
        return (
            jsonify(
                {
                    "error": "file_referenced",
                    "message": f"File is referenced by {len(refs)} project(s)",
                    "projects": [r["project_name"] for r in refs],
                }
            ),
            409,
        )

    delete_disk = request.args.get("delete_disk", "").lower() == "true"

    library_service.delete_file(file_id, delete_from_disk=delete_disk)

    return jsonify({"deleted": True})


@library_bp.get("/api/library/<int:file_id>/text")
def get_library_file_text(file_id: int):
    """Get extracted text for a library file."""
    user_id, err = ensure_user()
    if err:
        return err

    file = library_service.get_file(file_id)
    if not file:
        return jsonify({"error": "not_found"}), 404

    text, meta = text_service.get_text(file_id)

    return jsonify(
        {
            "file_id": file_id,
            "text": text,
            "meta": meta,
            "parseable": text_service.is_parseable(file_id),
        }
    )


@library_bp.post("/api/library/<int:file_id>/index")
def index_library_file(file_id: int):
    """
    Index a library file (generate chunks and embeddings).

    Query params:
        force: If 'true', regenerate even if already indexed
    """
    user_id, err = ensure_user()
    if err:
        return err

    file = library_service.get_file(file_id)
    if not file:
        return jsonify({"error": "not_found"}), 404

    force = request.args.get("force", "").lower() == "true"

    if force:
        chunks = chunk_service.reindex_file(file_id)
    else:
        chunks = chunk_service.get_chunks(file_id)

    return jsonify({"file_id": file_id, "chunk_count": len(chunks), "indexed": True})


@library_bp.get("/api/library/stats")
def get_library_stats():
    """Get library statistics."""
    user_id, err = ensure_user()
    if err:
        return err

    return jsonify(library_service.get_stats())


# =============================================================================
# PROJECT REFERENCES
# =============================================================================


@library_bp.get("/api/projects/<int:project_id>/library")
def get_project_library_refs(project_id: int):
    """Get all library files referenced by a project."""
    user_id, err = ensure_user()
    if err:
        return err

    # Verify project access
    conn = get_db()
    cur = conn.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    refs = reference_service.get_project_references(project_id)

    return jsonify({"references": refs})


@library_bp.post("/api/projects/<int:project_id>/library")
def add_project_library_ref(project_id: int):
    """
    Add a library file reference to a project.

    Body:
        library_file_id: ID of library file to reference
        notes: Optional notes about relevance
    """
    user_id, err = ensure_user()
    if err:
        return err

    # Verify project access
    conn = get_db()
    cur = conn.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "project_not_found"}), 404

    data = request.json or {}
    library_file_id = data.get("library_file_id")
    notes = data.get("notes")

    if not library_file_id:
        return jsonify({"error": "library_file_id required"}), 400

    # Verify library file exists
    if not library_service.get_file(library_file_id):
        return jsonify({"error": "library_file_not_found"}), 404

    result = reference_service.add_reference(
        project_id=project_id,
        library_file_id=library_file_id,
        user_id=user_id,
        notes=notes,
    )

    return jsonify(result), 201 if result["status"] == "created" else 200


@library_bp.delete("/api/projects/<int:project_id>/library/<int:library_file_id>")
def remove_project_library_ref(project_id: int, library_file_id: int):
    """Remove a library file reference from a project."""
    user_id, err = ensure_user()
    if err:
        return err

    # Verify project access
    conn = get_db()
    cur = conn.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    removed = reference_service.remove_reference(project_id, library_file_id)

    return jsonify({"removed": removed})


@library_bp.post("/api/projects/<int:project_id>/library/bulk")
def bulk_add_library_refs(project_id: int):
    """
    Add multiple library files to a project.

    Body:
        library_file_ids: List of library file IDs
    """
    user_id, err = ensure_user()
    if err:
        return err

    # Verify project access
    conn = get_db()
    cur = conn.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    data = request.json or {}
    library_file_ids = data.get("library_file_ids", [])

    if not library_file_ids:
        return jsonify({"error": "library_file_ids required"}), 400

    result = reference_service.bulk_add_references(
        project_id=project_id,
        library_file_ids=library_file_ids,
        user_id=user_id,
    )

    return jsonify(result)


# =============================================================================
# SCANNING
# =============================================================================


@library_bp.get("/api/library/scan/config")
def get_scan_config():
    """Get current scan configuration (patterns, mount path)."""
    user_id, err = ensure_user()
    if err:
        return err

    storage = scanner_service.storage

    return jsonify(
        {
            "mount_path": str(storage.get_mount_path()),
            "is_mounted": storage.is_mounted(),
            "include_patterns": scanner_service.get_include_patterns(),
            "exclude_patterns": scanner_service.get_exclude_patterns(),
        }
    )


@library_bp.patch("/api/library/scan/config")
def update_scan_config():
    """
    Update scan configuration.

    Body:
        include_patterns: List of glob patterns to include
        exclude_patterns: List of glob patterns to exclude
    """
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}

    if "include_patterns" in data:
        scanner_service.set_include_patterns(data["include_patterns"])

    if "exclude_patterns" in data:
        scanner_service.set_exclude_patterns(data["exclude_patterns"])

    return jsonify({"updated": True})


@library_bp.get("/api/library/scan/preview")
def preview_scan():
    """
    Preview what would be scanned without importing.

    Query params:
        path: Directory to scan (default: mount_path)
        limit: Max files to list (default: 100)
    """
    user_id, err = ensure_user()
    if err:
        return err

    path = request.args.get("path")
    limit = min(int(request.args.get("limit", 100)), 500)

    try:
        files = []
        for i, scanned in enumerate(scanner_service.scan_directory(path)):
            if i >= limit:
                break
            files.append(
                {
                    "path": scanned.relative_path,
                    "filename": scanned.filename,
                    "size_bytes": scanned.size_bytes,
                    "mime_type": scanned.mime_type,
                }
            )

        return jsonify(
            {"files": files, "count": len(files), "truncated": len(files) == limit}
        )

    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@library_bp.get("/api/library/scan/summary")
def scan_summary():
    """
    Get summary statistics for scan path.

    Query params:
        path: Directory to scan (default: mount_path)
    """
    user_id, err = ensure_user()
    if err:
        return err

    path = request.args.get("path")

    try:
        summary = scanner_service.scan_summary(path)
        return jsonify(summary)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@library_bp.get("/api/library/scan/new")
def scan_new_files():
    """
    List files in scan path not yet in library.

    Query params:
        path: Directory to scan (default: mount_path)
        limit: Max files to return (default: 100)
    """
    user_id, err = ensure_user()
    if err:
        return err

    path = request.args.get("path")
    limit = min(int(request.args.get("limit", 100)), 500)

    try:
        files = []
        for i, scanned in enumerate(scanner_service.find_new_files(path)):
            if i >= limit:
                break
            files.append(
                {
                    "path": scanned.path,
                    "relative_path": scanned.relative_path,
                    "filename": scanned.filename,
                    "size_bytes": scanned.size_bytes,
                    "mime_type": scanned.mime_type,
                }
            )

        total_new = scanner_service.count_new_files(path)

        return jsonify(
            {
                "files": files,
                "count": len(files),
                "total_new": total_new,
                "truncated": len(files) < total_new,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# INGESTING
# =============================================================================


@library_bp.post("/api/library/ingest")
def ingest_files():
    """
    Import files into the library.

    Body:
        path: Directory to scan and import (default: mount_path)
        file_paths: List of specific file paths to import (alternative to path)
        new_only: Only import files not already in library (default: true)
        auto_index: Generate embeddings during import (default: true)
    """
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}

    path = data.get("path")
    file_paths = data.get("file_paths")
    new_only = data.get("new_only", True)
    auto_index = data.get("auto_index", True)

    try:
        if file_paths:
            # Import specific files
            progress = ingest_service.ingest_batch(
                file_paths=file_paths, auto_index=auto_index
            )
        else:
            # Import from directory
            progress = ingest_service.ingest_directory(
                path=path, auto_index=auto_index, new_only=new_only
            )

        return jsonify({"status": "completed", "result": progress.to_dict()})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@library_bp.post("/api/library/sync")
def sync_library():
    """
    Synchronize library with filesystem.

    Adds new files and optionally removes records for deleted files.

    Body:
        path: Directory to sync (default: mount_path)
        remove_missing: Remove records for files no longer on disk (default: false)
    """
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}
    path = data.get("path")
    remove_missing = data.get("remove_missing", False)

    try:
        result = ingest_service.sync_library(path=path, remove_missing=remove_missing)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@library_bp.post("/api/library/ingest/single")
def ingest_single_file():
    """
    Import a single file by path.

    Body:
        file_path: Absolute path to the file
        metadata: Optional metadata dict
        auto_index: Generate embeddings (default: true)
    """
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}
    file_path = data.get("file_path")
    metadata = data.get("metadata")
    auto_index = data.get("auto_index", True)

    if not file_path:
        return jsonify({"error": "file_path required"}), 400

    from datetime import datetime
    from pathlib import Path

    path = Path(file_path)

    if not path.exists():
        return jsonify({"error": f"File not found: {file_path}"}), 404

    # Create ScannedFile
    scanned = ScannedFile(
        path=str(path),
        filename=path.name,
        size_bytes=path.stat().st_size,
        modified_at=datetime.fromtimestamp(path.stat().st_mtime),
        mime_type=scanner_service._guess_mime_type(path.name),
        relative_path=str(path),
    )

    result = ingest_service.ingest_file(
        scanned_file=scanned, auto_index=auto_index, metadata=metadata
    )

    if result["status"] == "error":
        return jsonify(result), 500

    return jsonify(result), 201 if result["status"] == "created" else 200


# =============================================================================
# INDEXING QUEUE
# =============================================================================


@library_bp.get("/api/library/index/queue")
def get_index_queue():
    """Get indexing queue statistics."""
    user_id, err = ensure_user()
    if err:
        return err

    return jsonify(index_queue_service.get_queue_stats())


@library_bp.get("/api/library/index/pending")
def get_pending_index():
    """
    Get files pending indexing.

    Query params:
        limit: Max files to return (default: 50)
    """
    user_id, err = ensure_user()
    if err:
        return err

    limit = min(int(request.args.get("limit", 50)), 200)
    files = index_queue_service.get_unindexed_files(limit=limit)

    return jsonify({"files": files, "count": len(files)})


@library_bp.post("/api/library/index/process")
def process_index_queue():
    """
    Process indexing queue.

    Body:
        count: Number of files to process (default: 10)
    """
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}
    count = min(int(data.get("count", 10)), 100)

    result = index_queue_service.index_next(count=count)

    return jsonify(result)


@library_bp.post("/api/library/index/all")
def index_all_files():
    """
    Process entire indexing queue.

    Warning: Can take a long time for large libraries!

    Body:
        batch_size: Files per batch (default: 10)
    """
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}
    batch_size = min(int(data.get("batch_size", 10)), 50)

    result = index_queue_service.index_all(batch_size=batch_size)

    return jsonify(result)


@library_bp.post("/api/library/index/reindex")
def reindex_files():
    """
    Mark files for reindexing.

    Body:
        file_ids: List of file IDs to reindex (if not provided, reindexes all)
    """
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}
    file_ids = data.get("file_ids")

    if file_ids:
        count = index_queue_service.mark_for_reindex(file_ids)
        return jsonify({"marked_for_reindex": count})
    else:
        # Reindex everything
        result = index_queue_service.reindex_all()
        return jsonify(result)
