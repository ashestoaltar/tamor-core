# api/routes/tasks_api.py
import json
from flask import Blueprint, jsonify, request, session
from utils.db import get_db

tasks_bp = Blueprint("tasks_api", __name__, url_prefix="/api/tasks")


def _task_row_to_dict(r):
    try:
        normalized = json.loads(r["normalized_json"]) if r["normalized_json"] else None
    except Exception:
        normalized = None

    status = r["status"]
    # Normalize legacy spelling if older rows exist
    if status == "canceled":
        status = "cancelled"

    return {
        "id": r["id"],
        "conversation_id": r["conversation_id"],
        "message_id": r["message_id"],
        "task_type": r["task_type"],
        "title": r["title"],
        "status": status,
        "confidence": r["confidence"],
        "normalized": normalized,
        "created_at": r["created_at"],
    }


@tasks_bp.get("")
def list_tasks():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    conversation_id = request.args.get("conversation_id")
    status = request.args.get("status")
    task_type = request.args.get("task_type")
    q = request.args.get("q")

    try:
        limit = int(request.args.get("limit", 50))
    except Exception:
        limit = 50
    limit = max(1, min(limit, 200))

    where = ["user_id=?"]
    params = [user_id]

    if conversation_id:
        where.append("conversation_id=?")
        params.append(conversation_id)

    if status:
        where.append("status=?")
        params.append(status)

    if task_type:
        where.append("task_type=?")
        params.append(task_type)

    if q:
        where.append("(title LIKE ? OR payload_json LIKE ? OR normalized_json LIKE ?)")
        qq = f"%{q}%"
        params.extend([qq, qq, qq])

    sql = f"""
    SELECT id, conversation_id, message_id, task_type, title, status, confidence, normalized_json, created_at
    FROM detected_tasks
    WHERE {' AND '.join(where)}
    ORDER BY id DESC
    LIMIT ?
    """
    params.append(limit)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    return jsonify({"ok": True, "tasks": [_task_row_to_dict(r) for r in rows]})


@tasks_bp.get("/counts")
def task_counts():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    conversation_id = request.args.get("conversation_id")

    where = ["user_id=?"]
    params = [user_id]

    if conversation_id:
        where.append("conversation_id=?")
        params.append(conversation_id)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT status, COUNT(*) AS n
        FROM detected_tasks
        WHERE {' AND '.join(where)}
        GROUP BY status
        """,
        params,
    )
    rows = cur.fetchall()
    conn.close()

    by_status = {r["status"]: r["n"] for r in rows}

    # Normalize legacy spelling if older rows exist
    if "canceled" in by_status and "cancelled" not in by_status:
        by_status["cancelled"] = by_status.pop("canceled")

    total = sum(by_status.values()) if by_status else 0
    return jsonify({"ok": True, "total": total, "by_status": by_status})


@tasks_bp.get("/<int:task_id>/runs")
def get_task_runs(task_id: int):
    """Return execution history for a task (most recent first)."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    try:
        limit = int(request.args.get("limit", 50))
    except Exception:
        limit = 50
    limit = max(1, min(limit, 200))

    conn = get_db()
    cur = conn.cursor()

    # Ensure the task belongs to the current user
    cur.execute(
        "SELECT id FROM detected_tasks WHERE id=? AND user_id=?",
        (task_id, user_id),
    )
    task_row = cur.fetchone()
    if not task_row:
        conn.close()
        return jsonify({"error": "not_found"}), 404

    # Discover available columns so we don't break if the schema differs slightly
    cur.execute("PRAGMA table_info(task_runs)")
    cols = [r["name"] for r in cur.fetchall()]
    wanted = ["id", "task_id", "status", "created_at", "started_at", "finished_at", "error_text"]
    select_cols = [c for c in wanted if c in cols]
    if not select_cols:
        select_cols = ["*"]

    cur.execute(
        f"""
        SELECT {', '.join(select_cols)}
        FROM task_runs
        WHERE task_id=?
        ORDER BY id DESC
        LIMIT ?
        """,
        (task_id, limit),
    )
    rows = cur.fetchall()
    conn.close()

    runs = []
    for r in rows:
        try:
            runs.append(dict(r))
        except Exception:
            runs.append({k: r[k] for k in r.keys()})

    return jsonify({"ok": True, "task_id": task_id, "runs": runs})


@tasks_bp.post("/<int:task_id>/confirm")
def confirm_task(task_id: int):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE detected_tasks
        SET status='confirmed'
        WHERE id=? AND user_id=?
        """,
        (task_id, user_id),
    )
    updated = cur.rowcount

    cur.execute(
        """
        SELECT id, conversation_id, message_id, task_type, title, status, confidence, normalized_json, created_at
        FROM detected_tasks
        WHERE id=? AND user_id=?
        """,
        (task_id, user_id),
    )
    row = cur.fetchone()
    conn.commit()
    conn.close()

    if not row:
        return jsonify({"error": "not_found"}), 404

    return jsonify({"ok": True, "updated": updated == 1, "task": _task_row_to_dict(row)})


@tasks_bp.post("/<int:task_id>/cancel")
def cancel_task(task_id: int):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE detected_tasks
        SET status='cancelled'
        WHERE id=? AND user_id=?
        """,
        (task_id, user_id),
    )
    updated = cur.rowcount

    cur.execute(
        """
        SELECT id, conversation_id, message_id, task_type, title, status, confidence, normalized_json, created_at
        FROM detected_tasks
        WHERE id=? AND user_id=?
        """,
        (task_id, user_id),
    )
    row = cur.fetchone()
    conn.commit()
    conn.close()

    if not row:
        return jsonify({"error": "not_found"}), 404

    return jsonify({"ok": True, "updated": updated == 1, "task": _task_row_to_dict(row)})


@tasks_bp.post("/<int:task_id>/complete")
def complete_task(task_id: int):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE detected_tasks
        SET status='completed'
        WHERE id=? AND user_id=?
        """,
        (task_id, user_id),
    )
    updated = cur.rowcount

    cur.execute(
        """
        SELECT id, conversation_id, message_id, task_type, title, status, confidence, normalized_json, created_at
        FROM detected_tasks
        WHERE id=? AND user_id=?
        """,
        (task_id, user_id),
    )
    row = cur.fetchone()
    conn.commit()
    conn.close()

    if not row:
        return jsonify({"error": "not_found"}), 404

    return jsonify({"ok": True, "updated": updated == 1, "task": _task_row_to_dict(row)})


@tasks_bp.post("/<int:task_id>/status")
def set_task_status(task_id: int):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    new_status = (body.get("status") or "").strip().lower()

    allowed = {
        "needs_confirmation",
        "confirmed",
        "dismissed",
        "completed",
        "cancelled",
        "canceled",  # accept legacy spelling from any callers
    }
    if new_status not in allowed:
        return jsonify({"error": "invalid_status"}), 400

    if new_status == "canceled":
        new_status = "cancelled"

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE detected_tasks
        SET status=?
        WHERE id=? AND user_id=?
        """,
        (new_status, task_id, user_id),
    )
    updated = cur.rowcount

    cur.execute(
        """
        SELECT id, conversation_id, message_id, task_type, title, status, confidence, normalized_json, created_at
        FROM detected_tasks
        WHERE id=? AND user_id=?
        """,
        (task_id, user_id),
    )
    row = cur.fetchone()
    conn.commit()
    conn.close()

    if not row:
        return jsonify({"error": "not_found"}), 404

    return jsonify({"ok": True, "updated": updated == 1, "task": _task_row_to_dict(row)})

