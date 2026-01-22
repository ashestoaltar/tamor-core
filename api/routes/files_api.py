# api/routes/files_api.py
import os
import uuid
import json
from typing import Any, Dict, Optional, List

from flask import (
    Blueprint,
    jsonify,
    request,
    current_app,
    send_from_directory,
)

from utils.db import get_db
from utils.auth import ensure_user
from services.file_parsing import extract_text_from_file
from services.structured_parsing import extract_structure_for_mime

# LLM service for summarize / explain / search flows
from services.llm_service import get_llm_client, get_model_name, llm_is_configured

# Auto-insights service (Phase 4.1)
from services.insights_service import (
    generate_insights,
    get_cached_insights,
    invalidate_insights,
)

# File actions service (Phase 5.1)
from services.file_actions_service import (
    rewrite_file,
    generate_spec,
    extract_parameters,
)

# Transcript service (Phase 5.3)
from services.transcript_service import transcribe_file

# Optional: PDF text extraction
try:
    from PyPDF2 import PdfReader
except ImportError:  # still works without this, but PDFs won't be parsed as well
    PdfReader = None

files_bp = Blueprint("files_api", __name__, url_prefix="/api")


def _get_upload_root():
    """Return the absolute directory where uploaded files are stored."""
    upload_root = current_app.config.get("UPLOAD_ROOT")
    if not upload_root:
        upload_root = os.path.join(current_app.root_path, "uploads")
    os.makedirs(upload_root, exist_ok=True)
    return upload_root


def _allowed_file(filename: str) -> bool:
    """Basic safety check for filenames."""
    return "/" not in filename and "\\" not in filename


def _get_file_record_for_user(file_id: int, user_id: int):
    conn = get_db()
    import sqlite3

    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT pf.*
        FROM project_files pf
        JOIN projects p ON pf.project_id = p.id
        WHERE pf.id = ? AND p.user_id = ?
        """,
        (file_id, user_id),
    )
    row = cur.fetchone()
    conn.close()

    if row:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM project_files WHERE id = ?", (file_id,))
        row = cur.fetchone()

    return row




# ---------------------------------------------------------------------------
# File upload / download
# ---------------------------------------------------------------------------


@files_bp.post("/projects/<int:project_id>/files")
def upload_file(project_id: int):
    """
    Upload a file and associate it with a project.

    Expects multipart/form-data with a single "file" field.
    """
    user_id, err = ensure_user()
    if err:
        return err

    import sqlite3

    try:
        project_id = int(project_id)

        # 1) Basic form validation
        if "file" not in request.files:
            return (
                jsonify({"error": "no_file", "details": "Missing form field 'file'."}),
                400,
            )

        f = request.files["file"]
        if not f or f.filename == "":
            return jsonify({"error": "empty_filename"}), 400

        if not _allowed_file(f.filename):
            return jsonify({"error": "invalid_filename"}), 400

        # 2) Where to store it on disk
        upload_root = _get_upload_root()
        project_dir = os.path.join(upload_root, str(project_id))
        os.makedirs(project_dir, exist_ok=True)

        stored_name = f"{uuid.uuid4().hex}_{f.filename}"
        stored_name_rel = os.path.join(str(project_id), stored_name)
        full_path = os.path.join(upload_root, stored_name_rel)

        # 3) Save file
        f.save(full_path)

        mime_type = f.mimetype or ""
        try:
            size_bytes = os.path.getsize(full_path)
        except OSError:
            size_bytes = None

        # 4) Insert DB row (support both schemas: with and without size_bytes)
        conn = get_db()
        cur = conn.cursor()

        try:
            # Newer schema with size_bytes AND user_id
            cur.execute(
                """
                INSERT INTO project_files (project_id, user_id, filename, stored_name, mime_type, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (project_id, user_id, f.filename, stored_name_rel, mime_type, size_bytes),
            )
        except sqlite3.OperationalError as e:
            # Fallback for older schema without size_bytes column
            if "size_bytes" not in str(e):
                raise

            cur.execute(
                """
                INSERT INTO project_files (project_id, user_id, filename, stored_name, mime_type)
                VALUES (?, ?, ?, ?, ?)
                """,
                (project_id, user_id, f.filename, stored_name_rel, mime_type),
            )

        file_id = cur.lastrowid
        conn.commit()

        # 5) Clean JSON response the frontend expects
        return jsonify(
            {
                "id": file_id,
                "project_id": project_id,
                "filename": f.filename,
                "stored_name": stored_name_rel,
                "mime_type": mime_type,
                "size_bytes": size_bytes,
            }
        )

    except Exception as e:
        current_app.logger.exception("Error during file upload")
        return (
            jsonify(
                {
                    "error": "upload_failed",
                    "details": str(e),
                }
            ),
            500,
        )


