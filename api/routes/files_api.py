# routes/files_api.py
import os
import uuid

from flask import (
    Blueprint,
    jsonify,
    session,
    request,
    current_app,
    send_from_directory,
)

from utils.db import get_db

# Optional: OpenAI for summarize / explain / search flows
try:
    from openai import OpenAI
except ImportError:  # lets the server run even if openai isn't installed yet
    OpenAI = None

# Optional: PDF text extraction
try:
    from PyPDF2 import PdfReader
except ImportError:  # still works without this, but PDFs won't be parsed
    PdfReader = None

files_bp = Blueprint("files_api", __name__, url_prefix="/api")


def _ensure_user():
    """Return (user_id, error_response_or_None)."""
    user_id = session.get("user_id")
    if not user_id:
        return None, (jsonify({"error": "not_authenticated"}), 401)
    return user_id, None


def _ensure_project_files_table():
    """Create project_files table if it does not already exist."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS project_files (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            project_id      INTEGER,
            conversation_id INTEGER,
            filename        TEXT NOT NULL,
            stored_name     TEXT NOT NULL,
            mime_type       TEXT,
            size_bytes      INTEGER,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def _get_upload_root():
    """Return absolute path to the upload root folder."""
    root = current_app.config.get("UPLOAD_FOLDER")
    if not root:
        # Fallback to ./uploads relative to api/
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        root = os.path.join(base_dir, "uploads")
    os.makedirs(root, exist_ok=True)
    return root


def _get_file_record_for_user(file_id: int, user_id: int):
    """Load a project_files row for a given user, or None."""
    _ensure_project_files_table()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, user_id, project_id, conversation_id, filename,
               stored_name, mime_type, size_bytes, created_at
        FROM project_files
        WHERE id = ? AND user_id = ?
        """,
        (file_id, user_id),
    )
    row = cur.fetchone()
    conn.close()
    return row


@files_bp.post("/files/upload")
def upload_file():
    """
    Upload a file and associate it with an optional project and/or conversation.

    Form-data fields:
      - file: the uploaded file (required)
      - project_id: optional project id
      - conversation_id: optional conversation id
    """
    user_id, err = _ensure_user()
    if err:
        return err

    _ensure_project_files_table()

    if "file" not in request.files:
        return jsonify({"error": "file_required"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "empty_filename"}), 400

    project_id = request.form.get("project_id") or None
    conversation_id = request.form.get("conversation_id") or None

    try:
        project_id = int(project_id) if project_id is not None else None
    except ValueError:
        return jsonify({"error": "invalid_project_id"}), 400

    try:
        conversation_id = (
            int(conversation_id) if conversation_id is not None else None
        )
    except ValueError:
        return jsonify({"error": "invalid_conversation_id"}), 400

    conn = get_db()
    cur = conn.cursor()

    # If a project is specified, make sure it belongs to this user
    if project_id is not None:
        cur.execute(
            "SELECT id FROM projects WHERE id = ? AND user_id = ?",
            (project_id, user_id),
        )
        if not cur.fetchone():
            conn.close()
            return jsonify({"error": "project_not_found"}), 404

    # If a conversation is specified, make sure it belongs to this user
    if conversation_id is not None:
        cur.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        if not cur.fetchone():
            conn.close()
            return jsonify({"error": "conversation_not_found"}), 404

    upload_root = _get_upload_root()

    # Build the folder path: uploads/<user>/<project or "general">
    sub_parts = [str(user_id)]
    if project_id is not None:
        sub_parts.append(f"project_{project_id}")
    else:
        sub_parts.append("general")

    user_folder = os.path.join(upload_root, *sub_parts)
    os.makedirs(user_folder, exist_ok=True)

    # Create a unique stored filename
    original_name = file.filename
    unique_prefix = uuid.uuid4().hex
    stored_filename = f"{unique_prefix}_{original_name}"
    full_path = os.path.join(user_folder, stored_filename)

    # Save file to disk
    file.save(full_path)
    size_bytes = os.path.getsize(full_path)
    mime_type = file.mimetype or None

    # Store relative path from upload_root
    stored_name_rel = os.path.relpath(full_path, upload_root)

    # Insert DB row
    cur.execute(
        """
        INSERT INTO project_files
            (user_id, project_id, conversation_id, filename, stored_name, mime_type, size_bytes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            project_id,
            conversation_id,
            original_name,
            stored_name_rel,
            mime_type,
            size_bytes,
        ),
    )
    conn.commit()
    file_id = cur.lastrowid

    cur.execute(
        """
        SELECT id, user_id, project_id, conversation_id, filename,
               stored_name, mime_type, size_bytes, created_at
        FROM project_files
        WHERE id = ?
        """,
        (file_id,),
    )
    row = cur.fetchone()
    conn.close()

    data = dict(row)
    return jsonify({"file": data})


@files_bp.get("/projects/<int:project_id>/files")
def list_project_files(project_id: int):
    """Return all files attached to a specific project for the current user."""
    user_id, err = _ensure_user()
    if err:
        return err

    _ensure_project_files_table()

    conn = get_db()
    cur = conn.cursor()

    # Make sure project belongs to user
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        conn.close()
        return jsonify({"error": "not_found"}), 404

    cur.execute(
        """
        SELECT id, user_id, project_id, conversation_id,
               filename, stored_name, mime_type, size_bytes, created_at
        FROM project_files
        WHERE user_id = ? AND project_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (user_id, project_id),
    )
    rows = cur.fetchall()
    conn.close()

    files = [dict(r) for r in rows]
    return jsonify({"project_id": project_id, "files": files})


