# api/routes/chat_api.py
import json
from functools import wraps
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, session
from openai import OpenAI

from utils.db import get_db
from core.prompt import build_system_prompt
from core.task_classifier import classify_task

chat_bp = Blueprint("chat_api", __name__, url_prefix="/api")

client = OpenAI()
OPENAI_MODEL = "gpt-4.1-mini"


# -------------------------------
# Auth (local; repo doesn't have utils.auth)
# -------------------------------
def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "not_authenticated"}), 401
        return fn(*args, **kwargs)
    return wrapper


# -------------------------------
# Minimal conversation/message helpers
# (repo doesn't have utils.messages)
# -------------------------------
def get_or_create_conversation(user_id, conversation_id=None, title="New chat", project_id=None):
    conn = get_db()
    cur = conn.cursor()

    if conversation_id:
        cur.execute("SELECT id FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id))
        row = cur.fetchone()
        if row:
            cid = row["id"] if hasattr(row, "keys") else row[0]
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


# -------------------------------
# Task helpers
# -------------------------------
def initial_task_status(normalized: dict | None) -> str:
    # UX rule: newly detected tasks always require confirmation
    return "needs_confirmation"


def persist_detected_task(user_id, project_id, conversation_id, message_id, detected_task):
    if not detected_task or not message_id:
        return

    task_type = detected_task.get("task_type") or detected_task.get("type")
    if not task_type:
        return

    normalized = detected_task.get("normalized") or {}
    status = detected_task.get("status") or initial_task_status(normalized)

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
            json.dumps(detected_task.get("payload"), default=str) if detected_task.get("payload") is not None else None,
            json.dumps(normalized, default=str) if normalized else None,
            status,
        ),
    )
    conn.commit()
    conn.close()


def _format_when(iso_str: str | None) -> str | None:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.astimezone().strftime("%a %b %d, %I:%M %p")
    except Exception:
        return iso_str


# -------------------------------
# Debug route (you tried this; it was missing)
# -------------------------------
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


# -------------------------------
# Main chat route
# -------------------------------
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

    # Ensure normalized/status exist if classifier provided them
    if detected_task:
        normalized = detected_task.get("normalized") or {}

        # HARDEN: if scheduled_for is a datetime, serialize it
        sf = normalized.get("scheduled_for")
        if isinstance(sf, datetime):
            normalized["scheduled_for"] = sf.astimezone(timezone.utc).isoformat(timespec="minutes")

        # HARDEN: if classifier accidentally put datetime anywhere else, stringify it now
        for k, v in list(normalized.items()):
            if isinstance(v, datetime):
                normalized[k] = v.astimezone(timezone.utc).isoformat()

        detected_task["normalized"] = normalized
        detected_task["status"] = detected_task.get("status") or initial_task_status(normalized)

    system_prompt = build_system_prompt(mode)

    # ✅ Key fix: explicit capabilities
    system_prompt += """

Capability note (Tamor app):
- This app supports reminders and tasks via an internal task system.
- If the user asks to "remind me" / set a reminder, do NOT say you cannot set reminders/alarms.
- Instead: acknowledge and (when a time is present) tell the user to confirm/cancel in the UI.
""".strip()

    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )

    reply_text = completion.choices[0].message.content or ""

    # Append confirmation line when appropriate
    if detected_task and detected_task.get("status") == "needs_confirmation":
        norm = detected_task.get("normalized") or {}
        when_txt = _format_when(norm.get("scheduled_for"))
        ttype = detected_task.get("task_type") or "task"

        line = "\n\n—\n"
        line += f"**Task detected:** {ttype}"
        if when_txt:
            line += f" for **{when_txt}**."
        else:
            line += "."
        line += " Confirm or cancel below."

        reply_text = (reply_text or "") + line

    user_mid = add_message(conv_id, "user", "user", user_message)
    assistant_mid = add_message(conv_id, "tamor", "assistant", reply_text)

    persist_detected_task(
        user_id=user_id,
        project_id=project_id,
        conversation_id=conv_id,
        message_id=assistant_mid,
        detected_task=detected_task,
    )

    return jsonify(
        {
            "tamor": reply_text,
            "conversation_id": conv_id,
            "detected_task": detected_task,
            "message_ids": {"user": user_mid, "assistant": assistant_mid},
        }
    )

