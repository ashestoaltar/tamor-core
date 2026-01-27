from flask import Blueprint, jsonify, request

from utils.db import get_db
from utils.auth import ensure_user
from core.config import TMDB_CACHE
from services.playlists import list_playlist, remove_movie_from_playlist
from services.tmdb_service import tmdb_lookup_movie
from services.file_semantic_service import (
    semantic_search_project_files,
    summarize_project_files,
)
from services.knowledge_graph import (
    extract_symbols_for_project,
    query_symbol,
)
from services.embedding_cache import invalidate_cache_for_project
from services.insights_service import (
    get_project_insights,
    aggregate_project_insights,
    invalidate_project_insights,
)
from services.ghm.profile_loader import get_available_profiles, is_valid_profile
from services.reasoning_service import (
    analyze_file_relationships,
    detect_cross_file_contradictions,
    analyze_logic_flow,
    get_full_reasoning,
    invalidate_reasoning,
)
from services.pipeline_service import (
    get_pipeline,
    start_pipeline,
    advance_pipeline,
    abandon_pipeline,
    reset_pipeline,
    get_step_guidance,
    get_pipeline_summary,
    list_pipeline_templates,
)
from services.transcript_service import (
    transcribe_url,
    get_transcript,
    get_project_transcripts,
    delete_transcript,
    get_transcript_service_status,
)


# Blueprint for all project-related routes (and playlist helpers)
projects_bp = Blueprint("projects_api", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# Project template defaults
# ---------------------------------------------------------------------------


def _get_template_defaults(template: str) -> dict:
    """Get default settings for a project template."""
    templates = {
        "general": {"hermeneutic_mode": None, "profile": None},
        "scripture_study": {"hermeneutic_mode": "ghm", "profile": None},
        "theological_research": {"hermeneutic_mode": "ghm", "profile": None},
        "engineering": {"hermeneutic_mode": None, "profile": None},
        "writing": {"hermeneutic_mode": None, "profile": None},
    }
    return templates.get(template, {})


# ---------------------------------------------------------------------------
# Projects CRUD
# ---------------------------------------------------------------------------


@projects_bp.get("/projects")
def list_projects():
    """Return all projects for the logged-in user."""
    user_id, err = ensure_user()
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
                "hermeneutic_mode": d.get("hermeneutic_mode"),
                "profile": d.get("profile"),
                "created_at": d.get("created_at"),
                "updated_at": d.get("updated_at"),
            }
        )

    return jsonify({"projects": projects})


@projects_bp.post("/projects")
def create_project():
    """Create a new project for the current user."""
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}
    raw_name = (data.get("name") or "").strip()
    if not raw_name:
        return jsonify({"error": "name_required"}), 400

    hermeneutic_mode = data.get("hermeneutic_mode")
    profile = data.get("profile")
    template = data.get("template")

    # Apply template defaults if specified
    if template:
        defaults = _get_template_defaults(template)
        if hermeneutic_mode is None:
            hermeneutic_mode = defaults.get("hermeneutic_mode")
        if profile is None:
            profile = defaults.get("profile")

    # Validate hermeneutic_mode
    if hermeneutic_mode and hermeneutic_mode not in ("ghm", "none"):
        return jsonify({"error": "invalid hermeneutic_mode"}), 400

    # Validate profile
    if profile:
        if not is_valid_profile(profile):
            return jsonify({"error": "invalid profile", "detail": f"Profile '{profile}' not found"}), 400
        # Check if profile requires GHM
        from services.ghm.profile_loader import load_profile
        profile_data = load_profile(profile)
        if profile_data and profile_data.get('requires_ghm') and hermeneutic_mode != 'ghm':
            return jsonify({"error": "profile_requires_ghm", "detail": f"Profile '{profile}' requires GHM to be active"}), 400

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO projects (user_id, name, hermeneutic_mode, profile)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, raw_name, hermeneutic_mode, profile),
        )
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

    conn.commit()
    project_id = cur.lastrowid
    conn.close()

    return jsonify({
        "id": project_id,
        "name": raw_name,
        "hermeneutic_mode": hermeneutic_mode,
        "profile": profile,
    })