@files_bp.get("/files/<int:file_id>")
def download_file(file_id: int):
    """
    Stream a file for download / preview.

    The file must belong to the current user.
    """
    user_id, err = _ensure_user()
    if err:
        return err

    row = _get_file_record_for_user(file_id, user_id)
    if not row:
        return jsonify({"error": "not_found"}), 404

    info = dict(row)
    upload_root = _get_upload_root()
    stored_name_rel = info["stored_name"]
    filename = info["filename"]
    mime_type = info.get("mime_type")

    full_path = os.path.join(upload_root, stored_name_rel)
    if not os.path.isfile(full_path):
        return jsonify({"error": "file_missing"}), 404

    directory = os.path.dirname(full_path)
    stored_basename = os.path.basename(full_path)

    # Use send_from_directory to avoid exposing full path
    return send_from_directory(
        directory,
        stored_basename,
        mimetype=mime_type,
        as_attachment=False,  # inline preview if browser supports it
        download_name=filename,
    )


@files_bp.delete("/files/<int:file_id>")
def delete_file(file_id: int):
    """
    Delete a file record and remove the underlying file from disk.
    """
    user_id, err = _ensure_user()
    if err:
        return err

    row = _get_file_record_for_user(file_id, user_id)
    if not row:
        return jsonify({"error": "not_found"}), 404

    info = dict(row)
    upload_root = _get_upload_root()
    stored_name_rel = info["stored_name"]
    full_path = os.path.join(upload_root, stored_name_rel)

    # Remove file from disk if it exists
    if os.path.isfile(full_path):
        try:
            os.remove(full_path)
        except OSError:
            # Don't fail the request just because the file is missing/locked
            pass

    # Delete DB row
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM project_files WHERE id = ? AND user_id = ?",
        (file_id, user_id),
    )
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "id": file_id})


def _extract_pdf_text(full_path: str) -> str:
    """Best-effort text extraction for PDFs using PyPDF2 if available."""
    if PdfReader is None:
        return (
            "This file is a PDF, but the PDF parser (PyPDF2) is not installed "
            "on the server yet. Install it with `pip install PyPDF2` to enable "
            "text extraction, summarization, and QA for PDFs."
        )

    try:
        with open(full_path, "rb") as f:
            reader = PdfReader(f)
            chunks = []
            for page in reader.pages:
                try:
                    t = page.extract_text() or ""
                except Exception:
                    t = ""
                chunks.append(t)
        text = "\n".join(chunks).strip()
        if not text:
            return (
                "This PDF appears to have no extractable text (it may be a scan). "
                "You can still open it directly from the file list."
            )
        return text
    except Exception as e:
        return f"Error extracting text from PDF: {e}"


