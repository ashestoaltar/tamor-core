# routes/chat_api.py
from flask import Blueprint, jsonify, request, session
import requests
import re

from core.config import client, OPENAI_MODEL, modes
from core.prompt import build_system_prompt
from core.intent import parse_intent, execute_intent
from utils.db import get_db  # per-user memory search uses DB directly

chat_bp = Blueprint("chat_api", __name__, url_prefix="/api")


@chat_bp.get("/modes")
def get_modes():
    from core.config import modes as all_modes
    return jsonify(all_modes)


@chat_bp.get("/mode/<mode_name>")
def get_mode(mode_name):
    from core.config import modes as all_modes

    mode_data = all_modes.get(mode_name, {})
    system_prompt = build_system_prompt(mode_name)
    return {"name": mode_name, "mode": mode_data, "system_prompt": system_prompt}


# ---------- Simple per-user memory search ------------------------------------


def _tokenize(text: str):
    """Very small tokenizer: lowercase, alphanumeric words."""
    return set(re.findall(r"\w+", (text or "").lower()))


def search_user_memories(user_id, query, limit=5, max_candidates=200):
    """
    Lightweight per-user memory search.

    Only considers memories where:
        user_id IS NULL  (global memories)
        OR user_id = current user

    Then ranks them by naive word-overlap score.
    Returns: list of tuples -> (score: float, id: int, content: str)
    """
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, category, content
        FROM memories
        WHERE (user_id IS NULL OR user_id = ?)
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (user_id, max_candidates),
    )
    rows = cur.fetchall()
    conn.close()

    scored = []
    for r in rows:
        content = r["content"] or ""
        content_tokens = _tokenize(content)
        if not content_tokens:
            continue

        overlap = query_tokens.intersection(content_tokens)
        if not overlap:
            continue

        score = len(overlap) / len(query_tokens)
        scored.append((score, r["id"], content))

    # sort by score desc, then by id for stability
    scored.sort(key=lambda x: (-x[0], x[1]))

    return scored[:limit]


# ---------- Conversation helpers ---------------------------------------------


def get_or_create_conversation(
    user_id, conversation_id=None, title=None, project_id=None
):
    """
    Ensure we have a conversation row for this user.
    - If conversation_id is provided and belongs to this user -> reuse it.
    - Otherwise create a new conversation.
    """
    conn = get_db()
    cur = conn.cursor()

    if conversation_id is not None:
        # Verify ownership
        cur.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        row = cur.fetchone()
        if row:
            # Touch updated_at
            cur.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (row["id"],),
            )
            conn.commit()
            conv_id = row["id"]
            conn.close()
            return conv_id

    # Create new conversation
    if not title:
        title = "New Conversation"

    cur.execute(
        """
        INSERT INTO conversations (user_id, project_id, title)
        VALUES (?, ?, ?)
        """,
        (user_id, project_id, title),
    )
    conn.commit()
    conv_id = cur.lastrowid
    conn.close()
    return conv_id


def add_message(conversation_id, sender, role, content):
    """
    Insert a message into the messages table and bump conversation.updated_at.

    sender: 'user' or 'tamor'
    role:   'user', 'assistant', 'system'

    Returns:
        message_id (int) for further linking (files, UI, etc.).
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO messages (conversation_id, sender, role, content)
        VALUES (?, ?, ?, ?)
        """,
        (conversation_id, sender, role, content),
    )
    message_id = cur.lastrowid

    cur.execute(
        "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (conversation_id,),
    )

    conn.commit()
    conn.close()
    return message_id


# ---------- Main chat route --------------------------------------------------