@projects_bp.patch("/projects/<int:project_id>")
def update_project(project_id):
    """Update a project belonging to the current user."""
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}

    updates = []
    params = []

    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            return jsonify({"error": "name_required"}), 400
        updates.append("name = ?")
        params.append(name)

    if "description" in data:
        updates.append("description = ?")
        params.append(data["description"])

    if "hermeneutic_mode" in data:
        mode = data["hermeneutic_mode"]
        if mode and mode not in ("ghm", "none"):
            return jsonify({"error": "invalid hermeneutic_mode"}), 400
        updates.append("hermeneutic_mode = ?")
        params.append(mode)

    if "profile" in data:
        prof = data["profile"]
        if prof and not is_valid_profile(prof):
            return jsonify({"error": "invalid profile", "detail": f"Profile '{prof}' not found"}), 400
        updates.append("profile = ?")
        params.append(prof)

    if not updates:
        return jsonify({"error": "no_fields_to_update"}), 400

    params.extend([project_id, user_id])

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        f"""
        UPDATE projects
        SET {', '.join(updates)}
        WHERE id = ? AND user_id = ?
        """,
        params,
    )

    if cur.rowcount == 0:
        conn.close()
        return jsonify({"error": "not_found"}), 404

    conn.commit()

    # Return updated project
    cur.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cur.fetchone()
    conn.close()

    d = dict(row)
    return jsonify({
        "id": d["id"],
        "name": d.get("name"),
        "hermeneutic_mode": d.get("hermeneutic_mode"),
        "profile": d.get("profile"),
        "created_at": d.get("created_at"),
    })


@projects_bp.delete("/projects/<int:project_id>")
def delete_project(project_id):
    """Delete a project and unassign its conversations."""
    user_id, err = ensure_user()
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

    # Invalidate caches for this project
    invalidate_cache_for_project(project_id)
    invalidate_project_insights(project_id)
    invalidate_reasoning(project_id)

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


@projects_bp.get("/projects/templates")
def get_project_templates():
    """Get available project templates."""
    templates = [
        {
            "id": "general",
            "name": "General",
            "description": "Standard project with no special constraints",
            "ghm_enabled": False,
        },
        {
            "id": "scripture_study",
            "name": "Scripture Study",
            "description": "Bible study with Global Hermeneutic Mode enabled",
            "ghm_enabled": True,
        },
        {
            "id": "theological_research",
            "name": "Theological Research",
            "description": "In-depth theological work with GHM and optional profiles",
            "ghm_enabled": True,
        },
        {
            "id": "engineering",
            "name": "Engineering",
            "description": "Technical projects - code, systems, design",
            "ghm_enabled": False,
        },
        {
            "id": "writing",
            "name": "Writing Project",
            "description": "General writing and content creation",
            "ghm_enabled": False,
        },
    ]
    return jsonify(templates)


@projects_bp.get("/projects/profiles")
def get_profiles():
    """Get available GHM profiles."""
    return jsonify(get_available_profiles())


@projects_bp.get("/projects/<int:project_id>/conversations")
def project_conversations(project_id):
    """List conversations under a specific project for the current user."""
    user_id, err = ensure_user()
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
# Project-wide semantic file search
# ---------------------------------------------------------------------------


@projects_bp.post("/projects/<int:project_id>/files/semantic-search")
def project_files_semantic_search(project_id: int):
    """
    Run a semantic search over all text-like files in a project.

    Request JSON:
      {
        "query": "Where do we set the louver spacing?",
        "top_k": 8   # optional
      }

    Response JSON:
      {
        "project_id": 1,
        "query": "...",
        "results": [ { chunk hit ... }, ... ],
        "answer": "LLM-grounded explanation..."
      }
    """
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query_required"}), 400

    raw_top_k = data.get("top_k")
    try:
        top_k = int(raw_top_k) if raw_top_k is not None else 8
    except (TypeError, ValueError):
        top_k = 8

    # Verify project ownership
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    proj = cur.fetchone()
    conn.close()
    if not proj:
        return jsonify({"error": "not_found"}), 404

    try:
        result = semantic_search_project_files(
            project_id=project_id,
            user_id=user_id,
            query=query,
            top_k=top_k,
            include_answer=True,
        )
    except Exception as e:
        print("Error during semantic file search:", e)
        return jsonify({"error": "semantic_search_failed", "detail": str(e)}), 500

    return jsonify(
        {
            "project_id": project_id,
            "query": query,
            "results": result.get("results", []),
            "answer": result.get("answer"),
        }
    )


@projects_bp.post("/projects/<int:project_id>/summarize")
def project_summarize(project_id: int):
    """
    Summarize all indexed file content in a project.

    Request JSON:
      {
        "prompt": "High-level overview focusing on constraints and config keys"
      }

    Response JSON:
      {
        "project_id": 1,
        "prompt": "…",
        "summary": "Markdown/text summary from LLM"
      }
    """
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}
    prompt = (data.get("prompt") or "").strip()

    # Verify project ownership
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    proj = cur.fetchone()
    conn.close()
    if not proj:
        return jsonify({"error": "not_found"}), 404

    try:
        summary = summarize_project_files(
            project_id=project_id,
            user_id=user_id,
            prompt=prompt or None,
        )
    except Exception as e:
        print("Error during project summarization:", e)
        return jsonify({"error": "summarize_failed", "detail": str(e)}), 500

    return jsonify(
        {
            "project_id": project_id,
            "prompt": prompt or None,
            "summary": summary,
        }
    )