@files_bp.get("/projects/<int:project_id>/files")
def list_project_files(project_id: int):
    """
    List files for a project, including cached parse metadata when available.
    """
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    conn.row_factory = None
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            pf.*,
            ftc.text AS cached_text,
            ftc.meta_json AS cached_meta_json,
            ftc.parser AS cached_parser
        FROM project_files pf
        JOIN projects p ON pf.project_id = p.id
        LEFT JOIN file_text_cache ftc ON ftc.file_id = pf.id
        WHERE pf.project_id = ? AND p.user_id = ?
        ORDER BY pf.id DESC
        """,
        (project_id, user_id),
    )
    rows = cur.fetchall()

    files = []

    # Same placeholder logic used by semantic search / knowledge graph
    placeholder_prefixes = (
        "This file is not a plain-text type.",
        "This file is a PDF, but the PDF parser",
        "This PDF appears to have no extractable text",
        "Error extracting text from PDF:",
        "Error reading file:",
    )

    colnames = [d[0] for d in cur.description]
    for row in rows:
        info = dict(zip(colnames, row))

        cached_text = (info.get("cached_text") or "").strip()
        meta_json = info.get("cached_meta_json")
        parser = info.get("cached_parser") or None

        has_text = False
        warnings: list[str] = []

        if meta_json:
            try:
                meta = json.loads(meta_json)
                w = meta.get("warnings") or []
                if isinstance(w, str):
                    warnings = [w]
                elif isinstance(w, list):
                    warnings = [str(x) for x in w]
            except Exception:
                warnings = []

        if cached_text:
            is_placeholder = cached_text.startswith(placeholder_prefixes)
            has_text = not is_placeholder

        files.append(
            {
                "id": info["id"],
                "project_id": info["project_id"],
                "filename": info["filename"],
                "stored_name": info["stored_name"],
                "mime_type": info.get("mime_type") or "",
                # may be None if not set; UI already tolerates that
                "size_bytes": info.get("size_bytes"),
                # new fields for UI badges
                "has_text": has_text,
                "parser": parser,
                "warnings": warnings,
            }
        )

    conn.close()
    return jsonify({"files": files})


@files_bp.get("/files/<int:file_id>/download")
def download_file(file_id: int):
    """
    Download the raw file.
    """
    user_id, err = ensure_user()
    if err:
        return err

    conn = get_db()
    conn.row_factory = None
    cur = conn.cursor()
    cur.execute(
        """
        SELECT pf.*, p.user_id
        FROM project_files pf
        JOIN projects p ON pf.project_id = p.id
        WHERE pf.id = ?
        """,
        (file_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "not_found"}), 404

    info = dict(zip([d[0] for d in cur.description], row))
    if info["user_id"] != user_id:
        return jsonify({"error": "forbidden"}), 403

    upload_root = _get_upload_root()
    stored_name_rel = info["stored_name"]
    full_path = os.path.join(upload_root, stored_name_rel)

    if not os.path.isfile(full_path):
        return jsonify({"error": "file_missing"}), 404

    directory = os.path.dirname(full_path)
    filename = os.path.basename(full_path)
    return send_from_directory(directory, filename, as_attachment=False)


# ---------------------------------------------------------------------------
# Centralized text extraction + caching
# ---------------------------------------------------------------------------


def get_or_extract_file_text_for_row(file_row):
    """
    Centralized helper to obtain (and cache) extracted text for a project_files row.

    Accepts a sqlite3.Row or dict with at least: id, stored_name, mime_type.
    Returns (text, meta_dict, parser_name).

    Phase 2.6: we also attach a lightweight "structure" object into meta_json:
      meta["structure"] = { ... }
    """
    conn = get_db()
    cur = conn.cursor()

    file_id = file_row["id"]

    # Try cache first
    try:
        cur.execute(
            "SELECT text, meta_json, parser FROM file_text_cache WHERE file_id = ?",
            (file_id,),
        )
        row = cur.fetchone()
    except Exception:
        row = None

    if row and row[0] is not None:
        cached_text = row[0] or ""
        meta_json = row[1]
        parser = row[2] or None
        meta: Optional[Dict[str, Any]] = None
        if meta_json:
            try:
                meta = json.loads(meta_json)
            except Exception:
                meta = None

        # Phase 2.6 backfill: if we have meta but no structure, compute once
        try:
            if isinstance(meta, dict) and "structure" not in meta:
                upload_root = _get_upload_root()
                stored_name_rel = file_row["stored_name"]
                try:
                    mime_type = file_row["mime_type"] or ""
                except KeyError:
                    mime_type = ""
                full_path = os.path.join(upload_root, stored_name_rel)

                structure = extract_structure_for_mime(mime_type or "", full_path)
                if structure is not None:
                    meta["structure"] = structure
                    cur.execute(
                        "UPDATE file_text_cache SET meta_json = ? WHERE file_id = ?",
                        (json.dumps(meta), file_id),
                    )
                    conn.commit()
        except Exception:
            # Structure backfill failures must not break basic flows
            pass

        return cached_text, meta, parser

    # Cache miss: extract from disk
    upload_root = _get_upload_root()
    stored_name_rel = file_row["stored_name"]
    try:
        mime_type = file_row["mime_type"] or ""
    except KeyError:
        mime_type = ""

    full_path = os.path.join(upload_root, stored_name_rel)
    if not os.path.isfile(full_path):
        return "", None, None

    result = extract_text_from_file(
        full_path, mime_type or "", os.path.basename(full_path)
    )
    text = (result.get("text") or "").strip()
    meta: Optional[Dict[str, Any]] = result.get("meta") or {}
    parser = result.get("parser") or None

    # Phase 2.6: attach structure on first parse
    try:
        structure = extract_structure_for_mime(mime_type or "", full_path)
    except Exception:
        structure = None

    if structure is not None:
        if not isinstance(meta, dict):
            meta = {}
        meta["structure"] = structure

    meta_json = None
    if meta:
        try:
            meta_json = json.dumps(meta)
        except TypeError:
            meta_json = None

    try:
        cur.execute(
            "INSERT OR REPLACE INTO file_text_cache (file_id, text, meta_json, parser) VALUES (?, ?, ?, ?)",
            (file_id, text, meta_json, parser),
        )
        conn.commit()
    except Exception:
        # Failing to cache should not break the main flow
        pass

    # Phase 4.1: Trigger auto-insights generation (non-blocking)
    try:
        project_id = file_row.get("project_id")
        filename = file_row.get("filename", "")
        if project_id and text and len(text.strip()) >= 100:
            generate_insights(
                file_id=file_id,
                project_id=project_id,
                text=text,
                filename=filename,
                mime_type=mime_type,
            )
    except Exception:
        # Insights generation failure should not break the main flow
        pass

    return text, meta, parser


def _read_file_text(full_path: str, mime_type: str | None):
    """
    Best-effort text extraction for LLM/search flows.

    This now delegates to services.file_parsing.extract_text_from_file so
    that all backends (plain text, PDF, Word, Excel, HTML, etc.) share one
    implementation.

    For backward compatibility, we still return a plain text string here
    and apply a conservative length cap. Placeholder messages for
    unsupported types and PDF errors are preserved inside the parsing
    service so that other modules can continue to detect them.
    """
    # Delegate to the centralized parsing service
    result = extract_text_from_file(
        full_path, mime_type or "", os.path.basename(full_path)
    )
    text = (result.get("text") or "").strip()

    # Conservative cap to keep responses / logs manageable.
    max_chars = 16000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[... truncated for size ...]\n"

    return text


def _build_structure_hint(meta: Optional[Dict[str, Any]]) -> str:
    """
    Turn meta["structure"] (if present) into a short natural-language hint
    for the LLM so summaries can be page / sheet / heading aware.
    """
    if not meta or not isinstance(meta, dict):
        return ""

    structure = meta.get("structure")
    if not isinstance(structure, dict):
        return ""

    t = structure.get("type")

    # PDF: mention pages by number and a few page headings
    if t == "pdf":
        pages = structure.get("pages") or []
        if not isinstance(pages, list) or not pages:
            return ""
        page_indices: List[str] = []
        heading_bits: List[str] = []
        for p in pages:
            if not isinstance(p, dict):
                continue
            idx = p.get("index")
            if idx is not None:
                page_indices.append(str(idx))
            heading = (p.get("heading") or "").strip()
            if heading:
                heading_bits.append(f"page {idx}: {heading}")
        if not page_indices:
            return ""
        joined_pages = ", ".join(page_indices)
        heading_hint = ""
        if heading_bits:
            heading_hint = " Example top headings: " + "; ".join(heading_bits[:5])
        return (
            "\n\nThe file is a PDF with pages "
            f"{joined_pages}. When summarizing, mention important content by page number."
            + heading_hint
        )

    # Excel: mention sheet names + headers
    if t == "xlsx":
        sheets = structure.get("sheets") or []
        if not isinstance(sheets, list) or not sheets:
            return ""
        names = [s.get("name", "?") for s in sheets if isinstance(s, dict)]
        names = [n for n in names if n]
        if not names:
            return ""
        names_str = ", ".join(names)

        # Optionally include a bit of header info
        header_bits: List[str] = []
        for s in sheets:
            if not isinstance(s, dict):
                continue
            sheet_name = s.get("name", "?")
            headers = s.get("headers") or []
            if headers:
                header_bits.append(f"{sheet_name}: {', '.join(headers[:8])}")
        header_hint = ""
        if header_bits:
            header_hint = (
                " Key sheets and their headers include: "
                + " | ".join(header_bits[:4])
            )

        return (
            "\n\nThe file is an Excel workbook with sheets: "
            f"{names_str}. Summarize per sheet and call out key headers."
            + header_hint
        )

    # DOCX: mention top headings
    if t == "docx":
        heads = structure.get("headings") or []
        if not isinstance(heads, list) or not heads:
            return ""
        texts = [
            h.get("text", "")
            for h in heads
            if isinstance(h, dict) and h.get("text")
        ]
        texts = [t for t in texts if t]
        if not texts:
            return ""
        top = texts[:5]
        joined = ", ".join(top)
        return (
            "\n\nThe file is a Word document with major headings: "
            f"{joined}. Use these headings to structure the summary."
        )

    return ""


@files_bp.get("/files/<int:file_id>/content")
def get_file_content(file_id: int):
    """
    Return text content for a file, mainly useful for debugging
    or future richer flows. The main LLM entrypoint is /files/<id>/summarize.
    """
    user_id, err = ensure_user()
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
            },
            "text": text,
        }
    )
    
@files_bp.get("/files/<int:file_id>/structure")
def get_file_structure(file_id: int):
    """
    Debug endpoint: return the parsed structure for a file
    (pages for PDF, sheet headers for XLSX, headings for DOCX).

    This does NOT return file text — only meta["structure"].
    """
    user_id, err = ensure_user()
    if err:
        return err

    row = _get_file_record_for_user(file_id, user_id)
    if not row:
        return jsonify({"error": "not_found"}), 404

    # Reuse centralized cached extractor
    text, meta, _parser = get_or_extract_file_text_for_row(row)

    structure = None
    if isinstance(meta, dict):
        structure = meta.get("structure")

    # Convert sqlite3.Row to a plain dict so .get() works
    info = dict(row)

    return jsonify(
        {
            "file_id": info["id"],
            "filename": info["filename"],
            "mime_type": info.get("mime_type"),
            "structure": structure,
        }
    )




# ---------------------------------------------------------------------------
# Summarize / QA within a file
# ---------------------------------------------------------------------------


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
        "result": "LLM answer here",
      }
    """
    user_id, err = ensure_user()
    if err:
        return err

    row = _get_file_record_for_user(file_id, user_id)
    if not row:
        return jsonify({"error": "not_found"}), 404

    # Convert sqlite3.Row to a real dict safely
    info = {key: row[key] for key in row.keys()}
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

    # Use cached extraction if available (now includes structure in meta)
    text, meta, _parser = get_or_extract_file_text_for_row(row)
    structure_hint = _build_structure_hint(meta)

    if not llm_is_configured():
        # Graceful fallback if LLM isn't configured on this server
        if task == "summary":
            pseudo = text[:2000]
            return jsonify(
                {
                    "file": {
                        "id": info["id"],
                        "filename": info["filename"],
                        "mime_type": mime_type,
                    },
                    "task": "summary",
                    "query": query,
                    "result": (
                        "LLM is not configured on this server, so this is a "
                        "truncated preview of the file instead of a real LLM summary:\n\n"
                        + pseudo
                    ),
                }
            )
        else:
            return (
                jsonify(
                    {
                        "error": "llm_not_configured",
                        "message": "LLM is not configured on this server.",
                    }
                ),
                501,
            )

    # Build the prompt based on task, with structure-aware hint
    if task == "summary":
        system_prompt = (
            "You are an assistant that summarizes files for the user. "
            "Provide a concise but detailed summary of the file content. "
            "If the file is multi-page (PDF) or multi-sheet (Excel), make "
            "clear references like 'On page 3' or 'In sheet Parts'."
        )
        user_prompt = (
            "Summarize the following file for the user."
            + structure_hint
            + "\n\nHere is the file content:\n\n"
            + text
        )
    else:  # qa
        if not query:
            return jsonify({"error": "missing_query"}), 400
        system_prompt = (
            "You are an assistant that answers questions about a file. "
            "If the answer is not in the file, say you don't know. "
            "If the file is multi-page or multi-sheet, cite the relevant "
            "page or sheet in your answer when possible."
        )
        user_prompt = (
            f"The user has this question about the file: {query}"
            + structure_hint
            + "\n\nAnswer using only the information in the file below:\n\n"
            + text
        )

    llm = get_llm_client()
    answer = llm.chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=get_model_name(),
    )

    return jsonify(
        {
            "file": {
                "id": info["id"],
                "filename": info["filename"],
                "mime_type": mime_type,
            },
            "task": task,
            "query": query,
            "result": answer,
        }
    )


