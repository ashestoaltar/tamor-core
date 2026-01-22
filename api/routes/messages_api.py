# api/routes/messages_api.py
from flask import Blueprint, jsonify, request

from utils.db import get_db
from utils.auth import ensure_user

messages_bp = Blueprint("messages_api", __name__, url_prefix="/api")


@messages_bp.get("/messages/file_refs")
def get_messages_file_refs():
    """
    UI compatibility endpoint.

    Some UI code calls:
      GET /api/messages/file_refs?conversation_id=123

    We don't have a real message<->file linkage system yet, so this returns
    a stable payload that stops 404 spam.

    Response shape:
      {
        "ok": true,
        "conversation_id": 123 | null,
        "files_by_message_id": {}
      }

    If conversation_id is provided, we verify it belongs to the current user.
    """
    user_id, err = ensure_user()
    if err:
        return err

    conversation_id = request.args.get("conversation_id", type=int)

    if conversation_id:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return jsonify({"error": "not_found"}), 404

    # No linkage system yet — return empty mapping.
    return jsonify(
        {
            "ok": True,
            "conversation_id": conversation_id,
            "files_by_message_id": {},
        }
    )


@messages_bp.get("/messages/<int:message_id>/file-refs")
def get_message_file_refs(message_id: int):
    """
    Return file references for a given message.

    UI expects: { "files": [...] }

    For now (Phase 3.1 cleanup): return an empty list so the UI stops 404 spamming.
    We still verify ownership so users can't probe other users' message IDs.
    """
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()

    # Verify this message belongs to the current user (via conversations ownership)
    cur.execute(
        """
        SELECT m.id
        FROM messages m
        JOIN conversations c ON c.id = m.conversation_id
        WHERE m.id = ? AND c.user_id = ?
        """,
        (message_id, user_id),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "not_found"}), 404

    # No file linkage system yet, so return empty.
    return jsonify({"files": []})

