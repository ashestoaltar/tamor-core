"""
Embedding Cache Service

Manages persistent caching of file chunk embeddings in the file_chunks table.
Embeddings are generated on first access and reused for subsequent queries.

This eliminates redundant embedding generation during semantic search.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from utils.db import get_db
from core.memory_core import embed_many
from routes.files_api import get_or_extract_file_text_for_row


# Chunking config - must match file_semantic_service.py
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


def _is_placeholder_text(text: str) -> bool:
    """Detect placeholder texts that indicate parsing failed."""
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
    Sliding-window chunking by characters.
    Returns list of (start_offset, chunk_text).
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


def _map_offset_to_page(
    offset: int, page_offsets: Optional[List[int]]
) -> Optional[int]:
    """Map character offset to 1-based page number."""
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


def get_cached_chunks_for_file(file_id: int) -> Optional[List[Dict[str, Any]]]:
    """
    Get cached chunks with embeddings for a file.

    Returns None if no cache exists, otherwise returns list of chunk dicts:
    {
        "chunk_index": int,
        "content": str,
        "embedding": np.ndarray (float32)
    }
    """
    conn = get_db()
    cur = conn.execute(
        """
        SELECT chunk_index, content, embedding
        FROM file_chunks
        WHERE file_id = ?
        ORDER BY chunk_index ASC
        """,
        (file_id,)
    )
    rows = cur.fetchall()

    if not rows:
        return None

    chunks = []
    for row in rows:
        emb_blob = row["embedding"]
        emb_array = np.frombuffer(emb_blob, dtype=np.float32)
        chunks.append({
            "chunk_index": row["chunk_index"],
            "content": row["content"],
            "embedding": emb_array
        })

    return chunks


def cache_chunks_for_file(
    file_id: int,
    project_id: int,
    chunks: List[Dict[str, Any]]
) -> None:
    """
    Store chunks with embeddings in the database.

    Each chunk dict should have:
    - chunk_index: int
    - content: str
    - embedding: bytes (BLOB)
    """
    if not chunks:
        return

    conn = get_db()

    # Clear any existing chunks for this file
    conn.execute("DELETE FROM file_chunks WHERE file_id = ?", (file_id,))

    # Insert new chunks
    for chunk in chunks:
        conn.execute(
            """
            INSERT INTO file_chunks (project_id, file_id, chunk_index, content, embedding)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                project_id,
                file_id,
                chunk["chunk_index"],
                chunk["content"],
                chunk["embedding"]
            )
        )

    conn.commit()


def invalidate_cache_for_file(file_id: int) -> int:
    """
    Delete cached chunks for a file.
    Returns number of chunks deleted.
    """
    conn = get_db()
    cur = conn.execute(
        "DELETE FROM file_chunks WHERE file_id = ?",
        (file_id,)
    )
    conn.commit()
    return cur.rowcount


def invalidate_cache_for_project(project_id: int) -> int:
    """
    Delete cached chunks for all files in a project.
    Returns number of chunks deleted.
    """
    conn = get_db()
    cur = conn.execute(
        "DELETE FROM file_chunks WHERE project_id = ?",
        (project_id,)
    )
    conn.commit()
    return cur.rowcount


def get_or_create_file_chunks(
    file_row,
    project_id: int
) -> List[Dict[str, Any]]:
    """
    Get cached chunks for a file, or create them if not cached.

    Args:
        file_row: sqlite3.Row from project_files table
        project_id: Project ID for storage

    Returns list of chunk dicts with:
    - file_id, filename, mime_type
    - chunk_index, start_offset, page
    - content (text)
    - embedding (np.ndarray)
    """
    file_id = file_row["id"]
    filename = file_row["filename"]
    mime_type = file_row["mime_type"]

    # Check cache first
    cached = get_cached_chunks_for_file(file_id)
    if cached is not None:
        # Enrich cached chunks with file metadata
        return [
            {
                "file_id": file_id,
                "filename": filename,
                "mime_type": mime_type,
                "chunk_index": c["chunk_index"],
                "content": c["content"],
                "embedding": c["embedding"],
                # Note: start_offset and page not stored in cache
                # These are only needed for display, not search
                "start_offset": None,
                "page": None,
            }
            for c in cached
        ]

    # No cache - generate chunks and embeddings
    text, meta, _parser = get_or_extract_file_text_for_row(file_row)
    if not text or _is_placeholder_text(text):
        return []

    # Get page offsets for PDFs
    page_offsets = None
    if isinstance(meta, dict):
        po = meta.get("page_offsets")
        if isinstance(po, list):
            page_offsets = po

    # Create chunks
    windowed = _chunk_text_with_offsets(text, CHUNK_SIZE, CHUNK_OVERLAP)

    chunks_to_embed = []
    chunk_metadata = []

    for idx, (start_offset, chunk_text) in enumerate(windowed):
        if not chunk_text.strip():
            continue

        page_num = _map_offset_to_page(start_offset, page_offsets)

        chunks_to_embed.append(chunk_text)
        chunk_metadata.append({
            "chunk_index": idx,
            "start_offset": start_offset,
            "page": page_num,
        })

    if not chunks_to_embed:
        return []

    # Generate embeddings (batch)
    embeddings = embed_many(chunks_to_embed)

    # Prepare chunks for caching and return
    chunks_for_cache = []
    result_chunks = []

    for i, (text_content, emb_blob) in enumerate(zip(chunks_to_embed, embeddings)):
        meta = chunk_metadata[i]

        # For cache storage
        chunks_for_cache.append({
            "chunk_index": meta["chunk_index"],
            "content": text_content,
            "embedding": emb_blob,  # bytes for DB
        })

        # For return (with numpy array)
        emb_array = np.frombuffer(emb_blob, dtype=np.float32)
        result_chunks.append({
            "file_id": file_id,
            "filename": filename,
            "mime_type": mime_type,
            "chunk_index": meta["chunk_index"],
            "start_offset": meta["start_offset"],
            "page": meta["page"],
            "content": text_content,
            "embedding": emb_array,
        })

    # Store in cache
    cache_chunks_for_file(file_id, project_id, chunks_for_cache)

    return result_chunks


def get_cache_stats() -> Dict[str, Any]:
    """Get statistics about the embedding cache."""
    conn = get_db()

    cur = conn.execute("SELECT COUNT(*) as count FROM file_chunks")
    total_chunks = cur.fetchone()["count"]

    cur = conn.execute("SELECT COUNT(DISTINCT file_id) as count FROM file_chunks")
    cached_files = cur.fetchone()["count"]

    cur = conn.execute("SELECT COUNT(DISTINCT project_id) as count FROM file_chunks")
    cached_projects = cur.fetchone()["count"]

    return {
        "total_chunks": total_chunks,
        "cached_files": cached_files,
        "cached_projects": cached_projects,
    }