# ---------------------------------------------------------------------------
# Project-wide file search
# ---------------------------------------------------------------------------


@files_bp.post("/projects/<int:project_id>/files/search")
def search_project_files(project_id: int):
    """
    Simple substring search across all text-like files in a project.

    This is separate from the semantic search endpoint, which uses embeddings.
    """
    user_id, err = ensure_user()
    if err:
        return err

    body = request.json or {}
    query = (body.get("query") or "").strip()
    if not query:
        return jsonify({"error": "missing_query"}), 400

    conn = get_db()
    conn.row_factory = None
    cur = conn.cursor()
    cur.execute(
        """
        SELECT pf.*
        FROM project_files pf
        JOIN projects p ON pf.project_id = p.id
        WHERE pf.project_id = ? AND p.user_id = ?
        ORDER BY pf.id DESC
        """,
        (project_id, user_id),
    )
    rows = cur.fetchall()

    upload_root = _get_upload_root()
    matches = []

    for row in rows:
        info = dict(zip([d[0] for d in cur.description], row))
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

        idx = text.lower().find(query.lower())
        if idx != -1:
            snippet_start = max(0, idx - 40)
            snippet_end = min(len(text), idx + len(query) + 40)
            snippet = text[snippet_start:snippet_end]
            matches.append(
                {
                    "file_id": info["id"],
                    "filename": info["filename"],
                    "mime_type": mime_type,
                    "snippet": snippet,
                }
            )

    return jsonify({"query": query, "matches": matches})


