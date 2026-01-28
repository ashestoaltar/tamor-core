# routes/search_api.py
from flask import Blueprint, jsonify, request

from utils.db import get_db
from utils.auth import ensure_user
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
    user_id, err = ensure_user()
    if err:
        return err

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
    title_matched_ids = {c["id"] for c in conversations}
    for c in conversations:
        c["match_source"] = "title"

    # --- Message content search (exclude title-matched conversations) ---
    placeholders = ""
    params = [user_id, like]
    if title_matched_ids:
        placeholders = " AND c.id NOT IN ({})".format(
            ",".join("?" for _ in title_matched_ids)
        )
        params.extend(title_matched_ids)

    cur.execute(
        f"""
        SELECT c.id, c.title, c.project_id, c.mode, c.created_at, c.updated_at,
               m.content AS _match_content
        FROM messages m
        JOIN conversations c ON c.id = m.conversation_id
        WHERE c.user_id = ?
          AND m.content LIKE ?
          {placeholders}
        GROUP BY c.id
        ORDER BY c.updated_at DESC
        LIMIT 20
        """,
        params,
    )
    for r in cur.fetchall():
        row = dict(r)
        content = row.pop("_match_content", "")
        # Build a truncated snippet (~150 chars) around the match
        lower_content = content.lower()
        idx = lower_content.find(query.lower())
        if idx >= 0:
            start = max(0, idx - 40)
            end = min(len(content), idx + 110)
            snippet = ("…" if start > 0 else "") + content[start:end].strip() + ("…" if end < len(content) else "")
        else:
            snippet = content[:150].strip() + ("…" if len(content) > 150 else "")
        row["match_source"] = "message"
        row["match_snippet"] = snippet
        conversations.append(row)

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
