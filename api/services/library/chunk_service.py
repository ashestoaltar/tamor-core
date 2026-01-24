# api/services/library/chunk_service.py

"""
Chunking and embedding service for library files.

Chunks library file text and generates embeddings for semantic search.
Reuses patterns from embedding_cache.py but for library_chunks table.
"""

from typing import Any, Dict, List, Optional

import numpy as np

from core.memory_core import embed_many
from utils.db import get_db

from .library_service import LibraryService
from .text_service import LibraryTextService


# Chunking configuration
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


class LibraryChunkService:
    """Service for chunking library files and generating embeddings."""

    def __init__(self):
        self.text_service = LibraryTextService()
        self.library = LibraryService()

    def get_chunks(self, library_file_id: int) -> List[Dict[str, Any]]:
        """
        Get chunks for a library file, generating if needed.

        Returns list of:
        {
            'chunk_index': int,
            'content': str,
            'embedding': np.ndarray,
            'start_offset': int,
            'page': int or None
        }
        """
        # Check cache first
        cached = self._get_cached_chunks(library_file_id)
        if cached is not None:
            return cached

        # Generate chunks
        return self._generate_chunks(library_file_id)

    def _get_cached_chunks(self, library_file_id: int) -> Optional[List[Dict]]:
        """Get chunks from database cache."""
        conn = get_db()
        cur = conn.execute(
            """
            SELECT chunk_index, content, embedding, start_offset, page
            FROM library_chunks
            WHERE library_file_id = ?
            ORDER BY chunk_index ASC
            """,
            (library_file_id,),
        )
        rows = cur.fetchall()

        if not rows:
            return None

        chunks = []
        for row in rows:
            emb_blob = row["embedding"]
            embedding = np.frombuffer(emb_blob, dtype=np.float32) if emb_blob else None

            chunks.append(
                {
                    "chunk_index": row["chunk_index"],
                    "content": row["content"],
                    "embedding": embedding,
                    "start_offset": row["start_offset"],
                    "page": row["page"],
                }
            )

        return chunks

    def _generate_chunks(self, library_file_id: int) -> List[Dict]:
        """Generate chunks and embeddings for a library file."""
        # Get text
        text, meta = self.text_service.get_text(library_file_id)

        if not text or not self.text_service.is_parseable(library_file_id):
            return []

        # Get page offsets if available (for PDFs)
        page_offsets = None
        if meta and isinstance(meta, dict):
            page_offsets = meta.get("page_offsets")

        # Create chunks
        windowed = self._chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)

        if not windowed:
            return []

        # Extract content and metadata
        chunks_to_embed = []
        chunk_metadata = []

        for idx, (start_offset, chunk_text) in enumerate(windowed):
            if not chunk_text.strip():
                continue

            page = self._offset_to_page(start_offset, page_offsets)

            chunks_to_embed.append(chunk_text)
            chunk_metadata.append(
                {
                    "chunk_index": idx,
                    "start_offset": start_offset,
                    "page": page,
                }
            )

        if not chunks_to_embed:
            return []

        # Generate embeddings
        embeddings = embed_many(chunks_to_embed)

        # Store in database
        conn = get_db()

        # Clear any existing chunks
        conn.execute(
            "DELETE FROM library_chunks WHERE library_file_id = ?",
            (library_file_id,),
        )

        chunks = []
        for i, (content, emb_blob) in enumerate(zip(chunks_to_embed, embeddings)):
            meta = chunk_metadata[i]
            # embed_many returns bytes directly, convert to numpy for return value
            embedding = np.frombuffer(emb_blob, dtype=np.float32)

            conn.execute(
                """
                INSERT INTO library_chunks
                (library_file_id, chunk_index, content, embedding, start_offset, page)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    library_file_id,
                    meta["chunk_index"],
                    content,
                    emb_blob,
                    meta["start_offset"],
                    meta["page"],
                ),
            )

            chunks.append(
                {
                    "chunk_index": meta["chunk_index"],
                    "content": content,
                    "embedding": embedding,
                    "start_offset": meta["start_offset"],
                    "page": meta["page"],
                }
            )

        conn.commit()

        # Mark file as indexed
        self.library.mark_indexed(library_file_id)

        return chunks

    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[tuple]:
        """
        Sliding window chunking.
        Returns list of (start_offset, chunk_text).
        """
        chunks = []
        start = 0
        length = len(text)

        while start < length:
            end = min(length, start + chunk_size)
            chunks.append((start, text[start:end]))

            if end == length:
                break

            start = max(0, end - overlap)

        return chunks

    def _offset_to_page(
        self, offset: int, page_offsets: Optional[List[int]]
    ) -> Optional[int]:
        """Map character offset to 1-based page number."""
        if not page_offsets or not isinstance(page_offsets, list):
            return None

        page_index = 0
        for i, page_offset in enumerate(page_offsets):
            if not isinstance(page_offset, int):
                continue
            if page_offset <= offset:
                page_index = i
            else:
                break

        return page_index + 1

    def invalidate_chunks(self, library_file_id: int) -> int:
        """Delete cached chunks for a file."""
        conn = get_db()
        cur = conn.execute(
            "DELETE FROM library_chunks WHERE library_file_id = ?",
            (library_file_id,),
        )
        conn.commit()
        return cur.rowcount

    def reindex_file(self, library_file_id: int) -> List[Dict]:
        """Force re-extraction, re-chunking, and re-embedding."""
        # Clear text cache
        self.text_service.invalidate_cache(library_file_id)

        # Clear chunk cache
        self.invalidate_chunks(library_file_id)

        # Regenerate
        return self._generate_chunks(library_file_id)