# ---------------------------------------------------------------------------
# Helper to verify message ownership (for potential future flows)
# ---------------------------------------------------------------------------


def _verify_message_belongs_to_user(message_id: int, user_id: int) -> bool:
    """
    Verify that a message belongs to the current user via its conversation.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT m.id
        FROM messages m
        JOIN conversations c ON m.conversation_id = c.id
        WHERE m.id = ? AND c.user_id = ?
        """,
        (message_id, user_id),
    )
    row = cur.fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# File Insights (Phase 4.1)
# ---------------------------------------------------------------------------


@files_bp.get("/files/<int:file_id>/insights")
def get_file_insights(file_id: int):
    """
    Get auto-generated insights for a file.

    If insights haven't been generated yet and the file has extracted text,
    they will be generated on-demand.

    Query params:
        force=true - Force regeneration even if cached
    """
    user_id, err = ensure_user()
    if err:
        return err

    # Verify file belongs to user
    file_row = _get_file_record_for_user(file_id, user_id)
    if not file_row:
        return jsonify({"error": "not_found"}), 404

    force = request.args.get("force", "").lower() == "true"

    # Check for cached insights first (unless forcing)
    if not force:
        cached = get_cached_insights(file_id)
        if cached:
            return jsonify(cached)

    # Try to generate insights
    # First, we need the extracted text
    text, meta, parser = get_or_extract_file_text_for_row(file_row)

    if not text or len(text.strip()) < 100:
        return jsonify({
            "file_id": file_id,
            "insights": None,
            "error": "insufficient_content",
            "details": "File has insufficient text content for insights generation",
        })

    # Generate insights (this will also cache them)
    result = generate_insights(
        file_id=file_id,
        project_id=file_row["project_id"],
        text=text,
        filename=file_row.get("filename", ""),
        mime_type=file_row.get("mime_type"),
        force=force,
    )

    if not result:
        return jsonify({
            "file_id": file_id,
            "insights": None,
            "error": "generation_failed",
            "details": "Failed to generate insights (LLM may not be configured)",
        })

    return jsonify(result)


