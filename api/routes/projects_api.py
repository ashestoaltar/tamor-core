# routes/projects_api.py
from flask import Blueprint, jsonify, session, request
from utils.db import get_db

projects_bp = Blueprint("projects_api", __name__, url_prefix="/api")


def _ensure_user():
    user_id = session.get("user_id")
    if not user_id:
        return None, (jsonify({"error": "not_authenticated"}), 401)
    return user_id, None


@projects_bp.get("/projects")
def list_projects():
    """Return all projects for the logged-in user."""
    user_id, err = _ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM projects
        WHERE user_id = ?
        ORDER BY updated_at DESC, created_at DESC
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()

    projects = []
    for r in rows:
        d = dict(r)
        # Support either "name" or "title" column for project label
        name = d.get("name") or d.get("title") or "Untitled Project"
        projects.append(
            {
                "id": d["id"],
                "name": name,
                "created_at": d.get("created_at"),
                "updated_at": d.get("updated_at"),
            }
        )

    return jsonify({"projects": projects})


@projects_bp.post("/projects")
def create_project():
    """Create a new project for the current user."""
    user_id, err = _ensure_user()
    if err:
        return err

    data = request.json or {}
    raw_name = (data.get("name") or "").strip()
    if not raw_name:
        return jsonify({"error": "name_required"}), 400

    conn = get_db()
    cur = conn.cursor()

    # Try inserting into "name", fall back to "title" if needed
    try:
        cur.execute(
            "INSERT INTO projects (user_id, name) VALUES (?, ?)",
            (user_id, raw_name),
        )
    except Exception:
        try:
            cur.execute(
                "INSERT INTO projects (user_id, title) VALUES (?, ?)",
                (user_id, raw_name),
            )
        except Exception as e2:
            conn.close()
            return jsonify({"error": str(e2)}), 500

    conn.commit()
    project_id = cur.lastrowid
    conn.close()

    return jsonify({"id": project_id, "name": raw_name})


@projects_bp.patch("/projects/<int:project_id>")
def rename_project(project_id):
    """Rename a project belonging to the current user."""
    user_id, err = _ensure_user()
    if err:
        return err

    data = request.json or {}
    raw_name = (data.get("name") or "").strip()
    if not raw_name:
        return jsonify({"error": "name_required"}), 400

    conn = get_db()
    cur = conn.cursor()

    # Try updating "name", fall back to "title"
    try:
        cur.execute(
            """
            UPDATE projects
            SET name = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (raw_name, project_id, user_id),
        )
    except Exception:
        try:
            cur.execute(
                """
                UPDATE projects
                SET title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
                """,
                (raw_name, project_id, user_id),
            )
        except Exception as e2:
            conn.close()
            return jsonify({"error": str(e2)}), 500

    if cur.rowcount == 0:
        conn.close()
        return jsonify({"error": "not_found"}), 404

    conn.commit()
    conn.close()

    return jsonify({"id": project_id, "name": raw_name})


@projects_bp.delete("/projects/<int:project_id>")
def delete_project(project_id):
    """
    Delete a project for the current user.

    Conversations under this project are NOT deleted;
    their project_id is set to NULL (Unassigned).
    """
    user_id, err = _ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()

    # Ensure project belongs to user
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "not_found"}), 404

    # Unassign conversations from this project
    cur.execute(
        """
        UPDATE conversations
        SET project_id = NULL
        WHERE project_id = ? AND user_id = ?
        """,
        (project_id, user_id),
    )

    # Delete project
    cur.execute(
        "DELETE FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )

    conn.commit()
    conn.close()

    return jsonify({"ok": True, "id": project_id})


@projects_bp.get("/projects/<int:project_id>/conversations")
def project_conversations(project_id):
    """List conversations under a specific project for the current user."""
    user_id, err = _ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()

    # Ensure project belongs to user
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        conn.close()
        return jsonify({"error": "not_found"}), 404

    cur.execute(
        """
        SELECT id, user_id, project_id, title, created_at, updated_at
        FROM conversations
        WHERE user_id = ? AND project_id = ?
        ORDER BY updated_at DESC
        """,
        (user_id, project_id),
    )
    rows = cur.fetchall()
    conn.close()

    convos = [dict(r) for r in rows]
    return jsonify({"conversations": convos})
