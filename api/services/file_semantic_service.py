# services/file_semantic_service.py
"""
Semantic multi-file search + project-wide summarization over project files.

Responsibilities:
- Ensure file_chunks table exists
- Chunk & embed text-like project files
- Run cosine similarity search over chunks
- Summarize all chunks across a project
"""

import os
import sqlite3
from typing import Any, Dict, List

import numpy as np

from utils.db import get_db
from core.memory_core import embed, embed_many
from core.config import (
    client,
    OPENAI_MODEL,
    FILE_CHUNK_SIZE,
    FILE_CHUNK_OVERLAP,
)
from routes.files_api import _get_upload_root, _read_file_text


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def ensure_file_chunks_table() -> None:
    """Create the file_chunks table if it does not exist."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS file_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            file_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (file_id) REFERENCES project_files(id)
        );
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_file_chunks_project
        ON file_chunks(project_id);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_file_chunks_file
        ON file_chunks(file_id);
        """
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Chunking + embedding
# ---------------------------------------------------------------------------


_PLACEHOLDER_PREFIXES = (
    "This file is not a plain-text type.",
    "This file is a PDF, but the PDF parser",
    "This PDF appears to have no extractable text",
    "Error extracting text from PDF:",
    "Error reading file contents.",
)


def _is_placeholder_text(text: str) -> bool:
    t = (text or "").strip()
    return any(t.startswith(p) for p in _PLACEHOLDER_PREFIXES)


def _chunk_text(text: str) -> List[str]:
    """
    Simple character-based sliding-window chunking with overlap.

    This is intentionally simple and robust across code, config, notes, etc.
    """
    text = text or ""
    if not text:
        return []

    size = max(256, int(FILE_CHUNK_SIZE))
    overlap = max(0, int(FILE_CHUNK_OVERLAP))
    chunks: List[str] = []

    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = end - overlap if overlap > 0 else end

    return chunks


def _load_file_text(file_row: sqlite3.Row) -> str:
    """Read text for a project_files row using the same logic as /files/content."""
    upload_root = _get_upload_root()
    stored_name_rel = file_row["stored_name"]
    mime_type = file_row["mime_type"] or ""

    full_path = os.path.join(upload_root, stored_name_rel)
    if not os.path.isfile(full_path):
        return ""

    return _read_file_text(full_path, mime_type)


def _index_single_file(project_id: int, file_row: sqlite3.Row) -> int:
    """
    Create or refresh chunks for one file.
    Returns number of chunks written.
    """
    ensure_file_chunks_table()

    file_id = file_row["id"]
    text = _load_file_text(file_row)
    if not text or _is_placeholder_text(text):
        # Nothing useful to index
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM file_chunks WHERE file_id = ?", (file_id,))
        conn.commit()
        conn.close()
        return 0

    chunks = _chunk_text(text)
    if not chunks:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM file_chunks WHERE file_id = ?", (file_id,))
        conn.commit()
        conn.close()
        return 0

    # Embed all chunks
    embeddings = embed_many(chunks)

    conn = get_db()
    cur = conn.cursor()

    # Clear any previous chunks for this file
    cur.execute("DELETE FROM file_chunks WHERE file_id = ?", (file_id,))

    rows_to_insert = []
    for idx, (content, emb_blob) in enumerate(zip(chunks, embeddings)):
        rows_to_insert.append((project_id, file_id, idx, content, emb_blob))

    cur.executemany(
        """
        INSERT INTO file_chunks (project_id, file_id, chunk_index, content, embedding)
        VALUES (?, ?, ?, ?, ?)
        """,
        rows_to_insert,
    )

    conn.commit()
    conn.close()
    return len(chunks)


