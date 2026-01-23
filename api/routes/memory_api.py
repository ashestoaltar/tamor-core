# routes/memory_api.py
"""
Memory API - Governed Memory System (Phase 6.1)

Endpoints for managing user memories with governance controls.
"""
from flask import Blueprint, jsonify, request, session

from utils.auth import require_login, get_current_user_id
import services.memory_service as mem_svc

memory_bp = Blueprint("memory_api", __name__, url_prefix="/api")


@memory_bp.get("/personality")
def get_personality():
    from core.config import personality
    return jsonify(personality)


# -----------------------------------------------------------------------------
# Memory CRUD
# -----------------------------------------------------------------------------

@memory_bp.post("/memory/add")
@require_login
def add_memory():
    """Add a manual memory."""
    import json as json_mod
    data = request.json or {}
    # Handle case where JSON might be double-encoded as string
    if isinstance(data, str):
        try:
            data = json_mod.loads(data)
        except (json_mod.JSONDecodeError, TypeError):
            data = {}
    content = data.get("content")
    category = data.get("category", "general")
    is_pinned = data.get("is_pinned", False)

    if not content:
        return jsonify({"error": "content is required"}), 400

    user_id = get_current_user_id()

    memory_id = mem_svc.add_memory(
        content=content,
        category=category,
        user_id=user_id,
        source="manual",
        is_pinned=is_pinned,
    )

    if memory_id:
        return jsonify({"status": "success", "id": memory_id})
    else:
        return jsonify({"error": "Failed to add memory"}), 500


@memory_bp.get("/memory/list")
@require_login
def list_memories():
    """List memories with filters."""
    user_id = get_current_user_id()
    category = request.args.get("category")
    source = request.args.get("source")
    pinned_only = request.args.get("pinned_only", "").lower() == "true"
    query = request.args.get("q")
    limit = int(request.args.get("limit", 200))

    memories = mem_svc.list_memories(
        user_id=user_id,
        category=category,
        source=source,
        pinned_only=pinned_only,
        query=query,
        limit=limit,
    )

    return jsonify(memories)


@memory_bp.get("/memory/<int:memory_id>")
@require_login
def get_memory(memory_id):
    """Get a single memory."""
    memory = mem_svc.get_memory(memory_id)
    if not memory:
        return jsonify({"error": "Memory not found"}), 404

    # Check ownership
    user_id = get_current_user_id()
    if memory.get("user_id") and memory["user_id"] != user_id:
        return jsonify({"error": "Access denied"}), 403

    return jsonify(memory)


@memory_bp.put("/memory/<int:memory_id>")
@require_login
def update_memory(memory_id):
    """Update a memory."""
    data = request.json or {}
    user_id = get_current_user_id()

    content = data.get("content")
    category = data.get("category")
    is_pinned = data.get("is_pinned")

    success = mem_svc.update_memory(
        memory_id=memory_id,
        content=content,
        category=category,
        is_pinned=is_pinned,
        user_id=user_id,
    )

    if success:
        return jsonify({"status": "updated", "id": memory_id})
    else:
        return jsonify({"error": "Failed to update memory"}), 400


@memory_bp.delete("/memory/<int:memory_id>")
@require_login
def delete_memory(memory_id):
    """Delete a memory."""
    user_id = get_current_user_id()

    success = mem_svc.delete_memory(memory_id, user_id=user_id)

    if success:
        return jsonify({"status": "deleted", "id": memory_id})
    else:
        return jsonify({"error": "Failed to delete memory"}), 400


# -----------------------------------------------------------------------------
# Pin/Unpin
# -----------------------------------------------------------------------------

@memory_bp.post("/memory/<int:memory_id>/pin")
@require_login
def pin_memory(memory_id):
    """Pin a memory."""
    user_id = get_current_user_id()
    result = mem_svc.pin_memory(memory_id, user_id=user_id)

    if result.get("success"):
        return jsonify({"status": "pinned", "id": memory_id})
    else:
        return jsonify({"error": result.get("error", "Failed to pin")}), 400


@memory_bp.post("/memory/<int:memory_id>/unpin")
@require_login
def unpin_memory(memory_id):
    """Unpin a memory."""
    user_id = get_current_user_id()
    result = mem_svc.unpin_memory(memory_id, user_id=user_id)

    if result.get("success"):
        return jsonify({"status": "unpinned", "id": memory_id})
    else:
        return jsonify({"error": "Failed to unpin"}), 400


@memory_bp.get("/memory/pinned")
@require_login
def get_pinned_memories():
    """Get all pinned memories."""
    user_id = get_current_user_id()
    memories = mem_svc.get_pinned_memories(user_id=user_id)
    return jsonify(memories)


# -----------------------------------------------------------------------------
# Search
# -----------------------------------------------------------------------------

@memory_bp.post("/memory/search")
@require_login
def search_memories():
    """Semantic search for memories."""
    data = request.json or {}
    query = data.get("query", "")
    limit = data.get("limit", 10)

    if not query:
        return jsonify([])

    user_id = get_current_user_id()
    results = mem_svc.search_memories(query, user_id=user_id, limit=limit)

    return jsonify(results)


# -----------------------------------------------------------------------------
# Settings
# -----------------------------------------------------------------------------

@memory_bp.get("/memory/settings")
@require_login
def get_settings():
    """Get memory governance settings."""
    user_id = get_current_user_id()
    settings = mem_svc.get_settings(user_id)
    return jsonify(settings)


@memory_bp.put("/memory/settings")
@require_login
def update_settings():
    """Update memory governance settings."""
    data = request.json or {}
    user_id = get_current_user_id()

    auto_save_enabled = data.get("auto_save_enabled")
    auto_save_categories = data.get("auto_save_categories")
    max_pinned_memories = data.get("max_pinned_memories")

    success = mem_svc.update_settings(
        user_id=user_id,
        auto_save_enabled=auto_save_enabled,
        auto_save_categories=auto_save_categories,
        max_pinned_memories=max_pinned_memories,
    )

    if success:
        return jsonify({"status": "updated"})
    else:
        return jsonify({"error": "Failed to update settings"}), 500


# -----------------------------------------------------------------------------
# Categories
# -----------------------------------------------------------------------------

@memory_bp.get("/memory/categories")
@require_login
def get_categories():
    """Get list of memory categories in use."""
    categories = mem_svc.get_categories()
    return jsonify(categories)


# -----------------------------------------------------------------------------
# Legacy Auto-Memory Endpoint (for backwards compatibility)
# -----------------------------------------------------------------------------

@memory_bp.post("/memory/auto")
def auto_memory_ingest():
    """
    Auto-memory ingestion endpoint.
    Now uses governance settings to determine if storage is allowed.
    """
    from core.memory_core import auto_store_memory_if_relevant

    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    mode = data.get("mode", "Default")
    source = data.get("source", "user")

    if not text:
        return jsonify({"stored": False, "reason": "empty"}), 200

    # Get user_id if available
    user_id = get_current_user_id() if session.get("user_id") else None

    category = auto_store_memory_if_relevant(text, mode, source, user_id=user_id)

    if category:
        return jsonify({"stored": True, "category": category}), 200
    else:
        return jsonify({"stored": False, "reason": "not relevant or blocked"}), 200