# ---------------------------------------------------------------------------
# File Actions (Phase 5.1)
# ---------------------------------------------------------------------------


@files_bp.post("/files/<int:file_id>/rewrite")
def rewrite_file_content(file_id: int):
    """
    Rewrite/transform file content using LLM.

    Request JSON:
        {
            "mode": "simplify|expand|improve|restructure|technical|executive",
            "custom_instructions": "optional custom rewrite instructions"
        }

    Modes:
        - simplify: Make content clearer and more accessible
        - expand: Add more detail and explanation
        - improve: Fix issues and enhance quality (default)
        - restructure: Reorganize for better flow
        - technical: Rewrite for technical audience
        - executive: Create executive summary

    Returns the rewritten content without modifying the original file.
    """
    user_id, err = ensure_user()
    if err:
        return err

    file_row = _get_file_record_for_user(file_id, user_id)
    if not file_row:
        return jsonify({"error": "not_found"}), 404

    body = request.json or {}
    mode = body.get("mode", "improve")
    custom_instructions = body.get("custom_instructions")

    # Get file text
    text, meta, parser = get_or_extract_file_text_for_row(file_row)
    if not text:
        return jsonify({"error": "no_content", "details": "Could not extract text from file"}), 400

    result = rewrite_file(
        text=text,
        filename=file_row.get("filename", ""),
        mode=mode,
        custom_instructions=custom_instructions,
    )

    if result.get("error"):
        return jsonify({
            "file_id": file_id,
            "error": result["error"],
            "result": None,
        }), 400 if result["error"] == "insufficient_content" else 500

    return jsonify({
        "file_id": file_id,
        "filename": file_row.get("filename"),
        **result,
    })


