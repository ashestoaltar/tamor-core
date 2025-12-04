import json
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
from sentence_transformers import SentenceTransformer
import numpy as np
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# Load environment
load_dotenv()

PERSONALITY_FILE = os.getenv("PERSONALITY_FILE")
MEMORY_DB = os.getenv("MEMORY_DB")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

# OpenAI client
client = OpenAI()

# Load personality
with open(PERSONALITY_FILE, "r") as f:
    personality = json.load(f)

# Optional modes.json if present
MODES_FILE = os.path.join(os.path.dirname(PERSONALITY_FILE), "modes.json")
if os.path.exists(MODES_FILE):
    with open(MODES_FILE, "r") as f:
        modes = json.load(f)
else:
    modes = {}

# Load embedding model
model = SentenceTransformer(EMBEDDING_MODEL)

# Ensure memory DB exists
conn = sqlite3.connect(MEMORY_DB)
cursor = conn.cursor()
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    category TEXT,
    content TEXT,
    embedding BLOB
);
"""
)
conn.commit()
conn.close()


def embed(text: str) -> bytes:
    """Generate an embedding as a numpy float32 array (bytes)."""
    vec = model.encode([text])[0]
    return vec.astype(np.float32).tobytes()


def search_memories(query: str, limit: int = 5):
    """Semantic memory recall."""
    q_vec = model.encode([query])[0].astype(np.float32)

    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT id, content, embedding FROM memories")
    rows = cursor.fetchall()
    conn.close()

    scored = []
    for mid, content, emb_blob in rows:
        emb = np.frombuffer(emb_blob, dtype=np.float32)
        denom = np.linalg.norm(q_vec) * np.linalg.norm(emb)
        if denom == 0:
            continue
        score = float(np.dot(q_vec, emb) / denom)
        scored.append((score, mid, content))

    scored.sort(reverse=True)
    return scored[:limit]


# ---------- AUTO MEMORY HELPERS ----------

def classify_auto_memory(text: str, mode: str) -> str | None:
    """
    Very conservative first pass at auto memory classification.
    Returns a category string or None if we should NOT auto-store.
    """
    lower = text.lower().strip()

    if len(lower) < 20:
        # Too short, probably not worth auto-storing
        return None

    # Identity / personal facts
    identity_triggers = [
        "my name is",
        "i am ",
        "i'm ",
        "i work as",
        "i am the creator of",
        "i am the creator and steward of",
    ]
    if any(t in lower for t in identity_triggers):
        return "identity"

    # Preferences
    preference_triggers = [
        "i prefer",
        "i like",
        "i love",
        "i hate",
        "i usually",
        "i tend to",
    ]
    if any(t in lower for t in preference_triggers):
        return "preference"

    # Reminders / intentions
    reminder_triggers = [
        "remind me",
        "don't let me forget",
        "i need to remember",
    ]
    if any(t in lower for t in reminder_triggers):
        return "reminder"

    # Projects / ongoing work (very rough)
    project_triggers = [
        "i'm working on",
        "i am working on",
        "i'm building",
        "i am building",
        "project",
        "song",
        "teaching",
        "article",
        "macro",
        "pergola",
        "toscana",
        "ashes to altar",
        "light upon ruin",
    ]
    if any(t in lower for t in project_triggers):
        return "project"

    # Long notes in certain modes (e.g., Path / Anchor / System)
    if len(lower) > 300 and mode in ("Path", "Anchor", "System", "Scholar"):
        return "long_note"

    return None


def auto_store_memory_if_relevant(text: str, mode: str):
    """
    Decide whether to auto-store this message as memory.
    Very conservative; manual 'Store' button still exists for full control.
    """
    category = classify_auto_memory(text, mode)
    if not category:
        return

    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()

    # Skip if exact same content already exists
    cursor.execute("SELECT id FROM memories WHERE content = ? LIMIT 1", (text,))
    if cursor.fetchone():
        conn.close()
        return

    emb = embed(text)
    cursor.execute(
        "INSERT INTO memories (category, content, embedding) VALUES (?, ?, ?)",
        (category, text, emb),
    )
    conn.commit()
    conn.close()

def build_system_prompt(active_mode: str) -> str:
    """
    Build the full system prompt for Tamor based on:
    - Global personality (identity, directives, tone)
    - Active mode (summary, style, persona)
    """

    # Default to Scholar if mode not found
    mode_data = modes.get(active_mode, modes.get("Scholar", {}))

    # Global personality
    name = personality.get("name", "Tamor")
    identity = personality.get(
        "identity",
        "Tamor is an aligned, steady, illuminating intelligence."
    )
    directives = personality.get("directives", [])
    tone = personality.get("tone", {})

    # Format directives as bullet list
    directives_text = ""
    if directives:
        directives_text = "\n".join(f"- {d}" for d in directives)

    # Format tone as a compact description
    # Example: wisdom: high, precision: high, warmth: medium...
    tone_text = ", ".join(f"{k}: {v}" for k, v in tone.items()) if tone else ""

    # Mode fields
    mode_label = mode_data.get("label", active_mode)
    mode_summary = mode_data.get("summary", "")
    mode_style = mode_data.get("style", "")
    mode_when = mode_data.get("when_to_use", "")
    mode_persona = mode_data.get("persona", "")

    system_prompt = f"""