# ---------------------------------------------------------------------------
# Phase 2.3 – Knowledge graph: extract + search symbols
# ---------------------------------------------------------------------------


@projects_bp.post("/projects/<int:project_id>/knowledge/extract")
def project_knowledge_extract(project_id: int):
    """
    Extract symbols / config keys / parameters from all text-like files
    in this project and store them in file_symbols.

    Response JSON (example):
      {
        "project_id": 1,
        "symbols_written": 42
      }
    """
    user_id, err = ensure_user()
    if err:
        return err

    # Verify project ownership
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    proj = cur.fetchone()
    conn.close()
    if not proj:
        return jsonify({"error": "not_found"}), 404

    try:
        # returns an int (total_symbols), not a dict
        symbols_written = extract_symbols_for_project(
            project_id=project_id,
            user_id=user_id,
        )
    except Exception as e:
        print("Error during knowledge extraction:", e)
        return jsonify(
            {"error": "knowledge_extract_failed", "detail": str(e)}
        ), 500

    # Build a simple, explicit response
    return jsonify(
        {
            "project_id": project_id,
            "symbols_written": symbols_written,
        }
    )



@projects_bp.post("/projects/<int:project_id>/knowledge/search")
def project_knowledge_search(project_id: int):
    """
    Fuzzy search for symbols / config keys within a project's extracted symbols.

    Request JSON:
      {
        "symbol": "WidthMM",
        "top_k": 25   # optional
      }

    Response JSON:
      {
        "project_id": 1,
        "query": "WidthMM",
        "hits": [
          {
            "id": ...,
            "project_id": ...,
            "file_id": ...,
            "symbol": "WidthMM",
            "line_number": 42,
            "snippet": "WidthMM = 3650",
            "filename": "config.json",
            "mime_type": "application/json",
            "score": 0.91
          },
          ...
        ]
      }
    """
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}
    symbol = (data.get("symbol") or data.get("query") or "").strip()
    if not symbol:
        return jsonify({"error": "symbol_required"}), 400

    raw_top_k = data.get("top_k")
    try:
        top_k = int(raw_top_k) if raw_top_k is not None else 25
    except (TypeError, ValueError):
        top_k = 25

    # Verify project ownership
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    proj = cur.fetchone()
    conn.close()
    if not proj:
        return jsonify({"error": "not_found"}), 404

    try:
        result = query_symbol(
            project_id=project_id,
            user_id=user_id,
            symbol=symbol,
            top_k=top_k,
        )
    except Exception as e:
        print("Error during knowledge search:", e)
        return jsonify({"error": "knowledge_search_failed", "detail": str(e)}), 500

    return jsonify(
        {
            "project_id": project_id,
            "query": result.get("query", symbol),
            "hits": result.get("hits", []),
        }
    )


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
    user_id, err = ensure_user()
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
    user_id, err = ensure_user()
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
# Project Insights (Phase 4.1)
# ---------------------------------------------------------------------------


@projects_bp.get("/projects/<int:project_id>/insights")
def get_insights_for_project(project_id: int):
    """
    Get auto-generated insights for all files in a project.

    Query params:
        aggregate=true - Return combined insights across all files (default)
        aggregate=false - Return individual insights per file
    """
    user_id, err = ensure_user()
    if err:
        return err

    # Verify project belongs to user
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    aggregate = request.args.get("aggregate", "true").lower() != "false"

    if aggregate:
        result = aggregate_project_insights(project_id, user_id)
        return jsonify({
            "project_id": project_id,
            "aggregated": True,
            **result,
        })
    else:
        insights_list = get_project_insights(project_id, user_id)
        return jsonify({
            "project_id": project_id,
            "aggregated": False,
            "files": insights_list,
        })


# ---------------------------------------------------------------------------
# Multi-File Reasoning (Phase 4.2)
# ---------------------------------------------------------------------------


@projects_bp.get("/projects/<int:project_id>/reasoning")
def get_project_reasoning(project_id: int):
    """
    Get full multi-file reasoning analysis for a project.

    Includes: relationships, contradictions, and logic flow analysis.

    Query params:
        force=true - Force regeneration even if cached
    """
    user_id, err = ensure_user()
    if err:
        return err

    # Verify project belongs to user
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    force = request.args.get("force", "").lower() == "true"

    result = get_full_reasoning(project_id, user_id, force)
    return jsonify(result)


