# api/routes/chat_api.py
import json
import re
from datetime import datetime, timezone
from typing import Any, Optional, Dict

from flask import Blueprint, jsonify, request, session

from utils.db import get_db
from utils.auth import require_login, get_current_user_id
from services.llm_service import get_llm_client, get_model_name
from core.prompt import build_system_prompt
from core.task_classifier import classify_task
from core.intent import parse_intent, execute_intent
from core.mode_router import route_mode
from core.task_normalizer import normalize_detected_task
from core.deterministic import (
    DeterministicResult,
    DeterministicQueries,
    format_deterministic_response,
)
from services.references.reference_parser import find_references as find_scripture_refs
from services.references.reference_service import ReferenceService
from services.library import LibraryContextService, LibrarySettingsService
from services.epistemic import process_response as epistemic_process, EpistemicResult

chat_bp = Blueprint("chat_api", __name__, url_prefix="/api")

# Lazy-loaded reference service for scripture context injection
_reference_service = None

# Lazy-loaded library context service
_library_context_service = None

# Lazy-loaded library settings service
_library_settings_service = None


def get_library_settings_service() -> LibrarySettingsService:
    """Get or create library settings service singleton."""
    global _library_settings_service
    if _library_settings_service is None:
        _library_settings_service = LibrarySettingsService()
    return _library_settings_service


def get_library_context_service() -> LibraryContextService:
    """Get or create library context service singleton."""
    global _library_context_service
    if _library_context_service is None:
        _library_context_service = LibraryContextService()
    return _library_context_service


def get_reference_service() -> ReferenceService:
    """Get or create reference service singleton."""
    global _reference_service
    if _reference_service is None:
        _reference_service = ReferenceService()
    return _reference_service


def inject_scripture_context(user_message: str, existing_context: str = "") -> str:
    """
    Detect scripture references in user message and inject actual text.

    Args:
        user_message: The user's message to check for references
        existing_context: Existing system prompt context to append to

    Returns:
        Updated context with scripture passages injected
    """
    try:
        refs = find_scripture_refs(user_message)
    except Exception:
        return existing_context

    if not refs:
        return existing_context

    # Limit to avoid context bloat
    refs = refs[:5]

    scripture_blocks = []
    ref_service = get_reference_service()

    for parsed in refs:
        try:
            results = ref_service.lookup(
                parsed.normalized,
                sources=["sword"],  # Prefer local SWORD for speed
                translations=["KJV"],
            )

            for ref in results[:2]:  # Limit per reference
                block = f"\n{ref.ref_string} ({ref.translation}):\n\"{ref.text}\""

                if ref.hebrew:
                    block += f"\n\nHebrew:\n{ref.hebrew}"

                scripture_blocks.append(block)

        except Exception:
            # Don't fail chat if reference lookup fails
            continue

    if not scripture_blocks:
        return existing_context

    scripture_context = """
[Scripture Context]
The user's message references the following passages:
{}

When discussing these passages:
- Quote the actual text when relevant
- Distinguish clearly between what the text says and your interpretation
- Note if translation differences are significant
[End Scripture Context]
""".format("\n".join(scripture_blocks))

    if existing_context:
        return existing_context + "\n\n" + scripture_context

    return scripture_context


