# routes/projects_api.py
from flask import Blueprint, jsonify, session, request

from utils.db import get_db
from core.config import TMDB_CACHE
from services.playlists import list_playlist, remove_movie_from_playlist
from services.tmdb_service import tmdb_lookup_movie

# Blueprint for all project-related routes (and playlist helpers)
projects_bp = Blueprint("projects_api", __name__, url_prefix="/api")


def _ensure_user():
    """Return (user_id, error_response_or_None)."""
    user_id = session.get("user_id")
    if not user_id:
        return None, (jsonify({"error": "not_authenticated"}), 401)
    return user_id, None


# ---------------------------------------------------------------------------
# Projects CRUD
# ---------------------------------------------------------------------------


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
        ORDER BY id DESC
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()

    projects = []
    for r in rows:
        d = dict(r)
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

    try:
        cur.execute(
            """
            UPDATE projects
            SET name = ?
            WHERE id = ? AND user_id = ?
            """,
            (raw_name, project_id, user_id),
        )
    except Exception:
        try:
            cur.execute(
                """
                UPDATE projects
                SET title = ?
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
    """Delete a project and unassign its conversations."""
    user_id, err = _ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "not_found"}), 404

    cur.execute(
        """
        UPDATE conversations
        SET project_id = NULL
        WHERE project_id = ? AND user_id = ?
        """,
        (project_id, user_id),
    )

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


# ---------------------------------------------------------------------------
# Project notes
# ---------------------------------------------------------------------------


def _get_project_notes(user_id: int, project_id: int) -> str:
    """Return the notes content for a project (or empty string)."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    project_row = cur.fetchone()
    if not project_row:
        conn.close()
        raise ValueError("project_not_found")

    cur.execute(
        "SELECT content FROM project_notes WHERE user_id = ? AND project_id = ?",
        (user_id, project_id),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return ""
    return row["content"] or ""


def _set_project_notes(user_id: int, project_id: int, content: str) -> str:
    """Insert or update project_notes row and return final content."""
    content = content or ""
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    project_row = cur.fetchone()
    if not project_row:
        conn.close()
        raise ValueError("project_not_found")

    cur.execute(
        "SELECT id FROM project_notes WHERE user_id = ? AND project_id = ?",
        (user_id, project_id),
    )
    row = cur.fetchone()

    if row:
        cur.execute(
            """
            UPDATE project_notes
            SET content = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (content, row["id"]),
        )
    else:
        cur.execute(
            """
            INSERT INTO project_notes (user_id, project_id, content)
            VALUES (?, ?, ?)
            """,
            (user_id, project_id, content),
        )

    conn.commit()
    conn.close()
    return content


@projects_bp.get("/projects/<int:project_id>/notes")
def get_project_notes(project_id: int):
    user_id, err = _ensure_user()
    if err:
        return err

    try:
        content = _get_project_notes(user_id, project_id)
    except ValueError:
        return jsonify({"error": "not_found"}), 404

    return jsonify(
        {
            "project_id": project_id,
            "content": content,
        }
    )


@projects_bp.post("/projects/<int:project_id>/notes")
def update_project_notes(project_id: int):
    user_id, err = _ensure_user()
    if err:
        return err

    data = request.json or {}
    content = data.get("content") or ""

    try:
        final_content = _set_project_notes(user_id, project_id, content)
    except ValueError:
        return jsonify({"error": "not_found"}), 404

    return jsonify(
        {
            "project_id": project_id,
            "content": final_content,
        }
    )


# ---------------------------------------------------------------------------
# Playlist endpoints (multi-playlist + TMDb enrichment)
# ---------------------------------------------------------------------------


def _enrich_movie_item(item: dict) -> dict:
    """Use TMDb cache / lookup to add poster, year, ids, etc."""
    # Each stored movie is typically:
    # { "id": imdb_id, "name": "Title (Year)", "type": "movie", "tmdb_query": "Title Year" }
    our_id = item.get("id")
    enriched: dict = {}

    if our_id and our_id in TMDB_CACHE:
        enriched = TMDB_CACHE[our_id].copy()
    elif our_id:
        try:
            tmdb_bits = tmdb_lookup_movie(item.get("tmdb_query") or item.get("name") or "")
            enriched = tmdb_bits.copy()
            if enriched:
                TMDB_CACHE[our_id] = enriched
        except Exception as e:  # defensive
            print("TMDb enrich failed for", our_id, "->", e)
            enriched = {}

    # Build a merged view
    title = item.get("name") or item.get("title") or "Untitled"
    year = enriched.get("year")
    imdb_id = enriched.get("imdb_id") or our_id
    poster = enriched.get("poster")
    overview = enriched.get("overview")
    tmdb_id = enriched.get("tmdb_id")

    return {
        "title": title,
        "year": year,
        "imdb_id": imdb_id,
        "tmdb_id": tmdb_id,
        "poster": poster,
        "overview": overview,
        # Keep original bits in case the UI wants them later
        "raw": item,
    }


@projects_bp.get("/playlists/<string:slug>")
def get_playlist(slug: str):
    """Return a named playlist (christmas, thanksgiving, favorites, kids, etc.)."""
    user_id, err = _ensure_user()
    if err:
        return err

    movies = list_playlist(slug) or []
    items = [_enrich_movie_item(m) for m in movies]

    return jsonify(
        {
            "playlist": slug,
            "items": items,
        }
    )


@projects_bp.delete("/playlists/<string:slug>")
def remove_from_playlist(slug: str):
    """Remove a movie from a named playlist by title."""
    user_id, err = _ensure_user()
    if err:
        return err

    data = request.json or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title_required"}), 400

    reply = remove_movie_from_playlist(slug, title)

    return jsonify({"ok": True, "message": reply, "title": title, "playlist": slug})

