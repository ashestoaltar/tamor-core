# api/routes/tasks_api.py
import json
from functools import wraps

from flask import Blueprint, jsonify, request, session

from utils.db import get_db

tasks_bp = Blueprint("tasks_api", __name__, url_prefix="/api")


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "not_authenticated"}), 401
        return fn(*args, **kwargs)
    return wrapper


def _safe_json_load(s):
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {}


def _row_to_task(r):
    d = {k: r[k] for k in r.keys()}
    d["payload"] = _safe_json_load(d.pop("payload_json", None))
    d["normalized"] = _safe_json_load(d.pop("normalized_json", None))
    return d


@tasks_bp.get("/tasks")
@require_login
def list_tasks():
    """
    Matches UI expectations:
      GET /api/tasks?status=...&task_type=...&limit=...
    """
    user_id = session.get("user_id")
    status = (request.args.get("status") or "").strip()
    task_type = (request.args.get("task_type") or "").strip()
    try:
        limit = int(request.args.get("limit") or "100")
    except Exception:
        limit = 100
    limit = max(1, min(200, limit))

    where = ["user_id = ?"]
    params = [user_id]

    if status:
        where.append("status = ?")
        params.append(status)

    if task_type:
        where.append("task_type = ?")
        params.append(task_type)

    sql = f"""
        SELECT
            id, user_id, project_id, conversation_id, message_id,
            task_type, title, confidence,
            payload_json, normalized_json,
            status, created_at
        FROM detected_tasks
        WHERE {" AND ".join(where)}
        ORDER BY id DESC
        LIMIT ?
    """
    params.append(limit)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    tasks = [_row_to_task(r) for r in rows]
    return jsonify({"ok": True, "tasks": tasks})


def _update_and_return(task_id: int, new_status: str):
    user_id = session.get("user_id")

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE detected_tasks SET status = ? WHERE id = ? AND user_id = ?",
        (new_status, task_id, user_id),
    )
    if cur.rowcount == 0:
        conn.close()
        return None

    conn.commit()

    cur.execute(
        """
        SELECT
            id, user_id, project_id, conversation_id, message_id,
            task_type, title, confidence,
            payload_json, normalized_json,
            status, created_at
        FROM detected_tasks
        WHERE id = ? AND user_id = ?
        """,
        (task_id, user_id),
    )
    row = cur.fetchone()
    conn.close()

    return _row_to_task(row) if row else None


@tasks_bp.post("/tasks/<int:task_id>/confirm")
@require_login
def confirm_task(task_id: int):
    t = _update_and_return(task_id, "confirmed")
    if not t:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"ok": True, "task": t})


@tasks_bp.post("/tasks/<int:task_id>/cancel")
@require_login
def cancel_task(task_id: int):
    t = _update_and_return(task_id, "cancelled")
    if not t:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"ok": True, "task": t})


@tasks_bp.post("/tasks/<int:task_id>/complete")
@require_login
def complete_task(task_id: int):
    t = _update_and_return(task_id, "completed")
    if not t:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"ok": True, "task": t})


@tasks_bp.post("/tasks/<int:task_id>/status")
@require_login
def set_status(task_id: int):
    """
    Matches UI expectations:
      POST /api/tasks/<id>/status  { status: "dismissed" | "confirmed" }
    """
    data = request.json or {}
    next_status = (data.get("status") or "").strip()

    allowed = {"dismissed", "confirmed"}
    if next_status not in allowed:
        return jsonify({"error": "invalid_status"}), 400

    t = _update_and_return(task_id, next_status)
    if not t:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"ok": True, "task": t})

