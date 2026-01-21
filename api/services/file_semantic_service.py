# services/file_semantic_service.py
"""
Semantic multi-file search + project-wide summarization over project files.

This version is intentionally simple and stateless:

- It does NOT read embeddings from the file_chunks table.
- It uses cached file text (file_text_cache via get_or_extract_file_text_for_row).
- For each query, it:
    * loads text + metadata for all files in the project,
    * chunks them in memory (keeping track of char offsets),
    * embeds the chunks and the query,
    * computes cosine similarity,
    * returns top-k hits (with file, page, score, snippet),
    * optionally asks the LLM for a grounded answer.

Perfect for the Anchor spec demo scale.
"""

from typing import Any, Dict, List, Optional, Tuple
import sqlite3

import numpy as np

from utils.db import get_db
from core.memory_core import embed, embed_many
from services.llm_service import get_llm_client, get_model_name, llm_is_configured
from routes.files_api import get_or_extract_file_text_for_row

# Chunking config – keep local and simple
FILE_CHUNK_SIZE = 1200
FILE_CHUNK_OVERLAP = 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_placeholder_text(text: str) -> bool:
    """Detect placeholder texts that indicate we couldn't parse the file."""
    if not text:
        return True

    prefixes = (
        "This file is not a plain-text type.",
        "This file is a PDF, but the PDF parser",
        "This PDF appears to have no extractable text",
        "Error extracting text from PDF:",
        "Error reading file:",
    )
    return any(text.startswith(p) for p in prefixes)


def _chunk_text_with_offsets(
    text: str, chunk_size: int, overlap: int
) -> List[Tuple[int, str]]:
    """
    Sliding-window chunking by characters, but we keep the starting index
    of each chunk so we can map it back to a PDF page.
    Returns a list of (start_index, chunk_text).
    """
    chunks: List[Tuple[int, str]] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(length, start + chunk_size)
        chunks.append((start, text[start:end]))
        if end == length:
            break
        start = max(0, end - overlap)
    return chunks


def _load_project_file_rows(project_id: int, user_id: int) -> List[sqlite3.Row]:
    """Return project_files rows for this project/user."""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT pf.*
        FROM project_files pf
        JOIN projects p ON pf.project_id = p.id
        WHERE pf.project_id = ? AND p.user_id = ?
        ORDER BY pf.id ASC
        """,
        (project_id, user_id),
    )
    return cur.fetchall()


def _map_offset_to_page(
    offset: int, page_offsets: Optional[List[int]]
) -> Optional[int]:
    """
    Given a character offset into the concatenated PDF text and a list of
    page_offsets (one per page), return a 1-based page number.
    """
    if not page_offsets or not isinstance(page_offsets, list):
        return None

    page_index = 0
    for i, off in enumerate(page_offsets):
        if not isinstance(off, int):
            continue
        if off <= offset:
            page_index = i
        else:
            break
    return page_index + 1


def _build_chunks_for_project(
    project_id: int, user_id: int
) -> List[Dict[str, Any]]:
    """
    Load cached text + meta for all files in a project and return in-memory chunks.

    Each chunk dict looks like:
        {
            "file_id": int,
            "filename": str,
            "mime_type": str | None,
            "chunk_index": int,
            "text": str,
            "start_offset": int,
            "page": int | None,
        }
    """
    rows = _load_project_file_rows(project_id, user_id)
    if not rows:
        return []

    chunks_out: List[Dict[str, Any]] = []

    for row in rows:
        file_id = row["id"]
        filename = row["filename"]
        mime_type = row["mime_type"]

        text, meta, _parser = get_or_extract_file_text_for_row(row)
        if not text or _is_placeholder_text(text):
            continue

        page_offsets = None
        if isinstance(meta, dict):
            po = meta.get("page_offsets")
            if isinstance(po, list):
                page_offsets = po

        windowed = _chunk_text_with_offsets(
            text, FILE_CHUNK_SIZE, FILE_CHUNK_OVERLAP
        )

        for idx, (start_offset, chunk_text) in enumerate(windowed):
            if not chunk_text.strip():
                continue

            page_num = _map_offset_to_page(start_offset, page_offsets)

            chunks_out.append(
                {
                    "file_id": file_id,
                    "filename": filename,
                    "mime_type": mime_type,
                    "chunk_index": idx,
                    "start_offset": start_offset,
                    "page": page_num,
                    "text": chunk_text,
                }
            )

    return chunks_out


def _embed_query_and_chunks(
    query: str, chunks: List[Dict[str, Any]]
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Compute embeddings for a query and list of chunks.

    Returns (q_emb, chunk_embs) or (None, None) if embedding not available.

    Handles both normal float vectors and raw bytes/BLOB embeddings.
    """
    if not chunks:
        return None, None

    if not llm_is_configured():
        return None, None

    texts = [c["text"] for c in chunks]

    chunk_embs_raw = embed_many(texts)
    q_emb_raw = embed(query)

    # --- normalize query embedding ---
    if isinstance(q_emb_raw, (bytes, bytearray, memoryview)):
        q_emb = np.frombuffer(q_emb_raw, dtype=np.float32)
    elif isinstance(q_emb_raw, np.ndarray):
        q_emb = q_emb_raw.astype(np.float32, copy=False)
    else:
        q_emb = np.array(q_emb_raw, dtype=np.float32)

    # --- normalize chunk embeddings ---
    if isinstance(chunk_embs_raw, list):
        arrs: List[np.ndarray] = []
        for vec in chunk_embs_raw:
            if isinstance(vec, (bytes, bytearray, memoryview)):
                arr = np.frombuffer(vec, dtype=np.float32)
            elif isinstance(vec, np.ndarray):
                arr = vec.astype(np.float32, copy=False)
            else:
                arr = np.array(vec, dtype=np.float32)
            arrs.append(arr)
        if not arrs:
            return None, None
        chunk_embs = np.vstack(arrs)
    elif isinstance(chunk_embs_raw, np.ndarray):
        chunk_embs = chunk_embs_raw.astype(np.float32, copy=False)
        if chunk_embs.ndim == 1:
            chunk_embs = chunk_embs.reshape(1, -1)
    else:
        return None, None

    return q_emb, chunk_embs


