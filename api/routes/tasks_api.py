# api/routes/tasks_api.py

import json

from flask import Blueprint, jsonify, request

from utils.db import get_db
from utils.auth import require_login, get_current_user_id
from utils.errors import not_found, conflict, invalid_transition as err_invalid_transition

tasks_bp = Blueprint("tasks_api", __name__, url_prefix="/api")

TERMINAL_STATUSES = {"completed", "cancelled"}


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
    user_id = get_current_user_id()
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
    return err_invalid_transition(
        resource_id=(task or {}).get("id"),
        from_status=(task or {}).get("status"),
        to_status=to_status,
        reason=reason,
    )


def _update_status_guarded(task_id: int, from_status: str, to_status: str):
    """Atomic status transition."""
    user_id = get_current_user_id()
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
    user_id = get_current_user_id()
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


# -----------------------------
# Edit
# -----------------------------

@tasks_bp.patch("/tasks/<int:task_id>")
@require_login
def edit_task(task_id: int):
    """
    Edit task fields: title, scheduled_for.

    Body: { "title": "...", "scheduled_for": "ISO datetime" }
    Only provided fields are updated.
    Cannot edit a task that is currently running.
    """
    task = _get_task(task_id)
    if not task:
        return jsonify({"error": "not_found"}), 404

    if task["status"] == "running":
        return jsonify({"error": "task_running", "task_id": task_id}), 409

    data = request.json or {}
    new_title = data.get("title")
    new_scheduled_for = data.get("scheduled_for")

    if new_title is None and new_scheduled_for is None:
        return jsonify({"error": "no_fields_to_update"}), 400

    user_id = get_current_user_id()
    conn = get_db()
    cur = conn.cursor()

    # Update title if provided
    if new_title is not None:
        new_title = str(new_title).strip()
        if not new_title:
            conn.close()
            return jsonify({"error": "title_cannot_be_empty"}), 400

        cur.execute(
            "UPDATE detected_tasks SET title = ? WHERE id = ? AND user_id = ?",
            (new_title, task_id, user_id),
        )

    # Update scheduled_for if provided (stored in normalized_json)
    if new_scheduled_for is not None:
        normalized = task.get("normalized") or {}
        normalized["scheduled_for"] = new_scheduled_for

        cur.execute(
            "UPDATE detected_tasks SET normalized_json = ? WHERE id = ? AND user_id = ?",
            (json.dumps(normalized), task_id, user_id),
        )

    conn.commit()

    # Fetch updated task
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

    return jsonify({"ok": True, "task": _row_to_task(row) if row else None})


# -----------------------------
# Delete
# -----------------------------

@tasks_bp.delete("/tasks/<int:task_id>")
@require_login
def delete_task(task_id: int):
    """
    Permanently delete a task and its run history.

    Cannot delete a task that is currently running.
    """
    task = _get_task(task_id)
    if not task:
        return jsonify({"error": "not_found"}), 404

    if task["status"] == "running":
        return jsonify({"error": "task_running", "task_id": task_id}), 409

    user_id = get_current_user_id()
    conn = get_db()
    cur = conn.cursor()

    # Delete associated task_runs first (foreign key)
    cur.execute("DELETE FROM task_runs WHERE task_id = ?", (task_id,))

    # Delete the task itself
    cur.execute(
        "DELETE FROM detected_tasks WHERE id = ? AND user_id = ?",
        (task_id, user_id),
    )

    conn.commit()
    conn.close()

    return jsonify({"ok": True, "deleted": task_id})