You are {name}, a personal AI agent.

Identity:
{identity}

Global directives:
{directives_text}

Tone profile:
{tone_text}

Active mode: {mode_label}

Mode summary:
{mode_summary}

Mode style:
{mode_style}

When to use this mode:
{mode_when}

Mode persona (deep behavior spec):
{mode_persona}

General rules:
- Stay within the active mode's behavior and style unless the user explicitly asks to switch modes.
- Respect the user's values and constraints.
- Prefer clarity over cleverness. If you must make assumptions, state them briefly.
""".strip()

    return system_prompt


# ---------- API ROUTES ----------


@app.route("/api/personality", methods=["GET"])
def get_personality():
    return jsonify(personality)


@app.route("/api/memory/add", methods=["POST"])
def add_memory():
    data = request.json
    content = data.get("content")
    category = data.get("category", "general")
    emb = embed(content)

    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO memories (category, content, embedding) VALUES (?, ?, ?)",
        (category, content, emb),
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "success"})


@app.route("/api/memory/search", methods=["POST"])
def memory_search():
    data = request.json
    query = data.get("query")
    results = search_memories(query)

    output = [
        {
            "score": r[0],
            "id": r[1],
            "content": r[2],
        }
        for r in results
    ]

    return jsonify(output)


@app.route("/api/memory/list", methods=["GET"])
def memory_list():
    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, timestamp, category, content FROM memories ORDER BY id DESC"
    )
    rows = cursor.fetchall()
    conn.close()

    output = []
    for row in rows:
        output.append(
            {
                "id": row[0],
                "timestamp": row[1],
                "category": row[2],
                "content": row[3],
            }
        )

    return jsonify(output)

@app.get("/api/mode/<mode_name>")
def get_mode(mode_name):
    """Return mode metadata plus the fully built system prompt for debugging/inspection."""
    mode_data = modes.get(mode_name, {})
    system_prompt = build_system_prompt(mode_name)

    return {
        "name": mode_name,
        "mode": mode_data,
        "system_prompt": system_prompt,
    }


@app.route("/api/modes", methods=["GET"])
def get_modes():
    return jsonify(modes)


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message")
    mode = data.get("mode", "Scholar")

    # Retrieve memory
    memories = search_memories(user_message)
    memory_context = "\n".join([m[2] for m in memories])

    # Mode info if available
    mode_info = modes.get(mode, {})
    mode_summary = mode_info.get("summary", "")
    mode_style = mode_info.get("style", "")
    mode_when = mode_info.get("when_to_use", "")

    # Build system prompt using deep mode personality
    system_prompt = build_system_prompt(mode)

    # Add memory context (optional but helpful)
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

    # ---- AUTO MEMORY: decide if this user message should be stored ----
    auto_store_memory_if_relevant(user_message, mode)

    response = {
        "tamor": reply_text,
        "mode": mode,
        "mode_info": mode_info,
        "memory_matches": [
            {
                "id": m[1],
                "score": m[0],
                "content": m[2],
            }
            for m in memories
        ],
    }
    return jsonify(response)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5055)