def ensure_chunks_for_project(project_id: int, user_id: int) -> int:
    """
    Ensure all files in this project have chunks.
    Returns the number of *new* chunks created (approx).
    """
    ensure_file_chunks_table()

    conn = get_db()
    cur = conn.cursor()

    # Load all project_files for this user + project
    cur.execute(
        """
        SELECT id, stored_name, mime_type
        FROM project_files
        WHERE project_id = ? AND user_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (project_id, user_id),
    )
    file_rows = cur.fetchall()
    conn.close()

    total_new_chunks = 0

    for row in file_rows:
        # Skip if we already have at least one chunk for this file
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM file_chunks WHERE file_id = ? LIMIT 1",
            (row["id"],),
        )
        has_any = cur.fetchone() is not None
        conn.close()

        if has_any:
            continue

        total_new_chunks += _index_single_file(project_id, row)

    return total_new_chunks


# ---------------------------------------------------------------------------
# Semantic search + LLM answer (Phase 2.1)
# ---------------------------------------------------------------------------


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _run_llm_answer(query: str, chunks: List[Dict[str, Any]]) -> str | None:
    """
    Given the user query and a list of top chunks, call OpenAI
    to synthesize an answer grounded in those chunks.
    """
    if not chunks:
        return None

    # Best-effort guard: if OpenAI client fails for any reason, just skip
    try:
        # Limit total context size
        max_chars = 8000
        used = 0
        context_parts: List[str] = []

        for ch in chunks:
            text = ch.get("content") or ""
            if not text:
                continue
            if used + len(text) > max_chars:
                break
            used += len(text)
            context_parts.append(
                f"FILE: {ch['filename']} (file_id={ch['file_id']}, chunk_index={ch['chunk_index']})\n"
                f"CONTENT:\n{text}\n-----\n"
            )

        if not context_parts:
            return None

        context_str = "".join(context_parts)

        system_prompt = (
            "You are Tamor, an engineering- and study-focused assistant. "
            "You are given several text chunks from multiple project files, plus a user query. "
            "Answer ONLY using the provided chunks. "
            "When you use information from a file, explicitly mention it like "
            "\"According to motor-config.json (chunk 2)...\". "
            "If the answer is not clearly present, say you cannot find it."
        )

        user_prompt = (
            f"USER QUERY:\n{query}\n\n"
            "Here are the most relevant file chunks:\n\n"
            f"{context_str}\n"
            "Using ONLY this information, answer the query as clearly as possible. "
            "Cite which files you are using."
        )

        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"(Error calling OpenAI for semantic answer: {e})"


def semantic_search_project_files(
    project_id: int,
    user_id: int,
    query: str,
    top_k: int = 8,
    include_answer: bool = True,
) -> Dict[str, Any]:
    """
    Main entrypoint for semantic search:

    - Ensure chunks exist for all project files
    - Embed the query
    - Compute cosine similarity against all chunks in project
    - Return top_k chunk hits + optional LLM answer
    """
    query = (query or "").strip()
    if not query:
        return {"results": [], "answer": None}

    ensure_chunks_for_project(project_id, user_id)

    # Embed the query via the same model used for file chunks
    q_vec = np.frombuffer(embed(query), dtype=np.float32)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            fc.id AS chunk_id,
            fc.file_id,
            fc.chunk_index,
            fc.content,
            fc.embedding,
            pf.filename,
            pf.mime_type,
            pf.size_bytes,
            pf.created_at
        FROM file_chunks fc
        JOIN project_files pf ON fc.file_id = pf.id
        WHERE fc.project_id = ?
        """,
        (project_id,),
    )
    rows = cur.fetchall()
    conn.close()

    scored: List[Dict[str, Any]] = []

    for row in rows:
        emb_blob = row["embedding"]
        emb_vec = np.frombuffer(emb_blob, dtype=np.float32)
        score = _cosine_similarity(q_vec, emb_vec)
        if score <= 0:
            continue

        content = row["content"] or ""
        snippet = content[:260]
        if len(content) > 260:
            snippet += " …"

        scored.append(
            {
                "chunk_id": row["chunk_id"],
                "file_id": row["file_id"],
                "chunk_index": row["chunk_index"],
                "content": content,
                "snippet": snippet,
                "score": score,
                "filename": row["filename"],
                "mime_type": row["mime_type"],
                "size_bytes": row["size_bytes"],
                "created_at": row["created_at"],
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[: max(1, top_k)]

    answer = None
    if include_answer:
        answer = _run_llm_answer(query, top)

    return {
        "results": top,
        "answer": answer,
    }


# ---------------------------------------------------------------------------
# Project-wide summarization (Phase 2.2)
# ---------------------------------------------------------------------------


def summarize_project_files(
    project_id: int,
    user_id: int,
    prompt: str | None = None,
    max_context_chars: int = 9000,
) -> str:
    """
    Summarize all (text-like) file chunks in a project.

    - Ensures chunks exist for all project files.
    - Pulls chunks in a stable order: by filename, then chunk_index.
    - Feeds a limited amount of text into the LLM with a project-focused prompt.

    prompt: an optional natural-language instruction like
        "High-level overview of all files, focusing on constraints and config keys."
    """
    ensure_chunks_for_project(project_id, user_id)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            pf.filename,
            pf.mime_type,
            fc.file_id,
            fc.chunk_index,
            fc.content
        FROM file_chunks fc
        JOIN project_files pf ON fc.file_id = pf.id
        WHERE fc.project_id = ?
        ORDER BY pf.filename ASC, fc.chunk_index ASC
        """,
        (project_id,),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return "This project has no indexed text-like file content to summarize yet."

    used = 0
    context_parts: List[str] = []

    for row in rows:
        filename = row["filename"]
        chunk_index = row["chunk_index"]
        content = row["content"] or ""
        if not content:
            continue

        # Reserve some room for headers
        header = f"FILE: {filename} (chunk {chunk_index + 1})\n"
        block = header + content + "\n-----\n"

        if used + len(block) > max_context_chars:
            break

        context_parts.append(block)
        used += len(block)

    if not context_parts:
        return "The project files have content, but it could not be loaded into context for summarization."

    context_str = "".join(context_parts)

    if not prompt:
        prompt = (
            "Provide a high-level overview of this project based on its files. "
            "Group related files together, explain what they do, and call out any "
            "key configuration parameters, constraints, or open questions you can infer."
        )

    system_prompt = (
        "You are Tamor, an engineering- and study-focused assistant. "
        "You are given many chunks of text from multiple files in a single project. "
        "Write a clear, structured summary of the project, focusing on how the files fit together. "
        "Mention specific filenames when relevant (e.g., motor-config.json, main.ipynb). "
        "If there are gaps or unclear areas, explicitly list them as open questions."
    )

    user_prompt = (
        f"SUMMARY INSTRUCTION:\n{prompt}\n\n"
        "Here are the file chunks from the project:\n\n"
        f"{context_str}\n"
        "Using ONLY this information, produce a concise but detailed project summary. "
        "Use headings and bullet points where helpful."
    )

    try:
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"(Error calling OpenAI for project summary: {e})"