def _build_library_context(
    user_message: str,
    project_id: Optional[int],
    existing_system_prompt: str,
    user_id: Optional[int] = None,
) -> str:
    """
    Build enhanced system prompt with library context.

    Finds relevant library content based on the user message and injects
    it into the system prompt for grounded LLM responses.
    Respects user's library settings.

    Args:
        user_message: The user's message
        project_id: Optional project ID for scoped search
        existing_system_prompt: The base system prompt to enhance
        user_id: User ID for settings lookup

    Returns:
        Enhanced system prompt with library context appended
    """
    try:
        # Check user settings
        if user_id:
            settings_service = get_library_settings_service()
            settings = settings_service.get_settings(user_id)

            if not settings.get("context_injection_enabled", True):
                return existing_system_prompt

            # Get settings values
            max_chunks = settings.get("context_max_chunks", 5)
            max_chars = settings.get("context_max_chars", 4000)
            min_score = settings.get("context_min_score", 0.4)
            scope = settings.get("context_scope", "all")

            # Adjust scope based on project context
            if scope == "project" and not project_id:
                scope = "library"  # Fallback if no project context

            # Determine effective project_id based on scope
            effective_project_id = project_id if scope in ("project", "all") else None
        else:
            # Default settings if no user_id
            max_chunks = 5
            max_chars = 4000
            min_score = 0.4
            effective_project_id = project_id

        ctx_service = get_library_context_service()

        # Get library context
        library_context = ctx_service.get_context_for_message(
            message=user_message,
            project_id=effective_project_id,
            max_chunks=max_chunks,
            max_chars=max_chars,
            min_score=min_score,
        )

        # If no relevant context found, return original prompt
        if not library_context["context_text"]:
            return existing_system_prompt

        # Build addition to system prompt
        context_addition = ctx_service.build_system_prompt_addition(
            context_text=library_context["context_text"],
            sources=library_context["sources"],
        )

        # Append to system prompt
        return existing_system_prompt + "\n\n" + context_addition

    except Exception:
        # Don't fail chat if library context fails
        return existing_system_prompt


def _get_library_context_text(
    user_message: str,
    project_id: Optional[int],
    user_id: Optional[int] = None,
) -> Optional[str]:
    """
    Get library context as formatted text for router path.

    Returns just the context text (without system prompt wrapper).
    Respects user's library settings.
    """
    try:
        # Check user settings
        if user_id:
            settings_service = get_library_settings_service()
            settings = settings_service.get_settings(user_id)

            if not settings.get("context_injection_enabled", True):
                return None

            max_chunks = settings.get("context_max_chunks", 5)
            max_chars = settings.get("context_max_chars", 4000)
            min_score = settings.get("context_min_score", 0.4)
            scope = settings.get("context_scope", "all")

            if scope == "project" and not project_id:
                scope = "library"

            effective_project_id = project_id if scope in ("project", "all") else None
        else:
            max_chunks = 5
            max_chars = 4000
            min_score = 0.4
            effective_project_id = project_id

        ctx_service = get_library_context_service()

        library_context = ctx_service.get_context_for_message(
            message=user_message,
            project_id=effective_project_id,
            max_chunks=max_chunks,
            max_chars=max_chars,
            min_score=min_score,
        )

        if not library_context["context_text"]:
            return None

        return ctx_service.build_system_prompt_addition(
            context_text=library_context["context_text"],
            sources=library_context["sources"],
        )

    except Exception:
        return None


CHAT_HISTORY_LIMIT = 24


def get_conversation_mode(conversation_id: int, user_id: int) -> str | None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT mode FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return row["mode"] if isinstance(row, dict) else row[0]


