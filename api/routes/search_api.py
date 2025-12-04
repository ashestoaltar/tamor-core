# routes/search_api.py
from flask import Blueprint, jsonify, request, session

from utils.db import get_db
from core.memory_core import search_memories

search_bp = Blueprint("search_api", __name__, url_prefix="/api")


@search_bp.get("/search")
def global_search():
    """
    Global workspace search.

    Returns:
    {
      "conversations": [...],
      "projects": [...],
      "memories": [...]
    }
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "not_authenticated"}), 401

    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify(
            {"conversations": [], "projects": [], "memories": []}
        )

    like = f"%{query}%"

    conn = get_db()
    cur = conn.cursor()

    # --- Conversation search (title, most recent first) ---
    cur.execute(
        """
        SELECT id, title, project_id, mode, created_at, updated_at
        FROM conversations
        WHERE user_id = ?
          AND title LIKE ?
        ORDER BY updated_at DESC
        LIMIT 50
        """,
        (user_id, like),
    )
    conversations = [dict(r) for r in cur.fetchall()]

    # --- Project search (name + description) ---
    cur.execute(
        """
        SELECT id, name, description, created_at
        FROM projects
        WHERE user_id = ?
          AND (name LIKE ? OR COALESCE(description, '') LIKE ?)
        ORDER BY created_at DESC
        LIMIT 50
        """,
        (user_id, like, like),
    )
    projects = [dict(r) for r in cur.fetchall()]

    conn.close()

    # --- Memory search (vector-based, global knowledge store) ---
    memories = []
    try:
        mem_results = search_memories(query, limit=10)
        memories = [
            {"score": float(score), "id": mem_id, "content": content}
            for (score, mem_id, content) in mem_results
        ]
    except Exception:
        # If embeddings/model are unavailable for any reason, just omit memories
        memories = []

    return jsonify(
        {
            "conversations": conversations,
            "projects": projects,
            "memories": memories,
        }
    )
