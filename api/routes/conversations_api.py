# routes/conversations_api.py
from flask import Blueprint, jsonify, session, request
from utils.db import get_db

conversations_bp = Blueprint("conversations_api", __name__, url_prefix="/api")


@conversations_bp.get("/conversations")
def list_conversations():
    """Return all conversations for the logged-in user."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "not_authenticated"}), 401

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
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "not_authenticated"}), 401

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
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "not_authenticated"}), 401

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
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "not_authenticated"}), 401

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
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "not_authenticated"}), 401

    data = request.json or {}
    project_id = data.get("project_id", None)

    conn = get_db()
    cur = conn.cursor()

    # If project_id is not None, ensure the project belongs to this user
    if project_id is not None:
        cur.execute(
          "SELECT id FROM projects WHERE id = ? AND user_id = ?",
          (project_id, user_id),
        )
        if not cur.fetchone():
            conn.close()
            return jsonify({"error": "project_not_found"}), 404

    # Ensure conversation belongs to this user
    cur.execute(
        "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    )
    if not cur.fetchone():
        conn.close()
        return jsonify({"error": "conversation_not_found"}), 404

    cur.execute(
        """
        UPDATE conversations
        SET project_id = ?
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