@chat_bp.post("/chat")
def chat():
    data = request.json or {}
    user_message = data.get("message", "") or ""
    mode = data.get("mode", "Scholar")
    conversation_id = data.get("conversation_id")  # may be None
    conversation_title = (data.get("conversation_title") or "").strip()
    project_id = data.get("project_id")  # optional, mostly for future use

    # Require login so we can keep conversations + memories per user
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "not_authenticated"}), 401

    # If no explicit title for new conversation, derive from first user message
    if not conversation_title and not conversation_id:
        conversation_title = user_message.strip()[:80] or "New Conversation"

    # Ensure we have a conversation for this chat
    conv_id = get_or_create_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
        title=conversation_title,
        project_id=project_id,
    )

    mode_info = modes.get(mode, {})

    reply_text = None
    memories = []
    memory_matches = []

    # ---------- INTENT PARSER / COMMANDS BRANCH -------------------------
    intent = parse_intent(user_message)

    if intent is not None:
        intent_result = execute_intent(
            intent,
            user_id=user_id,
            conversation_id=conv_id,
        )
        if intent_result.get("handled"):
            # We handled this as a command: set reply_text and skip the LLM.
            reply_text = intent_result.get("reply_text", "")
            memory_matches = intent_result.get("memory_matches", [])
        else:
            intent = None  # Let normal chat handle it if not actually handled.

    # ---------- NORMAL CHAT BRANCH --------------------------------------
    if reply_text is None:
        # Per-user memory search (no more global identity bleed)
        memories = search_user_memories(user_id, user_message)

        memory_context = "\n".join([m[2] for m in memories])

        system_prompt = build_system_prompt(mode)
        system_prompt += (
            "\n\nUse the following long-term memory context only if it is helpful and relevant. "
            "Do not force it into the answer if it doesn't fit.\n"
            f"Memory context:\n{memory_context}"
        )

        try:
            completion = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            reply_text = completion.choices[0].message.content
        except Exception as e:
            reply_text = f"(Tamor encountered an error talking to the model: {e})"

        memory_matches = [
            {"id": m[1], "score": m[0], "content": m[2]} for m in memories
        ]

    # ---------- Store messages in DB ----------------------------------------
    user_message_id = None
    assistant_message_id = None

    try:
        user_message_id = add_message(conv_id, "user", "user", user_message)
    except Exception as e:
        print("Failed to save user message:", e)

    try:
        assistant_message_id = add_message(conv_id, "tamor", "assistant", reply_text)
    except Exception as e:
        print("Failed to save assistant message:", e)

    # ---------- Auto-memory (unchanged, still via HTTP) ---------------------
    try:
        requests.post(
            "http://127.0.0.1:5055/api/memory/auto",
            json={"text": user_message, "mode": mode, "source": "user"},
            timeout=1.0,
        )
    except Exception as e:
        print("Auto-memory (user) failed:", e)

    try:
        requests.post(
            "http://127.0.0.1:5055/api/memory/auto",
            json={"text": reply_text, "mode": mode, "source": "assistant"},
            timeout=1.0,
        )
    except Exception as e:
        print("Auto-memory (assistant) failed:", e)

    # ---------- Build response ----------------------------------------------
    response = {
        "tamor": reply_text,
        "mode": mode,
        "mode_info": mode_info,
        "memory_matches": memory_matches,
        "conversation_id": conv_id,
        # Optional but very useful for the UI to attach files / show badges:
        "message_ids": {
          "user": user_message_id,
          "assistant": assistant_message_id,
        },
    }

    return jsonify(response)


@chat_bp.post("/chat/inject")
def inject_assistant_message():
    """
    Inject an assistant-style message into an existing conversation
    without calling the LLM.

    Request JSON:
      {
        "conversation_id": 123,
        "message": "Here is the summary of file ...",
        "mode": "Scholar"   # optional, only used for auto-memory tagging
      }

    Response JSON:
      {
        "conversation_id": 123,
        "message": {
          "id": 456,
          "role": "assistant",
          "sender": "tamor",
          "content": "Here is the summary of file ..."
        }
      }
    """
    data = request.json or {}
    content = (data.get("message") or data.get("content") or "").strip()
    mode = data.get("mode", "Scholar")
    conversation_id = data.get("conversation_id")

    if not content:
        return jsonify({"error": "message_required"}), 400
    if not conversation_id:
        return jsonify({"error": "conversation_id_required"}), 400

    # Require login so we can enforce ownership
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "not_authenticated"}), 401

    # Ensure the conversation belongs to this user
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, user_id FROM conversations WHERE id = ?",
        (conversation_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "conversation_not_found"}), 404
    if row["user_id"] != user_id:
        return jsonify({"error": "forbidden"}), 403

    # Store message in DB as coming from Tamor / assistant
    message_id = None
    try:
        message_id = add_message(conversation_id, "tamor", "assistant", content)
    except Exception as e:
        print("Failed to save injected assistant message:", e)

    # Optional: auto-memory for this assistant message
    try:
        requests.post(
            "http://127.0.0.1:5055/api/memory/auto",
            json={"text": content, "mode": mode, "source": "assistant"},
            timeout=1.0,
        )
    except Exception as e:
        print("Auto-memory (assistant, injected) failed:", e)

    return jsonify(
        {
            "conversation_id": conversation_id,
            "message": {
                "id": message_id,
                "role": "assistant",
                "sender": "tamor",
                "content": content,
            },
        }
    )