def _read_file_text(full_path: str, mime_type: str | None):
    """
    Best-effort text extraction for LLM/search flows.

    - PDFs: try PyPDF2 (if available)
    - For text/* and common code/markdown extensions, read as UTF-8 (with errors ignored).
    - For everything else, return a helpful placeholder.
    """
    mime_type = (mime_type or "").lower()
    lower_path = full_path.lower()

    # PDFs
    if mime_type == "application/pdf" or lower_path.endswith(".pdf"):
        text = _extract_pdf_text(full_path)
    else:
        text_like = False
        if mime_type.startswith("text/"):
            text_like = True
        elif any(
            lower_path.endswith(ext)
            for ext in (
                ".txt",
                ".md",
                ".markdown",
                ".py",
                ".js",
                ".ts",
                ".jsx",
                ".tsx",
                ".json",
                ".html",
                ".css",
                ".csv",
                ".yml",
                ".yaml",
            )
        ):
            text_like = True

        if not text_like:
            return (
                "This file is not a plain-text type. "
                "You can still download and open it, but automated summarization "
                "and search will require a richer extractor (PDF/Word/etc.)."
            )

        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError:
            return "Error reading file contents."

    # To keep payloads safe, trim very long content
    max_chars = 16000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[... truncated for size ...]\n"

    return text


@files_bp.get("/files/<int:file_id>/content")
def get_file_content(file_id: int):
    """
    Return text content for a file, mainly useful for debugging
    or future richer flows. The main LLM entrypoint is /files/<id>/summarize.
    """
    user_id, err = _ensure_user()
    if err:
        return err

    row = _get_file_record_for_user(file_id, user_id)
    if not row:
        return jsonify({"error": "not_found"}), 404

    info = dict(row)
    upload_root = _get_upload_root()
    stored_name_rel = info["stored_name"]
    mime_type = info.get("mime_type") or ""

    full_path = os.path.join(upload_root, stored_name_rel)
    if not os.path.isfile(full_path):
        return jsonify({"error": "file_missing"}), 404

    text = _read_file_text(full_path, mime_type)

    return jsonify(
        {
            "file": {
                "id": info["id"],
                "project_id": info["project_id"],
                "conversation_id": info["conversation_id"],
                "filename": info["filename"],
                "mime_type": mime_type,
                "size_bytes": info["size_bytes"],
                "created_at": info["created_at"],
            },
            "text": text,
        }
    )


def _get_openai_client():
    """Return an OpenAI client or None if not configured."""
    if OpenAI is None:
        return None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


@files_bp.post("/files/<int:file_id>/summarize")
def summarize_or_qa_file(file_id: int):
    """
    Use the LLM to summarize / explain / search within a single file.

    Request JSON:
      {
        "task": "summary" | "qa",
        "query": "optional question when task == 'qa'"
      }

    Response JSON:
      {
        "file": { ... basic metadata ... },
        "task": "summary" | "qa",
        "query": "...",
        "result": "<LLM text>"
      }
    """
    user_id, err = _ensure_user()
    if err:
        return err

    row = _get_file_record_for_user(file_id, user_id)
    if not row:
        return jsonify({"error": "not_found"}), 404

    info = dict(row)
    upload_root = _get_upload_root()
    stored_name_rel = info["stored_name"]
    mime_type = info.get("mime_type") or ""

    full_path = os.path.join(upload_root, stored_name_rel)
    if not os.path.isfile(full_path):
        return jsonify({"error": "file_missing"}), 404

    body = request.json or {}
    task = (body.get("task") or "summary").lower()
    if task not in ("summary", "qa"):
        task = "summary"

    query = (body.get("query") or "").strip()

    text = _read_file_text(full_path, mime_type)

    client = _get_openai_client()
    if client is None:
        # Graceful fallback if OpenAI isn't configured on this server
        if task == "summary":
            pseudo = text[:2000]
            return jsonify(
                {
                    "file": {
                        "id": info["id"],
                        "filename": info["filename"],
                        "mime_type": mime_type,
                        "size_bytes": info["size_bytes"],
                        "created_at": info["created_at"],
                    },
                    "task": task,
                    "query": query,
                    "result": (
                        "OpenAI is not configured on this server, so here is a "
                        "truncated preview of the file instead:\n\n"
                        + pseudo
                    ),
                }
            )
        else:
            return jsonify(
                {
                    "file": {
                        "id": info["id"],
                        "filename": info["filename"],
                        "mime_type": mime_type,
                        "size_bytes": info["size_bytes"],
                        "created_at": info["created_at"],
                    },
                    "task": task,
                    "query": query,
                    "result": (
                        "OpenAI is not configured on this server, so I cannot run a "
                        "semantic search over this file yet. You can still open it "
                        "directly from the file list."
                    ),
                }
            )

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    if task == "summary":
        system_prompt = (
            "You are Tamor, an assistant helping the user understand a single file.\n"
            "You are given the file's text content. Provide a clear, concise summary "
            "that captures its structure and key points. Assume this is part of a "
            "larger engineering / study / project workspace."
        )
        user_prompt = (
            "Summarize the following file for the user. "
            "Highlight any sections that look like configuration, parameters, key decisions, "
            "or action items.\n\n"
            "--- FILE CONTENT START ---\n"
            f"{text}\n"
            "--- FILE CONTENT END ---"
        )
    else:  # task == "qa"
        system_prompt = (
            "You are Tamor, an assistant answering questions about a single file.\n"
            "You are given the file's text content as context. Answer ONLY from that text. "
            "If the answer isn't clearly present, say that you can't find it."
        )
        user_prompt = (
            "Here is the file content, followed by the user's question.\n\n"
            f"USER QUESTION: {query}\n\n"
            "--- FILE CONTENT START ---\n"
            f"{text}\n"
            "--- FILE CONTENT END ---"
        )

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        result_text = completion.choices[0].message.content.strip()
    except Exception as e:
        result_text = f"(Error calling OpenAI: {e})"

    return jsonify(
        {
            "file": {
                "id": info["id"],
                "filename": info["filename"],
                "mime_type": mime_type,
                "size_bytes": info["size_bytes"],
                "created_at": info["created_at"],
            },
            "task": task,
            "query": query,
            "result": result_text,
        }
    )