@projects_bp.get("/projects/<int:project_id>/reasoning/relationships")
def get_file_relationships(project_id: int):
    """
    Analyze relationships and dependencies between project files.

    Query params:
        force=true - Force regeneration even if cached
    """
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    force = request.args.get("force", "").lower() == "true"

    result = analyze_file_relationships(project_id, user_id, force)
    return jsonify({"project_id": project_id, **result})


@projects_bp.get("/projects/<int:project_id>/reasoning/contradictions")
def get_cross_file_contradictions(project_id: int):
    """
    Detect contradictions and inconsistencies between project files.

    Query params:
        force=true - Force regeneration even if cached
    """
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    force = request.args.get("force", "").lower() == "true"

    result = detect_cross_file_contradictions(project_id, user_id, force)
    return jsonify({"project_id": project_id, **result})


@projects_bp.get("/projects/<int:project_id>/reasoning/logic-flow")
def get_logic_flow_analysis(project_id: int):
    """
    Analyze logical coherence and assumption coverage across files.

    Query params:
        force=true - Force regeneration even if cached
    """
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    force = request.args.get("force", "").lower() == "true"

    result = analyze_logic_flow(project_id, user_id, force)
    return jsonify({"project_id": project_id, **result})


# ---------------------------------------------------------------------------
# Project Pipelines (Phase 5.2)
# ---------------------------------------------------------------------------


@projects_bp.get("/pipelines")
def list_pipelines():
    """List all available pipeline templates."""
    templates = list_pipeline_templates()
    return jsonify({"pipelines": templates})


@projects_bp.get("/projects/<int:project_id>/pipeline")
def get_project_pipeline(project_id: int):
    """Get current pipeline status for a project."""
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    pipeline = get_pipeline(project_id)
    if not pipeline:
        return jsonify({
            "project_id": project_id,
            "pipeline": None,
            "message": "No active pipeline for this project",
        })

    return jsonify({"project_id": project_id, "pipeline": pipeline})


@projects_bp.post("/projects/<int:project_id>/pipeline/start")
def start_project_pipeline(project_id: int):
    """
    Start a new pipeline for a project.

    Request JSON:
        {"pipeline_type": "research|writing|study|long_form"}
    """
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    body = request.json or {}
    pipeline_type = body.get("pipeline_type")

    if not pipeline_type:
        templates = list_pipeline_templates()
        return jsonify({
            "error": "missing_pipeline_type",
            "available_pipelines": templates,
        }), 400

    result = start_pipeline(project_id, pipeline_type)
    if result.get("error"):
        return jsonify(result), 400

    return jsonify({"project_id": project_id, **result})


@projects_bp.post("/projects/<int:project_id>/pipeline/advance")
def advance_project_pipeline(project_id: int):
    """
    Advance pipeline to next step.

    Request JSON:
        {"notes": "optional notes about completed step"}
    """
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    body = request.json or {}
    notes = body.get("notes")

    result = advance_pipeline(project_id, notes)
    if result.get("error"):
        return jsonify(result), 400

    return jsonify({"project_id": project_id, **result})


@projects_bp.post("/projects/<int:project_id>/pipeline/abandon")
def abandon_project_pipeline(project_id: int):
    """Abandon/cancel current pipeline."""
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    result = abandon_pipeline(project_id)
    if result.get("error"):
        return jsonify(result), 400

    return jsonify(result)


@projects_bp.post("/projects/<int:project_id>/pipeline/reset")
def reset_project_pipeline(project_id: int):
    """Reset pipeline to first step."""
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    result = reset_pipeline(project_id)
    if result.get("error"):
        return jsonify(result), 400

    return jsonify({"project_id": project_id, **result})


@projects_bp.get("/projects/<int:project_id>/pipeline/guidance")
def get_pipeline_guidance(project_id: int):
    """Get detailed guidance for current pipeline step."""
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    result = get_step_guidance(project_id, user_id)
    if result.get("error"):
        return jsonify(result), 400

    return jsonify({"project_id": project_id, **result})


@projects_bp.get("/projects/<int:project_id>/pipeline/summary")
def get_pipeline_progress_summary(project_id: int):
    """Get LLM-generated summary of pipeline progress."""
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    result = get_pipeline_summary(project_id, user_id)
    return jsonify({"project_id": project_id, **result})


# ---------------------------------------------------------------------------
# Transcripts (Phase 5.3)
# ---------------------------------------------------------------------------


@projects_bp.get("/transcripts/status")
def get_transcripts_status():
    """Check if transcript service is available."""
    status = get_transcript_service_status()
    return jsonify(status)


