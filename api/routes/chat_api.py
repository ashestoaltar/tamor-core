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
from core.mode_router import route_mode
from core.task_normalizer import normalize_detected_task

chat_bp = Blueprint("chat_api", __name__, url_prefix="/api")

client = OpenAI()
OPENAI_MODEL = "gpt-4.1-mini"

CHAT_HISTORY_LIMIT = 24


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "not_authenticated"}), 401
        return fn(*args, **kwargs)

    return wrapper


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
    tz_name = (data.get("tz_name") or "").strip() or None
    tz_offset_minutes = data.get("tz_offset_minutes")

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

    # Intent handling
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

    system_prompt = build_system_prompt(effective_mode)
    system_prompt += """
Capability note (Tamor app):
- This app supports reminders and tasks via an internal task system.
- If the user asks to "remind me" / set a reminder, do NOT say you cannot set reminders/alarms.
- Instead: If a reminder is detected and it needs confirmation, tell the user to confirm/cancel below. Otherwise, acknowledge that it’s scheduled and can be managed below.
""".strip()

    history = fetch_chat_history(conv_id, limit=CHAT_HISTORY_LIMIT)

    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "system", "content": system_prompt}, *history, {"role": "user", "content": user_message}],
    )

    reply_text = completion.choices[0].message.content or ""

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


    user_mid = add_message(conv_id, "user", "user", user_message)
    assistant_mid = add_message(conv_id, "tamor", "assistant", reply_text)

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