@files_bp.post("/projects/<int:project_id>/files/search")
def search_project_files(project_id: int):
    """
    Search all text-like files in a project for a simple substring query.

    Request JSON:
      { "query": "louver" }

    Response JSON:
      {
        "project_id": 1,
        "query": "louver",
        "hits": [
          {
            "file_id": 12,
            "filename": "PergolaLightingNotes.txt",
            "snippet": "... louver spacing is set to 150mm ...",
            "matches": 3,
            "mime_type": "text/plain",
            "size_bytes": 12345,
            "created_at": "2025-12-03 14:21:00"
          },
          ...
        ]
      }
    """
    user_id, err = _ensure_user()
    if err:
        return err

    body = request.json or {}
    query = (body.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query_required"}), 400

    _ensure_project_files_table()

    conn = get_db()
    cur = conn.cursor()

    # Verify project ownership
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    proj = cur.fetchone()
    if not proj:
        conn.close()
        return jsonify({"error": "not_found"}), 404

    cur.execute(
        """
        SELECT id, user_id, project_id, conversation_id,
               filename, stored_name, mime_type, size_bytes, created_at
        FROM project_files
        WHERE user_id = ? AND project_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (user_id, project_id),
    )
    rows = cur.fetchall()
    conn.close()

    upload_root = _get_upload_root()
    q_lower = query.lower()
    hits = []

    for r in rows:
        info = dict(r)
        stored_name_rel = info["stored_name"]
        mime_type = info.get("mime_type") or ""
        full_path = os.path.join(upload_root, stored_name_rel)

        if not os.path.isfile(full_path):
            continue

        text = _read_file_text(full_path, mime_type)

        # Skip placeholder / error texts so we don't match within them
        if text.startswith("This file is not a plain-text type."):
            continue
        if text.startswith("This file is a PDF, but the PDF parser"):
            continue
        if text.startswith("This PDF appears to have no extractable text"):
            continue
        if text.startswith("Error extracting text from PDF:"):
            continue
        if text.startswith("Error reading file contents."):
            continue

        text_lower = text.lower()
        idx = text_lower.find(q_lower)
        if idx == -1:
            continue

        # Count matches (simple substring counting)
        match_count = text_lower.count(q_lower)

        # Build a snippet around the first match
        window = 80
        start = max(0, idx - window)
        end = min(len(text), idx + len(query) + window)
        snippet = text[start:end].replace("\n", " ")

        if start > 0:
            snippet = "... " + snippet
        if end < len(text):
            snippet = snippet + " ..."

        hits.append(
            {
                "file_id": info["id"],
                "filename": info["filename"],
                "snippet": snippet,
                "matches": match_count,
                "mime_type": mime_type,
                "size_bytes": info["size_bytes"],
                "created_at": info["created_at"],
            }
        )

    return jsonify(
        {
            "project_id": project_id,
            "query": query,
            "hits": hits,
        }
    )