@files_bp.post("/files/<int:file_id>/generate-spec")
def generate_spec_from_file(file_id: int):
    """
    Generate a specification document from file content.

    Request JSON:
        {
            "focus": "optional focus area (e.g., 'security', 'api', 'data model')"
        }

    Returns a structured specification document.
    """
    user_id, err = ensure_user()
    if err:
        return err

    file_row = _get_file_record_for_user(file_id, user_id)
    if not file_row:
        return jsonify({"error": "not_found"}), 404

    body = request.json or {}
    focus = body.get("focus")

    text, meta, parser = get_or_extract_file_text_for_row(file_row)
    if not text:
        return jsonify({"error": "no_content", "details": "Could not extract text from file"}), 400

    result = generate_spec(
        text=text,
        filename=file_row.get("filename", ""),
        focus=focus,
    )

    if result.get("error"):
        return jsonify({
            "file_id": file_id,
            "error": result["error"],
            "result": None,
        }), 400 if result["error"] == "insufficient_content" else 500

    return jsonify({
        "file_id": file_id,
        "filename": file_row.get("filename"),
        **result,
    })


@files_bp.post("/files/<int:file_id>/extract-parameters")
def extract_parameters_from_file(file_id: int):
    """
    Extract parameters and configuration values from file content.

    Request JSON:
        {
            "parameter_types": ["env", "config", "api"]  // optional filter
        }

    Returns structured list of parameters found in the file.
    """
    user_id, err = ensure_user()
    if err:
        return err

    file_row = _get_file_record_for_user(file_id, user_id)
    if not file_row:
        return jsonify({"error": "not_found"}), 404

    body = request.json or {}
    parameter_types = body.get("parameter_types")

    text, meta, parser = get_or_extract_file_text_for_row(file_row)
    if not text:
        return jsonify({"error": "no_content", "details": "Could not extract text from file"}), 400

    result = extract_parameters(
        text=text,
        filename=file_row.get("filename", ""),
        parameter_types=parameter_types,
    )

    if result.get("error"):
        return jsonify({
            "file_id": file_id,
            "error": result["error"],
            "parameters": None,
        }), 400 if result["error"] == "insufficient_content" else 500

    return jsonify({
        "file_id": file_id,
        "filename": file_row.get("filename"),
        **result,
    })


