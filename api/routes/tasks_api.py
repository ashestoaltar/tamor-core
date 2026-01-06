# api/routes/tasks_api.py

import json
from functools import wraps

from flask import Blueprint, jsonify, request, session

from utils.db import get_db

tasks_bp = Blueprint("tasks_api", __name__, url_prefix="/api")

TERMINAL_STATUSES = {"completed", "cancelled"}


# -----------------------------
# Auth
# -----------------------------

def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "not_authenticated"}), 401
        return fn(*args, **kwargs)
    return wrapper


# -----------------------------
# Helpers
# -----------------------------

def _safe_json_load(v):
    if not v:
        return None
    try:
        return json.loads(v)
    except Exception:
        return None


def _row_to_task(r):
    d = {k: r[k] for k in r.keys()}
    d["payload"] = _safe_json_load(d.pop("payload_json", None))
    d["normalized"] = _safe_json_load(d.pop("normalized_json", None))
    return d


def _get_task(task_id: int):
    """Fetch task for current user."""
    user_id = session.get("user_id")
    conn = get_db()
    cur = conn.cursor()
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


def _is_recurring(task: dict) -> bool:
    n = (task or {}).get("normalized") or {}
    return bool(n.get("recurrence") or n.get("rrule"))


def _invalid_transition(task: dict, to_status: str, reason: str | None = None):
    payload = {
        "error": "invalid_transition",
        "task_id": (task or {}).get("id"),
        "from": (task or {}).get("status"),
        "to": to_status,
    }
    if reason:
        payload["reason"] = reason
    return jsonify(payload), 400


def _update_status_guarded(task_id: int, from_status: str, to_status: str):
    """Atomic status transition."""
    user_id = session.get("user_id")
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE detected_tasks
        SET status = ?
        WHERE id = ? AND user_id = ? AND status = ?
        """,
        (to_status, task_id, user_id, from_status),
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


# -----------------------------
# List / Query
# -----------------------------

@tasks_bp.get("/tasks")
@require_login
def list_tasks():
    user_id = session.get("user_id")
    status = (request.args.get("status") or "").strip()
    task_type = (request.args.get("task_type") or "").strip()
    limit = int(request.args.get("limit") or 100)

    conn = get_db()
    cur = conn.cursor()

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
        WHERE {' AND '.join(where)}
        ORDER BY id DESC
        LIMIT ?
    """
    params.append(limit)

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    return jsonify({"tasks": [_row_to_task(r) for r in rows]})


# -----------------------------
# Transitions
# -----------------------------

@tasks_bp.post("/tasks/<int:task_id>/confirm")
@require_login
def confirm_task(task_id: int):
    task = _get_task(task_id)
    if not task:
        return jsonify({"error": "not_found"}), 404

    cur_status = task["status"]

    if cur_status == "running":
        return jsonify({"error": "task_running", "task_id": task_id}), 409

    if cur_status == "confirmed":
        return jsonify({"ok": True, "task": task})

    if cur_status != "needs_confirmation":
        return _invalid_transition(task, "confirmed")

    t = _update_status_guarded(task_id, "needs_confirmation", "confirmed")
    if not t:
        task2 = _get_task(task_id)
        return _invalid_transition(task2 or task, "confirmed", "stale_state")

    return jsonify({"ok": True, "task": t})


@tasks_bp.post("/tasks/<int:task_id>/cancel")
@require_login
def cancel_task(task_id: int):
    task = _get_task(task_id)
    if not task:
        return jsonify({"error": "not_found"}), 404

    cur_status = task["status"]

    if cur_status == "running":
        return jsonify({"error": "task_running", "task_id": task_id}), 409

    if cur_status == "cancelled":
        return jsonify({"ok": True, "task": task})

    if cur_status == "completed":
        return _invalid_transition(task, "cancelled")

    if cur_status not in {"needs_confirmation", "confirmed", "dismissed"}:
        return _invalid_transition(task, "cancelled")

    t = _update_status_guarded(task_id, cur_status, "cancelled")
    if not t:
        task2 = _get_task(task_id)
        return _invalid_transition(task2 or task, "cancelled", "stale_state")

    return jsonify({"ok": True, "task": t})


@tasks_bp.post("/tasks/<int:task_id>/complete")
@require_login
def complete_task(task_id: int):
    task = _get_task(task_id)
    if not task:
        return jsonify({"error": "not_found"}), 404

    cur_status = task["status"]

    if cur_status == "running":
        return jsonify({"error": "task_running", "task_id": task_id}), 409

    if cur_status == "completed":
        return jsonify({"ok": True, "task": task})

    if cur_status != "confirmed":
        return _invalid_transition(task, "completed")

    if _is_recurring(task):
        return _invalid_transition(task, "completed", "recurring_cannot_complete")

    t = _update_status_guarded(task_id, "confirmed", "completed")
    if not t:
        task2 = _get_task(task_id)
        return _invalid_transition(task2 or task, "completed", "stale_state")

    return jsonify({"ok": True, "task": t})


@tasks_bp.post("/tasks/<int:task_id>/status")
@require_login
def set_task_status(task_id: int):
    """
    Pause / resume for recurring tasks only.
    Body: { status: "dismissed" | "confirmed" }
    """
    data = request.json or {}
    next_status = (data.get("status") or "").strip()

    if next_status not in {"dismissed", "confirmed"}:
        return jsonify({"error": "invalid_status"}), 400

    task = _get_task(task_id)
    if not task:
        return jsonify({"error": "not_found"}), 404

    cur_status = task["status"]

    if cur_status == "running":
        return jsonify({"error": "task_running", "task_id": task_id}), 409

    recurring = _is_recurring(task)

    # Resume
    if next_status == "confirmed":
        if cur_status == "confirmed":
            return jsonify({"ok": True, "task": task})
        if cur_status != "dismissed":
            return _invalid_transition(task, "confirmed")
        if not recurring:
            return _invalid_transition(task, "confirmed", "non_recurring_cannot_resume")

        t = _update_status_guarded(task_id, "dismissed", "confirmed")
        if not t:
            task2 = _get_task(task_id)
            return _invalid_transition(task2 or task, "confirmed", "stale_state")
        return jsonify({"ok": True, "task": t})

    # Pause
    if next_status == "dismissed":
        if cur_status == "dismissed":
            return jsonify({"ok": True, "task": task})
        if cur_status != "confirmed":
            return _invalid_transition(task, "dismissed")
        if not recurring:
            return _invalid_transition(task, "dismissed", "non_recurring_cannot_pause")

        t = _update_status_guarded(task_id, "confirmed", "dismissed")
        if not t:
            task2 = _get_task(task_id)
            return _invalid_transition(task2 or task, "dismissed", "stale_state")
        return jsonify({"ok": True, "task": t})

    return jsonify({"error": "invalid_status"}), 400

