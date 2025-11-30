# routes/memory_api.py
import sqlite3
from flask import Blueprint, jsonify, request

from core.config import MEMORY_DB
from core.memory_core import embed, search_memories

memory_bp = Blueprint("memory_api", __name__, url_prefix="/api")


@memory_bp.get("/personality")
def get_personality():
    from core.config import personality

    return jsonify(personality)


@memory_bp.post("/memory/add")
def add_memory():
    data = request.json or {}
    content = data.get("content")
    category = data.get("category", "general")

    if not content:
        return jsonify({"error": "content is required"}), 400

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


@memory_bp.post("/memory/search")
def memory_search():
    data = request.json or {}
    query = data.get("query", "")
    results = search_memories(query)

    output = [
        {"score": r[0], "id": r[1], "content": r[2]}
        for r in results
    ]
    return jsonify(output)


@memory_bp.get("/memory/list")
def list_memories():
    category = request.args.get("category")
    query = request.args.get("q")

    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()

    base_sql = "SELECT id, category, content FROM memories"
    params = []
    filters = []

    if category and category.lower() != "all":
        filters.append("category = ?")
        params.append(category)

    if query:
        filters.append("content LIKE ?")
        params.append(f"%{query}%")

    if filters:
        base_sql += " WHERE " + " AND ".join(filters)

    base_sql += " ORDER BY id DESC LIMIT 200"

    cursor.execute(base_sql, params)
    rows = cursor.fetchall()
    conn.close()

    memories = [
        {"id": row[0], "category": row[1], "content": row[2]} for row in rows
    ]
    return jsonify(memories)


@memory_bp.delete("/memory/<int:memory_id>")
def delete_memory(memory_id):
    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted", "id": memory_id})


@memory_bp.post("/memory/auto")
def auto_memory_ingest():
    from core.memory_core import classify_auto_memory, embed

    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    mode = data.get("mode", "Default")
    source = data.get("source", "user")

    if not text:
        return jsonify({"stored": False, "reason": "empty"}), 200

    category = classify_auto_memory(text, mode, source)
    if not category:
        return jsonify({"stored": False, "reason": "not relevant"}), 200

    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM memories WHERE content = ? LIMIT 1", (text,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"stored": False, "reason": "duplicate"}), 200

    emb = embed(text)
    cursor.execute(
        "INSERT INTO memories (category, content, embedding) VALUES (?, ?, ?)",
        (category, text, emb),
    )
    conn.commit()
    conn.close()

    return jsonify({"stored": True, "category": category}), 200