# ---------------------------------------------------------------------------
# File Transcription (Phase 5.3)
# ---------------------------------------------------------------------------


@files_bp.post("/files/<int:file_id>/transcribe")
def transcribe_uploaded_file(file_id: int):
    """
    Transcribe an uploaded audio or video file.

    Request JSON:
        {
            "model": "base",  // optional: tiny, base, small, medium, large-v2
            "language": "en"  // optional: auto-detected if not specified
        }

    Supported formats: mp3, mp4, wav, m4a, webm, ogg, flac, etc.

    Returns transcript with text and timestamped segments.
    """
    user_id, err = ensure_user()
    if err:
        return err

    file_row = _get_file_record_for_user(file_id, user_id)
    if not file_row:
        return jsonify({"error": "not_found"}), 404

    # Get file path
    upload_root = _get_upload_root()
    stored_name_rel = file_row["stored_name"]
    file_path = os.path.join(upload_root, stored_name_rel)

    if not os.path.exists(file_path):
        return jsonify({"error": "file_missing"}), 404

    body = request.json or {}
    model = body.get("model")
    language = body.get("language")

    result = transcribe_file(
        file_path=file_path,
        project_id=file_row["project_id"],
        file_id=file_id,
        filename=file_row.get("filename"),
        model_name=model,
        language=language,
    )

    if result.get("error"):
        return jsonify({
            "file_id": file_id,
            "error": result["error"],
        }), 500

    return jsonify({
        "file_id": file_id,
        "filename": file_row.get("filename"),
        **result,
    })
