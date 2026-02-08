"""
Harvest cluster import API routes.

Endpoints for importing pre-processed content packages from the
harvesting cluster into Tamor's library.
"""

from flask import Blueprint, jsonify, request

from utils.auth import ensure_user
from services.library.harvest_import_service import HarvestImportService

harvest_bp = Blueprint("harvest", __name__)
harvest_service = HarvestImportService()


@harvest_bp.get("/api/harvest/pending")
def list_pending():
    """List packages in the ready directory waiting for import."""
    user_id, err = ensure_user()
    if err:
        return err

    packages = harvest_service.list_pending()
    return jsonify({
        "pending": len(packages),
        "packages": packages,
    })


@harvest_bp.post("/api/harvest/import")
def import_package():
    """
    Import a specific package file.

    Body:
        filename: Name of the package file in /harvest/ready/
    """
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}
    filename = data.get("filename")
    if not filename:
        return jsonify({"error": "filename is required"}), 400

    import os
    from services.library.harvest_import_service import HARVEST_READY_DIR

    package_path = os.path.join(HARVEST_READY_DIR, filename)
    if not os.path.exists(package_path):
        return jsonify({"error": f"Package not found: {filename}"}), 404

    result = harvest_service.import_package(package_path)
    return jsonify(result)


@harvest_bp.post("/api/harvest/import-all")
def import_all():
    """Import all pending packages from the ready directory."""
    user_id, err = ensure_user()
    if err:
        return err

    result = harvest_service.import_all_pending()
    return jsonify(result)


@harvest_bp.get("/api/harvest/status")
def harvest_status():
    """Get overall harvest pipeline status."""
    user_id, err = ensure_user()
    if err:
        return err

    import os
    from services.library.harvest_import_service import (
        HARVEST_IMPORTED_DIR,
        HARVEST_READY_DIR,
    )

    pending = harvest_service.list_pending()
    pending_count = len(pending)

    # Count imported
    imported_count = 0
    if os.path.isdir(HARVEST_IMPORTED_DIR):
        imported_count = len([
            f for f in os.listdir(HARVEST_IMPORTED_DIR)
            if f.endswith(".json")
        ])

    # Check harvest dirs exist
    harvest_base = "/mnt/library/harvest"
    dirs_exist = {
        "raw": os.path.isdir(os.path.join(harvest_base, "raw")),
        "processed": os.path.isdir(os.path.join(harvest_base, "processed")),
        "ready": os.path.isdir(os.path.join(harvest_base, "ready")),
        "config": os.path.isdir(os.path.join(harvest_base, "config")),
        "logs": os.path.isdir(os.path.join(harvest_base, "logs")),
    }

    return jsonify({
        "pending_packages": pending_count,
        "imported_packages": imported_count,
        "harvest_dirs": dirs_exist,
        "ready_dir": HARVEST_READY_DIR,
    })