def set_conversation_mode(conversation_id: int, mode: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE conversations SET mode=? WHERE id=?", (mode, conversation_id))
    conn.commit()
    conn.close()


def get_or_create_conversation(user_id, conversation_id=None, title="New chat", project_id=None):
    conn = get_db()
    cur = conn.cursor()

    if conversation_id:
        cur.execute("SELECT id FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id))
        row = cur.fetchone()
        if row:
            cid = row["id"]
            conn.close()
            return cid

    cur.execute(
        """
        INSERT INTO conversations (user_id, project_id, title, created_at, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (user_id, project_id, title),
    )
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid


def add_message(conversation_id, sender, role, content, epistemic_json=None):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO messages (conversation_id, sender, role, content, epistemic_json, created_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (conversation_id, sender, role, content, epistemic_json),
    )
    mid = cur.lastrowid
    cur.execute("UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (conversation_id,))
    conn.commit()
    conn.close()
    return mid


def _build_epistemic_context(
    effective_mode: str,
    library_chunks: list = None,
    scripture_refs: list = None,
) -> Dict[str, Any]:
    """Build context for epistemic processing."""
    # Map mode to query type
    mode_to_query = {
        "Scholar": "theological",
        "Forge": "creative",
        "Path": "devotional",
        "Anchor": "practical",
        "Creative": "creative",
        "System": "system",
    }
    query_type = mode_to_query.get(effective_mode, "general")

    return {
        "query_type": query_type,
        "sources": [],
        "library_chunks": library_chunks or [],
        "references": scripture_refs or [],
        "user_prefers_accuracy": False,
    }


def _process_epistemic(
    response_text: str,
    epistemic_context: Dict[str, Any],
) -> tuple[str, Dict[str, Any]]:
    """
    Process response through epistemic pipeline.

    Returns:
        (processed_text, epistemic_metadata_dict)
    """
    try:
        result = epistemic_process(
            response_text=response_text,
            context=epistemic_context,
            skip_repair=False,
        )

        metadata = {
            "badge": result.metadata.badge,
            "answer_type": result.metadata.answer_type,
            "is_contested": result.metadata.is_contested,
            "contestation_level": result.metadata.contestation_level,
            "contested_domains": result.metadata.contested_domains,
            "alternative_positions": result.metadata.alternative_positions,
            "has_sources": result.metadata.has_sources,
            "sources": result.metadata.sources,
            "was_repaired": result.metadata.was_repaired,
        }

        return result.processed_text, metadata

    except Exception:
        # Don't fail chat if epistemic processing fails
        return response_text, None


def fetch_chat_history(conversation_id: int, limit: int = CHAT_HISTORY_LIMIT) -> list[dict]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT role, content
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (conversation_id, limit),
    )
    rows = cur.fetchall()
    conn.close()

    rows = list(reversed(rows or []))

    out: list[dict] = []
    for r in rows:
        role = (r["role"] or "").strip().lower()
        content = r["content"] or ""
        if not content.strip():
            continue
        if role not in ("user", "assistant"):
            continue
        out.append({"role": role, "content": content})
    return out


def initial_task_status(detected_task: dict | None) -> str:
    if not detected_task:
        return "needs_confirmation"

    title = (detected_task.get("title") or "").strip()
    low = title.lower()

    normalized = detected_task.get("normalized") or {}
    scheduled_for = normalized.get("scheduled_for")

    # Recurring language always requires confirmation for now
    if any(w in low for w in ("every ", "everyday", "daily", "weekly", "monthly", "each ")):
        return "needs_confirmation"

    if not scheduled_for:
        return "needs_confirmation"

    has_relative = " in " in low
    has_at = " at " in low
    has_time_token = re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", low) is not None
    has_colon_time = re.search(r"\b\d{1,2}:\d{2}\b", low) is not None

    if has_relative or has_at or has_time_token or has_colon_time:
        return "confirmed"

    return "needs_confirmation"


def _json_default(obj: Any):
    if isinstance(obj, datetime):
        return obj.astimezone(timezone.utc).isoformat(timespec="minutes")
    return str(obj)


def persist_detected_task(
    user_id: int,
    project_id: Optional[int],
    conversation_id: int,
    message_id: int,
    detected_task: Optional[dict],
) -> Optional[int]:
    if not detected_task or not message_id:
        return None

    task_type = detected_task.get("task_type") or detected_task.get("type")
    if not task_type:
        return None

    normalized = detected_task.get("normalized") or {}
    status = initial_task_status(detected_task)
    payload = detected_task.get("payload") or {}

    # Ensure scheduled_for is string if something upstream returned datetime
    sf = normalized.get("scheduled_for")
    if isinstance(sf, datetime):
        normalized["scheduled_for"] = sf.astimezone(timezone.utc).isoformat(timespec="minutes")

    payload_json = json.dumps(payload, default=_json_default, ensure_ascii=False)
    normalized_json = json.dumps(normalized, default=_json_default, ensure_ascii=False)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO detected_tasks (
            user_id, project_id, conversation_id, message_id,
            task_type, title, confidence, payload_json, normalized_json, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            project_id,
            conversation_id,
            message_id,
            task_type,
            detected_task.get("title"),
            detected_task.get("confidence"),
            payload_json,
            normalized_json,
            status,
        ),
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    return task_id


def _as_task_list(dt: Any) -> list[dict]:
    if not dt:
        return []
    if isinstance(dt, list):
        return [x for x in dt if isinstance(x, dict)]
    if isinstance(dt, dict):
        return [dt]
    return []


def _is_recurring_task(task: dict) -> bool:
    n = (task or {}).get("normalized") or {}
    return bool(n.get("recurrence") or n.get("rrule"))


def _task_key(task: dict) -> tuple:
    task_type = (task.get("task_type") or task.get("type") or "").strip().lower()
    title = (task.get("title") or "").strip().lower()
    return (task_type, title)


def _dedupe_detected_tasks(tasks: list[dict]) -> list[dict]:
    if not tasks:
        return []

    grouped: dict[tuple, list[dict]] = {}
    for t in tasks:
        if not isinstance(t, dict):
            continue
        grouped.setdefault(_task_key(t), []).append(t)

    kept: list[dict] = []
    for _k, bucket in grouped.items():
        recurring = [t for t in bucket if _is_recurring_task(t)]
        if recurring:
            kept.extend(recurring)
        else:
            kept.extend(bucket)

    kept_ids = {id(t) for t in kept}
    ordered = [t for t in tasks if id(t) in kept_ids]

    seen = set()
    final = []
    for t in ordered:
        if id(t) in seen:
            continue
        seen.add(id(t))
        final.append(t)
    return final


# ---------------------------------------------------------------------------
# Deterministic Query Handlers
# ---------------------------------------------------------------------------

def _handle_deterministic_query(
    message: str,
    user_id: int,
    project_id: Optional[int] = None,
) -> Optional[dict]:
    """
    Check if a message requires a deterministic answer and handle it.

    Returns a response dict if handled, None otherwise.

    IMPORTANT: This function enforces the rule that deterministic queries
    should NEVER fall through to the LLM. If we can't find an exact answer,
    we return a clear "not found" message.
    """
    msg = (message or "").lower().strip()

    # --- Task count query ---
    if DeterministicQueries.is_count_query(message) and "task" in msg:
        result = _count_user_tasks(user_id)
        return format_deterministic_response(result, "task_count")

    # --- Task list query ---
    if DeterministicQueries.is_list_query(message) and ("task" in msg or "reminder" in msg):
        result = _list_user_tasks(user_id)
        return format_deterministic_response(result, "task_list")

    # --- Project file count ---
    if DeterministicQueries.is_count_query(message) and "file" in msg and project_id:
        result = _count_project_files(project_id, user_id)
        return format_deterministic_response(result, "file_count")

    return None


def _count_user_tasks(user_id: int) -> DeterministicResult:
    """Count tasks for a user - deterministic query."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) as count
        FROM detected_tasks
        WHERE user_id = ? AND status NOT IN ('completed', 'cancelled')
        """,
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()

    count = row["count"] if row else 0
    if count == 0:
        return DeterministicResult.success("You have no active tasks or reminders.")
    elif count == 1:
        return DeterministicResult.success("You have 1 active task or reminder.")
    else:
        return DeterministicResult.success(f"You have {count} active tasks or reminders.")


def _list_user_tasks(user_id: int, limit: int = 10) -> DeterministicResult:
    """List tasks for a user - deterministic query."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, title, status, task_type, normalized_json
        FROM detected_tasks
        WHERE user_id = ? AND status NOT IN ('completed', 'cancelled')
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return DeterministicResult.success("You have no active tasks or reminders.")

    lines = ["Here are your active tasks:\n"]
    for r in rows:
        title = r["title"] or "(untitled)"
        status = r["status"] or "unknown"
        lines.append(f"• {title} [{status}]")

    return DeterministicResult.success("\n".join(lines))


def _count_project_files(project_id: int, user_id: int) -> DeterministicResult:
    """Count files in a project - deterministic query."""
    conn = get_db()
    cur = conn.cursor()

    # Verify project ownership
    cur.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not cur.fetchone():
        conn.close()
        return DeterministicResult.not_found("project", project_id)

    cur.execute(
        "SELECT COUNT(*) as count FROM project_files WHERE project_id = ?",
        (project_id,),
    )
    row = cur.fetchone()
    conn.close()

    count = row["count"] if row else 0
    if count == 0:
        return DeterministicResult.success("This project has no files.")
    elif count == 1:
        return DeterministicResult.success("This project has 1 file.")
    else:
        return DeterministicResult.success(f"This project has {count} files.")


@chat_bp.get("/mode/<mode_name>")
@require_login
def get_mode(mode_name):
    return jsonify({"ok": True, "mode": mode_name, "system_prompt": build_system_prompt(mode_name)})


@chat_bp.post("/chat")
@require_login
def chat():
    data = request.json or {}
    user_message = (data.get("message") or "").strip()

    requested_mode = (data.get("mode") or "").strip()
    allowed_modes = {"Scholar", "Forge", "Path", "Anchor", "Creative", "System", "Auto"}
    if requested_mode and requested_mode not in allowed_modes:
        requested_mode = "Auto"

    conversation_id = data.get("conversation_id")
    project_id = data.get("project_id")
    user_id = session.get("user_id")

    conv_id = get_or_create_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
        title=user_message[:80] if user_message else "New chat",
        project_id=project_id,
    )

    # Mode resolution (sticky)
    mode = requested_mode
    is_auto = (not mode) or (mode.lower() == "auto")
    if not is_auto:
        effective_mode = mode
        set_conversation_mode(conv_id, effective_mode)
    else:
        sticky = get_conversation_mode(conv_id, user_id)
        if sticky:
            effective_mode = sticky
        else:
            effective_mode, _conf = route_mode(user_message)
            set_conversation_mode(conv_id, effective_mode)

    # Timezone from browser (needed to interpret "9am" as 9am local)
    tz_name = (data or {}).get("tz_name")
    tz_offset_minutes = (data or {}).get("tz_offset_minutes")

    detected_raw = classify_task(user_message, tz_name=tz_name, tz_offset_minutes=tz_offset_minutes)
    detected_tasks = _as_task_list(detected_raw)

    normalized_tasks: list[dict] = []
    for t in detected_tasks:
        if not isinstance(t, dict):
            continue

        n = normalize_detected_task(t) or {}
        t2 = dict(t)
        if isinstance(n, dict) and n:
            t2["normalized"] = n

        t2["status"] = initial_task_status(t2)
        normalized_tasks.append(t2)

    detected_tasks = _dedupe_detected_tasks(normalized_tasks)
    detected_task = detected_tasks[0] if detected_tasks else None

    # Intent handling (explicit commands)
    intent = parse_intent(user_message)
    if intent:
        out = execute_intent(intent, user_id=user_id, conversation_id=conv_id)
        if out and out.get("handled"):
            reply_text = out.get("reply_text", "") or ""
            user_mid = add_message(conv_id, "user", "user", user_message)
            assistant_mid = add_message(conv_id, "tamor", "assistant", reply_text)
            return jsonify(
                {
                    "tamor": reply_text,
                    "conversation_id": conv_id,
                    "detected_task": None,
                    "message_ids": {"user": user_mid, "assistant": assistant_mid},
                    "meta": out.get("meta", {}),
                }
            )

    # Deterministic query handling (exact lookups - never fall through to LLM)
    deterministic_result = _handle_deterministic_query(
        user_message, user_id, project_id
    )
    if deterministic_result and deterministic_result.get("handled"):
        reply_text = deterministic_result.get("reply_text", "") or ""
        user_mid = add_message(conv_id, "user", "user", user_message)
        assistant_mid = add_message(conv_id, "tamor", "assistant", reply_text)
        return jsonify(
            {
                "tamor": reply_text,
                "conversation_id": conv_id,
                "detected_task": None,
                "message_ids": {"user": user_mid, "assistant": assistant_mid},
                "meta": deterministic_result.get("meta", {}),
            }
        )

    # Phase 6.2: Agent Router - check if multi-agent pipeline should handle this
    try:
        from services.router import route_chat, RequestContext as RouterContext
        import services.memory_service as mem_svc

        # Check for debug mode
        include_trace = (
            request.headers.get("X-Tamor-Debug") == "1"
            or request.args.get("debug") == "1"
        )

        # Get memories for context
        memories = []
        try:
            memories = mem_svc.get_memories_for_context(user_message, user_id, max_memories=5)
        except Exception:
            pass

        # Get scripture context if user references passages
        scripture_ctx = None
        try:
            scripture_ctx = inject_scripture_context(user_message)
        except Exception:
            pass

        # Get library context for relevant library content (Phase 7.3)
        library_ctx = None
        try:
            library_ctx = _get_library_context_text(user_message, project_id, user_id)
        except Exception:
            pass

        # Build router context
        history = fetch_chat_history(conv_id, limit=CHAT_HISTORY_LIMIT)
        router_ctx = RouterContext(
            user_message=user_message,
            conversation_id=conv_id,
            project_id=project_id,
            user_id=user_id,
            history=history,
            memories=memories,
            mode=effective_mode,
            scripture_context=scripture_ctx,
            library_context=library_ctx,
        )

        # Route the request
        router_result = route_chat(router_ctx, include_trace=include_trace)

        # If router handled it (not passthrough), return the result
        if router_result.handled_by not in ("llm_single_passthrough", "error"):
            reply_text = router_result.content

            # Phase 8.2: Epistemic processing
            epistemic_context = _build_epistemic_context(
                effective_mode=effective_mode,
                library_chunks=[],  # Router may have its own context
                scripture_refs=[],
            )
            processed_text, epistemic_metadata = _process_epistemic(
                reply_text, epistemic_context
            )
            epistemic_json = json.dumps(epistemic_metadata) if epistemic_metadata else None

            user_mid = add_message(conv_id, "user", "user", user_message)
            assistant_mid = add_message(
                conv_id, "tamor", "assistant", processed_text, epistemic_json
            )

            response_data = {
                "tamor": processed_text,
                "conversation_id": conv_id,
                "detected_task": detected_task,
                "message_ids": {"user": user_mid, "assistant": assistant_mid},
            }

            # Include epistemic metadata if available
            if epistemic_metadata:
                response_data["epistemic"] = epistemic_metadata

            # Include citations if present
            if router_result.citations:
                response_data["citations"] = router_result.citations

            # Include trace if requested
            if router_result.trace:
                response_data["router_trace"] = router_result.trace.to_dict()

            # Handle detected task persistence
            task_id = persist_detected_task(
                user_id=user_id,
                project_id=project_id,
                conversation_id=conv_id,
                message_id=user_mid,
                detected_task=detected_task,
            )
            if detected_task and task_id:
                detected_task["id"] = task_id
                detected_task["conversation_id"] = conv_id
                detected_task["message_id"] = user_mid
                response_data["detected_task"] = detected_task

            return jsonify(response_data)

    except Exception as e:
        # Log but don't fail - fall through to existing LLM path
        import logging
        logging.getLogger(__name__).warning(f"Router error, falling back to LLM: {e}")

    system_prompt = build_system_prompt(effective_mode)
    system_prompt += """
Capability note (Tamor app):
- This app supports reminders and tasks via an internal task system.
- If the user asks to "remind me" / set a reminder, do NOT say you cannot set reminders/alarms.
- Instead: If a reminder is detected and it needs confirmation, tell the user to confirm/cancel below. Otherwise, acknowledge that it's scheduled and can be managed below.
""".strip()

    # Inject relevant memories into context (Phase 6.1)
    try:
        import services.memory_service as mem_svc
        memories = mem_svc.get_memories_for_context(user_message, user_id, max_memories=5)
        memory_context = mem_svc.format_memories_for_prompt(memories)
        if memory_context:
            system_prompt += f"\n\n{memory_context}"
    except Exception:
        pass  # Don't fail chat if memory injection fails

    # Inject scripture context (Phase 3.5.5)
    try:
        scripture_context = inject_scripture_context(user_message)
        if scripture_context:
            system_prompt += f"\n\n{scripture_context}"
    except Exception:
        pass  # Don't fail chat if scripture injection fails

    # Inject library context (Phase 7.3)
    try:
        system_prompt = _build_library_context(
            user_message=user_message,
            project_id=project_id,
            existing_system_prompt=system_prompt,
            user_id=user_id,
        )
    except Exception:
        pass  # Don't fail chat if library context fails

    history = fetch_chat_history(conv_id, limit=CHAT_HISTORY_LIMIT)

    llm = get_llm_client()
    reply_text = llm.chat_completion(
        messages=[{"role": "system", "content": system_prompt}, *history, {"role": "user", "content": user_message}],
        model=get_model_name(),
    )

    # Safe cleanup: if already scheduled, strip any confirm/cancel prompting from the LLM text
    if detected_task:
        st = (detected_task.get("status") or "").lower()
        if st in ("confirmed", "scheduled"):
            text = reply_text or ""
            
            # If the model wrote "You can manage or ..." (often followed by confirm/cancel),
            # strip that entire sentence to avoid dangling "You can manage or".
            text = re.sub(
                r"(?is)\s*you can manage\s+or\b[^.?!]*(?:[.?!]|$)",
                " ",
                text,
            )


            # Remove common confirmation prompts (entire sentences)
            text = re.sub(r"(?is)\s*(?:please\s+)?confirm\b[^.?!]*(?:[.?!]|$)", " ", text)
            text = re.sub(r"(?is)\s*confirm\s+or\s+cancel\b[^.?!]*(?:[.?!]|$)", " ", text)
            text = re.sub(r"(?is)\s*you\s+can\s+(?:confirm|cancel)\b[^.?!]*(?:[.?!]|$)", " ", text)

            # Also remove the "if you want to confirm/cancel..." line (your original case)
            text = re.sub(r"(?im)^\s*if you want to (?:confirm|cancel)\b.*$", " ", text)

            # Clean whitespace
            cleaned = re.sub(r"\s{2,}", " ", text).strip()

            # Prevent awkward leftovers like "Please"
            if not cleaned or cleaned.lower() in ("please", "please.", "please!"):
                cleaned = "Got it."

            reply_text = cleaned
            
    if detected_task and (reply_text or "").strip().lower() == "got it.":
        reply_text = ""
       


    # Helper line (NO TIME HERE — pill is authoritative for local display)
    if detected_task:
        status = (detected_task.get("status") or "").lower()
        ttype = detected_task.get("task_type") or "task"

        # Ensure exactly ONE helper line
        line = "\n\n—\n"

        if detected_task.get("normalized", {}).get("recurrence"):
            line += "**Daily recurring reminder.**"
        else:
            line += f"**{ttype.capitalize()} detected.**"

        if status == "needs_confirmation":
            line += " Confirm or cancel below."
        else:
            line += " Reminder scheduled. You can manage it below."

        reply_text = (reply_text or "") + line

    # Phase 8.2: Epistemic processing
    epistemic_context = _build_epistemic_context(
        effective_mode=effective_mode,
        library_chunks=[],  # Could populate from library context if available
        scripture_refs=[],  # Could populate from scripture context if available
    )
    processed_text, epistemic_metadata = _process_epistemic(reply_text, epistemic_context)
    epistemic_json = json.dumps(epistemic_metadata) if epistemic_metadata else None

    user_mid = add_message(conv_id, "user", "user", user_message)
    assistant_mid = add_message(conv_id, "tamor", "assistant", processed_text, epistemic_json)

    task_id = persist_detected_task(
        user_id=user_id,
        project_id=project_id,
        conversation_id=conv_id,
        message_id=user_mid,
        detected_task=detected_task,
    )
    if detected_task and task_id:
        detected_task["id"] = task_id
        detected_task["conversation_id"] = conv_id
        detected_task["message_id"] = user_mid

    response_data = {
        "tamor": processed_text,
        "conversation_id": conv_id,
        "detected_task": detected_task,
        "message_ids": {"user": user_mid, "assistant": assistant_mid},
    }

    # Include epistemic metadata if available
    if epistemic_metadata:
        response_data["epistemic"] = epistemic_metadata

    return jsonify(response_data)

