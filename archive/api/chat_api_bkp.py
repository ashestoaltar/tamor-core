# routes/chat_api.py
from flask import Blueprint, jsonify, request, session
import requests

from core.config import client, OPENAI_MODEL, modes
from core.memory_core import search_memories
from core.prompt import build_system_prompt
from services.playlists import add_movie_to_christmas_by_title
from utils.db import get_db  # NEW: shared DB helper

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


# ---------- Conversation helpers --------------------------------------------


def get_or_create_conversation(user_id, conversation_id=None, title=None, project_id=None):
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

    cur.execute(
        "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (conversation_id,),
    )

    conn.commit()
    conn.close()


# ---------- Main chat route --------------------------------------------------


@chat_bp.post("/chat")
def chat():
    data = request.json or {}
    user_message = data.get("message", "") or ""
    mode = data.get("mode", "Scholar")
    conversation_id = data.get("conversation_id")  # may be None
    conversation_title = (data.get("conversation_title") or "").strip()
    project_id = data.get("project_id")  # optional, mostly for future use

    # Require login so we can keep conversations per user
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

    lower_msg = user_message.lower()
    mode_info = modes.get(mode, {})

    # ---------- STREMIO / PLAYLIST SPECIAL HANDLING -------------------------
    reply_text = None
    memory_matches = []

    if "add " in lower_msg and "to the christmas playlist" in lower_msg:
        # Playlist command branch
        try:
            raw_title = user_message[
                lower_msg.find("add ")
                + 4 : lower_msg.find("to the christmas playlist")
            ].strip(' ."\'')

        except Exception:
            raw_title = None

        if not raw_title:
            reply_text = (
                "Tell me the movie title, like: "
                "“Add The Polar Express to the Christmas playlist.”"
            )
        else:
            reply_text = add_movie_to_christmas_by_title(raw_title)

        # No memory search or model call in this branch
    else:
        # ---------- NORMAL CHAT BRANCH --------------------------------------
        memories = search_memories(user_message)
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

    try:
        add_message(conv_id, "user", "user", user_message)
    except Exception as e:
        print("Failed to save user message:", e)

    try:
        add_message(conv_id, "tamor", "assistant", reply_text)
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
    }

    return jsonify(response)

