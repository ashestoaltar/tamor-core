# routes/conversations_api.py
from flask import Blueprint, jsonify, request

from utils.db import get_db
from utils.auth import ensure_user

conversations_bp = Blueprint("conversations_api", __name__, url_prefix="/api")


@conversations_bp.get("/conversations")
def list_conversations():
    """Return all conversations for the logged-in user."""
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, user_id, project_id, title, created_at, updated_at
        FROM conversations
        WHERE user_id = ?
        ORDER BY updated_at DESC
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()

    convos = [dict(r) for r in rows]
    return jsonify({"conversations": convos})


@conversations_bp.get("/conversations/<int:conv_id>/messages")
def list_messages(conv_id):
    """Return all messages for a conversation, if it belongs to this user."""
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()

    # Verify ownership
    cur.execute(
        "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    )
    if not cur.fetchone():
        conn.close()
        return jsonify({"error": "not_found"}), 404

    cur.execute(
        """
        SELECT id, conversation_id, sender, role, content, created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY created_at ASC
        """,
        (conv_id,),
    )
    rows = cur.fetchall()
    conn.close()

    messages = [dict(r) for r in rows]
    return jsonify({"messages": messages})


@conversations_bp.patch("/conversations/<int:conv_id>")
def rename_conversation(conv_id):
    """Rename a conversation that belongs to the current user."""
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title_required"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE conversations
        SET title = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        """,
        (title, conv_id, user_id),
    )
    if cur.rowcount == 0:
        conn.close()
        return jsonify({"error": "not_found"}), 404

    conn.commit()
    conn.close()

    return jsonify({"id": conv_id, "title": title})


@conversations_bp.delete("/conversations/<int:conv_id>")
def delete_conversation(conv_id):
    """Delete a conversation and its messages for the current user."""
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()

    # Verify ownership
    cur.execute(
        "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "not_found"}), 404

    # Delete messages first (if no ON DELETE CASCADE)
    cur.execute(
        "DELETE FROM messages WHERE conversation_id = ?",
        (conv_id,),
    )

    # Then delete the conversation
    cur.execute(
        "DELETE FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    )

    conn.commit()
    conn.close()

    return jsonify({"ok": True, "id": conv_id})


@conversations_bp.patch("/conversations/<int:conv_id>/project")
def update_conversation_project(conv_id):
    """
    Assign or unassign a conversation to a project.

    body: { "project_id": <int or null> }
    """
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}
    raw_project_id = data.get("project_id", None)

    # Normalize project_id:
    # - null / "" / "null" -> None (Unassigned)
    # - otherwise try to cast to int
    project_id = None
    if raw_project_id not in (None, "", "null"):
        try:
            project_id = int(raw_project_id)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_project_id"}), 400

    conn = get_db()
    cur = conn.cursor()

    # Ensure conversation belongs to this user
    cur.execute(
        "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    )
    if not cur.fetchone():
        conn.close()
        return jsonify({"error": "conversation_not_found"}), 404

    # Just set project_id; the frontend only ever sends IDs from /projects
    cur.execute(
        """
        UPDATE conversations
        SET project_id = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        """,
        (project_id, conv_id, user_id),
    )
    if cur.rowcount == 0:
        conn.close()
        return jsonify({"error": "update_failed"}), 400

    conn.commit()
    conn.close()

    return jsonify({"id": conv_id, "project_id": project_id})


@conversations_bp.get("/conversations/search")
def search_conversations():
    """
    Simple search over conversations (title only) for the current user.
    Query: /api/conversations/search?q=term
    """
    user_id, err = ensure_user()
    if err:
        return err

    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"conversations": []})

    like = f"%{query}%"

    conn = get_db()
    cur = conn.cursor()
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
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    return jsonify({"conversations": rows})