@projects_bp.post("/projects/<int:project_id>/transcribe-url")
def transcribe_from_url(project_id: int):
    """
    Download and transcribe audio from YouTube or other URL.

    Request JSON:
        {
            "url": "https://youtube.com/watch?v=...",
            "model": "base",  // optional: tiny, base, small, medium, large-v2
            "language": "en"  // optional: auto-detected if not specified
        }

    Returns transcript with text and timestamped segments.
    """
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    body = request.json or {}
    url = body.get("url", "").strip()

    if not url:
        return jsonify({"error": "missing_url"}), 400

    model = body.get("model")
    language = body.get("language")

    result = transcribe_url(
        url=url,
        project_id=project_id,
        model_name=model,
        language=language,
    )

    if result.get("error"):
        return jsonify(result), 500

    return jsonify({"project_id": project_id, **result})


@projects_bp.get("/projects/<int:project_id>/transcripts")
def list_project_transcripts(project_id: int):
    """List all transcripts for a project."""
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    transcripts = get_project_transcripts(project_id)
    return jsonify({"project_id": project_id, "transcripts": transcripts})


@projects_bp.get("/projects/<int:project_id>/transcripts/<int:transcript_id>")
def get_project_transcript(project_id: int, transcript_id: int):
    """Get a specific transcript with full text and segments."""
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    transcript = get_transcript(transcript_id, project_id)
    if not transcript:
        return jsonify({"error": "transcript_not_found"}), 404

    return jsonify(transcript)


@projects_bp.delete("/projects/<int:project_id>/transcripts/<int:transcript_id>")
def delete_project_transcript(project_id: int, transcript_id: int):
    """Delete a transcript."""
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    deleted = delete_transcript(transcript_id, project_id)
    if not deleted:
        return jsonify({"error": "transcript_not_found"}), 404

    return jsonify({"deleted": True, "transcript_id": transcript_id})


@projects_bp.get("/projects/<int:project_id>/transcripts/<int:transcript_id>/export")
def export_project_transcript(project_id: int, transcript_id: int):
    """Export a transcript as PDF."""
    from flask import Response
    from fpdf import FPDF
    import io
    import json

    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        return jsonify({"error": "not_found"}), 404

    transcript = get_transcript(transcript_id, project_id)
    if not transcript:
        return jsonify({"error": "transcript_not_found"}), 404

    # Create PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title
    pdf.set_font("Helvetica", "B", 16)
    title = transcript.get("title", "Transcript")
    # Handle encoding - FPDF uses latin-1 by default
    safe_title = title.encode("latin-1", "replace").decode("latin-1")
    pdf.cell(0, 10, safe_title, ln=True)

    # Metadata
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    meta_parts = []
    if transcript.get("duration_seconds"):
        mins = int(transcript["duration_seconds"] // 60)
        secs = int(transcript["duration_seconds"] % 60)
        meta_parts.append(f"Duration: {mins}:{secs:02d}")
    if transcript.get("language"):
        meta_parts.append(f"Language: {transcript['language'].upper()}")
    if transcript.get("source_url"):
        meta_parts.append(f"Source: {transcript['source_url'][:60]}...")
    if meta_parts:
        pdf.cell(0, 6, " | ".join(meta_parts), ln=True)
    pdf.ln(5)

    # Transcript content
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 11)

    segments = transcript.get("segments", [])
    if segments:
        for seg in segments:
            start = seg.get("start", 0)
            mins = int(start // 60)
            secs = int(start % 60)
            timestamp = f"[{mins}:{secs:02d}]"

            text = seg.get("text", "").strip()
            safe_text = text.encode("latin-1", "replace").decode("latin-1")

            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(20, 6, timestamp)
            pdf.set_font("Helvetica", "", 11)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 6, safe_text)
            pdf.ln(2)
    else:
        # Fallback to full text if no segments
        text = transcript.get("text", "No transcript text available.")
        safe_text = text.encode("latin-1", "replace").decode("latin-1")
        pdf.multi_cell(0, 6, safe_text)

    # Output PDF
    pdf_bytes = bytes(pdf.output())
    safe_filename = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)[:50]

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}.pdf"'
        },
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
            tmdb_bits = tmdb_lookup_movie(
                item.get("tmdb_query") or item.get("name") or ""
            )
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
    user_id, err = ensure_user()
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
    user_id, err = ensure_user()
    if err:
        return err

    data = request.json or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title_required"}), 400

    reply = remove_movie_from_playlist(slug, title)

    return jsonify({"ok": True, "message": reply, "title": title, "playlist": slug})

