# api/routes/chat_api.py
import json
import re
from functools import wraps
from datetime import datetime, timezone
from typing import Any, Optional

from flask import Blueprint, jsonify, request, session
from openai import OpenAI

from utils.db import get_db
from core.prompt import build_system_prompt
from core.task_classifier import classify_task
from core.intent import parse_intent, execute_intent


chat_bp = Blueprint("chat_api", __name__, url_prefix="/api")

client = OpenAI()
OPENAI_MODEL = "gpt-4.1-mini"

# How many prior turns to include in the LLM context (tune later)
CHAT_HISTORY_LIMIT = 24


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "not_authenticated"}), 401
        return fn(*args, **kwargs)

    return wrapper


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


def add_message(conversation_id, sender, role, content):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO messages (conversation_id, sender, role, content, created_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (conversation_id, sender, role, content),
    )
    mid = cur.lastrowid
    cur.execute("UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (conversation_id,))
    conn.commit()
    conn.close()
    return mid


def fetch_chat_history(conversation_id: int, limit: int = CHAT_HISTORY_LIMIT) -> list[dict]:
    """
    Load the most recent messages for this conversation from the DB and format them
    for OpenAI Chat Completions.

    IMPORTANT:
    - We include BOTH user and assistant roles.
    - We return chronological order.
    """
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

    # reverse into chronological order
    rows = list(reversed(rows or []))

    out: list[dict] = []
    for r in rows:
        role = (r["role"] or "").strip().lower()
        content = r["content"] or ""
        if not content.strip():
            continue
        # Only pass roles OpenAI expects
        if role not in ("user", "assistant"):
            continue
        out.append({"role": role, "content": content})
    return out


def initial_task_status(detected_task: dict | None) -> str:
    """
    Confirmation policy (conservative):
    - Recurring language => needs_confirmation
    - No scheduled_for => needs_confirmation
    - Explicit one-shot time ("in 10 minutes", "tomorrow at 3pm", "at 8:30") => confirmed
    - Vague dates like "tomorrow" (no explicit time) => needs_confirmation
    """
    if not detected_task:
        return "needs_confirmation"

    title = (detected_task.get("title") or "").strip()
    low = title.lower()

    normalized = detected_task.get("normalized") or {}
    scheduled_for = normalized.get("scheduled_for")

    # 1) Always require confirmation for recurring-ish phrases (even before we add RRULE parsing)
    if any(w in low for w in ("every ", "daily", "weekly", "monthly", "each ", "everyday")):
        return "needs_confirmation"

    # 2) If we don't have a concrete time, require confirmation
    if not scheduled_for:
        return "needs_confirmation"

    # 3) Require explicit time indicators for auto-confirm (prevents "tomorrow" auto-confirming)
    has_relative = " in " in low  # e.g. "in 10 minutes"
    has_at = " at " in low        # e.g. "tomorrow at 3pm"
    has_time_token = re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", low) is not None  # 3pm, 3:15pm
    has_colon_time = re.search(r"\b\d{1,2}:\d{2}\b", low) is not None  # 15:30, 8:05

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
    """
    Persist a detected task into detected_tasks and return the inserted task id.

    Invariants:
    - If detected_task is None, do nothing.
    - Always persist valid JSON strings (never NULL) for payload_json/normalized_json.
    - Status defaults to needs_confirmation when missing.
    """
    if not detected_task or not message_id:
        return None

    task_type = detected_task.get("task_type") or detected_task.get("type")
    if not task_type:
        return None

    normalized = detected_task.get("normalized") or {}
    status = initial_task_status(detected_task)
    payload = detected_task.get("payload") or {}

    # Ensure scheduled_for is string if classifier returned datetime
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
            user_id,
            project_id,
            conversation_id,
            message_id,
            task_type,
            title,
            confidence,
            payload_json,
            normalized_json,
            status
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


def _format_when(iso_str: str | None) -> str | None:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.astimezone().strftime("%a %b %d, %I:%M %p")
    except Exception:
        return iso_str


@chat_bp.get("/mode/<mode_name>")
@require_login
def get_mode(mode_name):
    return jsonify(
        {
            "ok": True,
            "mode": mode_name,
            "system_prompt": build_system_prompt(mode_name),
        }
    )


@chat_bp.post("/chat")
@require_login
def chat():
    data = request.json or {}
    user_message = (data.get("message") or "").strip()
    mode = data.get("mode", "Scholar")
    conversation_id = data.get("conversation_id")
    project_id = data.get("project_id")

    user_id = session.get("user_id")

    conv_id = get_or_create_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
        title=user_message[:80] if user_message else "New chat",
        project_id=project_id,
    )

    detected_task = classify_task(user_message)

    if detected_task:
        normalized = detected_task.get("normalized") or {}

        # HARDEN datetime
        sf = normalized.get("scheduled_for")
        if isinstance(sf, datetime):
            normalized["scheduled_for"] = sf.astimezone(timezone.utc).isoformat(timespec="minutes")

        for k, v in list(normalized.items()):
            if isinstance(v, datetime):
                normalized[k] = v.astimezone(timezone.utc).isoformat(timespec="minutes")

    # --- Intent handling (playlist commands, TMDb disambiguation, etc.) ---
    intent = parse_intent(user_message)
    if intent:
        out = execute_intent(intent, user_id=user_id, conversation_id=conv_id)
        if out and out.get("handled"):
            reply_text = out.get("reply_text", "") or ""

            # ✅ persist chat history even when handled by intent
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

        detected_task["normalized"] = normalized
        detected_task["status"] = initial_task_status(detected_task)

    system_prompt = build_system_prompt(mode)
    system_prompt += """

Capability note (Tamor app):
- This app supports reminders and tasks via an internal task system.
- If the user asks to "remind me" / set a reminder, do NOT say you cannot set reminders/alarms.
- Instead: If a reminder is detected and it needs confirmation, tell the user to confirm/cancel below. Otherwise, acknowledge that it’s scheduled and can be managed below.
""".strip()

    # ✅ Include recent conversation history so the model has context
    history = fetch_chat_history(conv_id, limit=CHAT_HISTORY_LIMIT)

    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": user_message},
        ],
    )

    # Ensure detected_task carries the final status for downstream UX copy
    if detected_task and not detected_task.get("status"):
        detected_task["status"] = initial_task_status(detected_task)

    reply_text = completion.choices[0].message.content or ""

    # --- Enforce UX truth: remove confirm/cancel language for scheduled tasks
    if detected_task:
        st = (detected_task.get("status") or "").lower()
        if st in ("confirmed", "scheduled"):
            reply_text = re.sub(
                r"(?i)\b(confirm|cancel|confirmation)\b.*?$",
                "",
                reply_text,
            ).strip()

    # --- Task UX helper line (only say "Confirm or cancel" when applicable)
    if detected_task:
        status = (detected_task.get("status") or "").lower()
        norm = detected_task.get("normalized") or {}
        when_txt = _format_when(norm.get("scheduled_for"))
        ttype = detected_task.get("task_type") or "task"

        line = "\n\n—\n"
        line += f"**Task detected:** {ttype}"
        if when_txt:
            line += f" for **{when_txt}**."
        else:
            line += "."

        if status == "needs_confirmation":
            line += " Confirm or cancel below."
            reply_text = (reply_text or "") + line
        elif status in ("confirmed", "scheduled"):
            line += " Reminder scheduled. You can manage it below."
            reply_text = (reply_text or "") + line
    # else: for completed/cancelled/etc, do not append extra helper line

    user_mid = add_message(conv_id, "user", "user", user_message)
    assistant_mid = add_message(conv_id, "tamor", "assistant", reply_text)

    # ✅ persist task against USER message, and capture DB id
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

    return jsonify(
        {
            "tamor": reply_text,
            "conversation_id": conv_id,
            "detected_task": detected_task,
            "message_ids": {"user": user_mid, "assistant": assistant_mid},
        }
    )

