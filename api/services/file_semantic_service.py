# services/file_semantic_service.py
"""
Semantic multi-file search + project-wide summarization over project files.

Phase 4.3 Update: Now uses persistent embedding cache.

- Embeddings are cached in file_chunks table on first access
- Subsequent queries reuse cached embeddings (only query is embedded fresh)
- Cache is invalidated when files are deleted or updated

For each query, it:
    * loads cached chunks with embeddings (or generates if not cached),
    * embeds the query,
    * computes cosine similarity,
    * returns top-k hits (with file, page, score, snippet),
    * optionally asks the LLM for a grounded answer.
"""

from typing import Any, Dict, List, Optional, Tuple
import sqlite3

import numpy as np

from utils.db import get_db
from core.memory_core import embed
from services.llm_service import get_llm_client, get_model_name, llm_is_configured
from services.embedding_cache import get_or_create_file_chunks

# Chunking config – keep local and simple (must match embedding_cache.py)
FILE_CHUNK_SIZE = 1200
FILE_CHUNK_OVERLAP = 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _build_chunks_for_project(
    project_id: int, user_id: int
) -> List[Dict[str, Any]]:
    """
    Load chunks with cached embeddings for all files in a project.

    Uses embedding_cache to get or create cached embeddings.

    Each chunk dict looks like:
        {
            "file_id": int,
            "filename": str,
            "mime_type": str | None,
            "chunk_index": int,
            "content": str,
            "start_offset": int | None,
            "page": int | None,
            "embedding": np.ndarray,
        }
    """
    rows = _load_project_file_rows(project_id, user_id)
    if not rows:
        return []

    chunks_out: List[Dict[str, Any]] = []

    for row in rows:
        # Get or create cached chunks with embeddings
        file_chunks = get_or_create_file_chunks(row, project_id)
        chunks_out.extend(file_chunks)

    return chunks_out


def _embed_query_and_get_chunk_embeddings(
    query: str, chunks: List[Dict[str, Any]]
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Embed the query and extract pre-computed embeddings from chunks.

    Chunks are expected to have 'embedding' field (np.ndarray) from cache.
    Only the query needs to be embedded fresh.

    Returns (q_emb, chunk_embs) or (None, None) if not available.
    """
    if not chunks:
        return None, None

    if not llm_is_configured():
        return None, None

    # Embed query fresh
    q_emb_raw = embed(query)

    # Normalize query embedding
    if isinstance(q_emb_raw, (bytes, bytearray, memoryview)):
        q_emb = np.frombuffer(q_emb_raw, dtype=np.float32)
    elif isinstance(q_emb_raw, np.ndarray):
        q_emb = q_emb_raw.astype(np.float32, copy=False)
    else:
        q_emb = np.array(q_emb_raw, dtype=np.float32)

    # Extract pre-computed chunk embeddings
    arrs: List[np.ndarray] = []
    for c in chunks:
        emb = c.get("embedding")
        if emb is None:
            continue
        if isinstance(emb, np.ndarray):
            arrs.append(emb.astype(np.float32, copy=False))
        elif isinstance(emb, (bytes, bytearray, memoryview)):
            arrs.append(np.frombuffer(emb, dtype=np.float32))
        else:
            arrs.append(np.array(emb, dtype=np.float32))

    if not arrs:
        return None, None

    chunk_embs = np.vstack(arrs)
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

    q_emb, chunk_embs = _embed_query_and_get_chunk_embeddings(query, chunks)
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
                "text": c["content"],  # Cache uses "content" key
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

    all_text = "\n\n".join(c["content"] for c in chunks)
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