@chat_bp.post("/chat/inject-and-reply")
def inject_and_reply():
    """
    Insert a user-style message into an existing conversation AND
    immediately run one assistant turn (same behavior as /chat).

    Request JSON:
      {
        "conversation_id": 123,
        "message": "Question about symbol WidthMM...",
        "mode": "Scholar"
      }

    Response JSON:
      {
        "ok": true,
        "conversation_id": 123,
        "tamor": "...assistant reply...",
        "memory_matches": [...],
        "message_ids": {
          "user": <id>,
          "assistant": <id>
        }
      }
    """
    data = request.json or {}
    user_message = (data.get("message") or data.get("content") or "").strip()
    mode = data.get("mode", "Scholar")
    conversation_id = data.get("conversation_id")

    if not user_message:
        return jsonify({"error": "message_required"}), 400
    if not conversation_id:
        return jsonify({"error": "conversation_id_required"}), 400

    # Require login so we can enforce ownership
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "not_authenticated"}), 401

    # Ensure the conversation belongs to this user
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, user_id FROM conversations WHERE id = ?",
        (conversation_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "conversation_not_found"}), 404
    if row["user_id"] != user_id:
        return jsonify({"error": "forbidden"}), 403

    mode_info = modes.get(mode, {})

    reply_text = None
    memories = []
    memory_matches = []

    # ---------- INTENT PARSER / COMMANDS BRANCH -------------------------
    intent = parse_intent(user_message)

    if intent is not None:
        intent_result = execute_intent(
            intent,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        if intent_result.get("handled"):
            reply_text = intent_result.get("reply_text", "")
            memory_matches = intent_result.get("memory_matches", [])
        else:
            intent = None

    # ---------- NORMAL CHAT BRANCH --------------------------------------
    if reply_text is None:
        memories = search_user_memories(user_id, user_message)
        memory_context = "\n".join([m[2] for m in memories])

        system_prompt = build_system_prompt(mode)
        system_prompt += (
            "\n\nUse the following long-term memory context only if it is helpful and relevant. "
            "Do not force it into the answer if it doesn't fit.\n"
            f"Memory context:\n{memory_context}"
        )

        try:
            completion = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            reply_text = completion.choices[0].message.content
        except Exception as e:
            reply_text = f"(Tamor encountered an error talking to the model: {e})"

        memory_matches = [
            {"id": m[1], "score": m[0], "content": m[2]} for m in memories
        ]

    # ---------- Store messages in DB ----------------------------------------
    user_message_id = None
    assistant_message_id = None

    try:
        user_message_id = add_message(
            conversation_id, "user", "user", user_message
        )
    except Exception as e:
        print("Failed to save injected user message:", e)

    try:
        assistant_message_id = add_message(
            conversation_id, "tamor", "assistant", reply_text
        )
    except Exception as e:
        print("Failed to save assistant reply (inject-and-reply):", e)

    # ---------- Auto-memory (unchanged) -------------------------------------
    try:
        requests.post(
            "http://127.0.0.1:5055/api/memory/auto",
            json={"text": user_message, "mode": mode, "source": "user"},
            timeout=1.0,
        )
    except Exception as e:
        print("Auto-memory (user, inject-and-reply) failed:", e)

    try:
        requests.post(
            "http://127.0.0.1:5055/api/memory/auto",
            json={"text": reply_text, "mode": mode, "source": "assistant"},
            timeout=1.0,
        )
    except Exception as e:
        print("Auto-memory (assistant, inject-and-reply) failed:", e)

    return jsonify(
        {
            "ok": True,
            "conversation_id": conversation_id,
            "tamor": reply_text,
            "mode": mode,
            "mode_info": mode_info,
            "memory_matches": memory_matches,
            "message_ids": {
                "user": user_message_id,
                "assistant": assistant_message_id,
            },
        }
    )