# ---------------------------------------------------------------------------
# Semantic search
# ---------------------------------------------------------------------------


def semantic_search_project_files(
    project_id: int,
    user_id: int,
    query: str,
    top_k: int = 20,  # a bit higher for "find all specs mentioning X"
    include_answer: bool = True,
) -> Dict[str, Any]:
    """
    Top-level API used by routes.projects_api.

    Returns:
      {
        "query": "...",
        "results": [ {chunk hit...}, ... ],
        "answer": "LLM-grounded explanation or None"
      }
    """
    query = (query or "").strip()
    if not query:
        return {"query": query, "results": [], "answer": None}

    chunks = _build_chunks_for_project(project_id, user_id)
    if not chunks:
        return {"query": query, "results": [], "answer": None}

    q_emb, chunk_embs = _embed_query_and_chunks(query, chunks)
    if q_emb is None or chunk_embs is None:
        return {"query": query, "results": [], "answer": None}

    norms = np.linalg.norm(chunk_embs, axis=1) * np.linalg.norm(q_emb)
    sims = np.dot(chunk_embs, q_emb) / np.maximum(norms, 1e-8)

    top_indices = np.argsort(-sims)[:top_k]

    hits: List[Dict[str, Any]] = []
    for idx in top_indices:
        idx_int = int(idx)
        c = chunks[idx_int]
        hits.append(
            {
                "file_id": c["file_id"],
                "filename": c["filename"],
                "mime_type": c.get("mime_type"),
                "chunk_index": c["chunk_index"],
                "page": c.get("page"),
                "score": float(sims[idx_int]),
                "text": c["text"],
            }
        )

    result: Dict[str, Any] = {"query": query, "results": hits, "answer": None}

    if not include_answer or not hits or not llm_is_configured():
        return result

    # Build a context window out of the top chunks
    context_parts: List[str] = []
    max_chars = 8000
    used = 0
    for h in hits:
        chunk_text = h.get("text") or ""
        if not chunk_text:
            continue
        remaining = max_chars - used
        if remaining <= 0:
            break
        if len(chunk_text) > remaining:
            chunk_text = chunk_text[:remaining] + "\n...[truncated]..."
        page_str = (
            f" (page {h.get('page')})" if isinstance(h.get("page"), int) else ""
        )
        context_parts.append(
            f"From file '{h.get('filename', 'unknown')}'{page_str}, "
            f"chunk {h.get('chunk_index', '?')}:\n{chunk_text}"
        )
        used += len(chunk_text)

    context = "\n\n---\n\n".join(context_parts)

    messages = [
        {
            "role": "system",
            "content": (
                "You are an assistant that answers questions using semantic search "
                "results from the user's project files. Be concise but specific. "
                "If the answer is unclear from the snippets, say so explicitly "
                "and avoid hallucinating extra details."
            ),
        },
        {
            "role": "user",
            "content": (
                f"The user asked: {query}\n\n"
                "Use ONLY the following snippets from their project files "
                "as your source of truth:\n\n" + context
            ),
        },
    ]

    llm = get_llm_client()
    answer = llm.chat_completion(messages=messages, model=get_model_name())
    result["answer"] = answer

    return result


# ---------------------------------------------------------------------------
# Project-wide summarization
# ---------------------------------------------------------------------------


def summarize_project_files(
    project_id: int,
    user_id: int,
    prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Summarize all available chunks for a project using the LLM.

    If `prompt` is provided, it is treated as additional instructions for
    how to shape the summary (e.g. "focus on constraints and open questions").
    """
    chunks = _build_chunks_for_project(project_id, user_id)
    if not chunks:
        return {"summary": "", "used_model": None, "total_chunks": 0}

    all_text = "\n\n".join(c["text"] for c in chunks)
    if not all_text.strip():
        return {"summary": "", "used_model": None, "total_chunks": 0}

    if not llm_is_configured():
        pseudo = all_text[:3000]
        return {
            "summary": (
                "LLM is not configured on this server, so this is a "
                "truncated preview of the project file chunks:\n\n" + pseudo
            ),
            "used_model": None,
            "total_chunks": len(chunks),
        }

    base_system = (
        "You are an assistant that summarizes project documentation and files. "
        "Provide a clear, concise high-level overview of the project's files, "
        "focusing on constraints, config keys, and open questions."
    )

    if prompt:
        system_content = (
            base_system
            + " The user has additional instructions for this summary:\n"
            + prompt
        )
    else:
        system_content = base_system

    messages = [
        {
            "role": "system",
            "content": system_content,
        },
        {"role": "user", "content": all_text},
    ]

    llm = get_llm_client()
    model_name = get_model_name()
    answer = llm.chat_completion(messages=messages, model=model_name)

    return {
        "summary": answer,
        "used_model": model_name,
        "total_chunks": len(chunks),
    }

