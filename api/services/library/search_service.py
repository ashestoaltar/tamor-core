# api/services/library/search_service.py

"""
Library semantic search service.

Provides semantic search across library_chunks with scope control:
- library: Search entire library
- project: Search only files referenced by a project
- all: Search library + project files (hybrid)
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from core.memory_core import embed
from utils.db import get_db


@dataclass
class SearchResult:
    """A single search result."""

    library_file_id: int
    filename: str
    chunk_index: int
    content: str
    score: float
    page: Optional[int] = None
    metadata: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "library_file_id": self.library_file_id,
            "filename": self.filename,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "score": round(self.score, 4),
            "page": self.page,
            "metadata": self.metadata,
        }


class LibrarySearchService:
    """Service for semantic search across library files."""

    def __init__(self):
        pass

    def search(
        self,
        query: str,
        scope: str = "library",
        project_id: Optional[int] = None,
        limit: int = 10,
        min_score: float = 0.0,
        file_types: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """
        Semantic search across library.

        Args:
            query: Search query text
            scope: 'library' | 'project' | 'all'
                - library: Search entire library
                - project: Search only project's referenced files
                - all: Search both (project results weighted higher)
            project_id: Required if scope is 'project' or 'all'
            limit: Maximum results to return
            min_score: Minimum similarity score (0-1)
            file_types: Filter by mime type prefixes (e.g., ['application/pdf'])

        Returns:
            List of SearchResult sorted by score descending
        """
        # Embed query (returns bytes, convert to numpy)
        query_bytes = embed(query)
        query_embedding = np.frombuffer(query_bytes, dtype=np.float32)

        # Get candidate chunks based on scope
        if scope == "project":
            if not project_id:
                raise ValueError("project_id required for scope='project'")
            chunks = self._get_project_chunks(project_id)
        elif scope == "all":
            if not project_id:
                raise ValueError("project_id required for scope='all'")
            chunks = self._get_all_chunks(project_id)
        else:  # library
            chunks = self._get_library_chunks()

        # Filter by file type if specified
        if file_types:
            chunks = [c for c in chunks if self._matches_file_type(c, file_types)]

        # Score all chunks
        scored = []
        for chunk in chunks:
            if chunk["embedding"] is None:
                continue

            score = self._cosine_similarity(query_embedding, chunk["embedding"])

            # Boost project files in 'all' scope
            if scope == "all" and chunk.get("is_project_ref"):
                score *= 1.1  # 10% boost for project-referenced files

            if score >= min_score:
                scored.append((score, chunk))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Build results
        results = []
        for score, chunk in scored[:limit]:
            results.append(
                SearchResult(
                    library_file_id=chunk["library_file_id"],
                    filename=chunk["filename"],
                    chunk_index=chunk["chunk_index"],
                    content=chunk["content"],
                    score=score,
                    page=chunk.get("page"),
                    metadata=chunk.get("metadata"),
                )
            )

        return results

    def _get_library_chunks(self) -> List[Dict]:
        """Get all chunks from library."""
        conn = get_db()
        cur = conn.execute(
            """
            SELECT
                lc.library_file_id,
                lc.chunk_index,
                lc.content,
                lc.embedding,
                lc.page,
                lf.filename,
                lf.mime_type,
                lf.metadata_json
            FROM library_chunks lc
            JOIN library_files lf ON lc.library_file_id = lf.id
            WHERE lc.embedding IS NOT NULL
        """
        )

        return [self._row_to_chunk(row) for row in cur.fetchall()]

    def _get_project_chunks(self, project_id: int) -> List[Dict]:
        """Get chunks only from files referenced by project."""
        conn = get_db()
        cur = conn.execute(
            """
            SELECT
                lc.library_file_id,
                lc.chunk_index,
                lc.content,
                lc.embedding,
                lc.page,
                lf.filename,
                lf.mime_type,
                lf.metadata_json
            FROM library_chunks lc
            JOIN library_files lf ON lc.library_file_id = lf.id
            JOIN project_library_refs plr ON lf.id = plr.library_file_id
            WHERE plr.project_id = ?
            AND lc.embedding IS NOT NULL
        """,
            (project_id,),
        )

        chunks = [self._row_to_chunk(row) for row in cur.fetchall()]
        for chunk in chunks:
            chunk["is_project_ref"] = True
        return chunks

    def _get_all_chunks(self, project_id: int) -> List[Dict]:
        """Get all library chunks, marking which are project refs."""
        conn = get_db()

        # Get project file IDs
        cur = conn.execute(
            "SELECT library_file_id FROM project_library_refs WHERE project_id = ?",
            (project_id,),
        )
        project_file_ids = {row["library_file_id"] for row in cur.fetchall()}

        # Get all chunks
        chunks = self._get_library_chunks()

        # Mark project refs
        for chunk in chunks:
            chunk["is_project_ref"] = chunk["library_file_id"] in project_file_ids

        return chunks

    def _row_to_chunk(self, row) -> Dict:
        """Convert database row to chunk dict."""
        embedding = None
        if row["embedding"]:
            embedding = np.frombuffer(row["embedding"], dtype=np.float32)

        metadata = None
        if row["metadata_json"]:
            try:
                metadata = json.loads(row["metadata_json"])
            except json.JSONDecodeError:
                pass

        return {
            "library_file_id": row["library_file_id"],
            "chunk_index": row["chunk_index"],
            "content": row["content"],
            "embedding": embedding,
            "page": row["page"],
            "filename": row["filename"],
            "mime_type": row["mime_type"],
            "metadata": metadata,
            "is_project_ref": False,
        }

    def _matches_file_type(self, chunk: Dict, file_types: List[str]) -> bool:
        """Check if chunk's file matches any of the type prefixes."""
        mime = chunk.get("mime_type") or ""
        return any(mime.startswith(ft) for ft in file_types)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def search_by_file(
        self,
        query: str,
        library_file_id: int,
        limit: int = 5,
    ) -> List[SearchResult]:
        """
        Search within a specific library file.

        Useful for finding relevant sections in a known document.
        """
        query_bytes = embed(query)
        query_embedding = np.frombuffer(query_bytes, dtype=np.float32)

        conn = get_db()
        cur = conn.execute(
            """
            SELECT
                lc.library_file_id,
                lc.chunk_index,
                lc.content,
                lc.embedding,
                lc.page,
                lf.filename
            FROM library_chunks lc
            JOIN library_files lf ON lc.library_file_id = lf.id
            WHERE lc.library_file_id = ?
            AND lc.embedding IS NOT NULL
        """,
            (library_file_id,),
        )

        scored = []
        for row in cur.fetchall():
            embedding = np.frombuffer(row["embedding"], dtype=np.float32)
            score = self._cosine_similarity(query_embedding, embedding)
            scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, row in scored[:limit]:
            results.append(
                SearchResult(
                    library_file_id=row["library_file_id"],
                    filename=row["filename"],
                    chunk_index=row["chunk_index"],
                    content=row["content"],
                    score=score,
                    page=row["page"],
                )
            )

        return results

    def find_similar_files(
        self,
        library_file_id: int,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Find files similar to a given file.

        Uses average embedding of file's chunks as query.
        """
        conn = get_db()

        # Get embeddings for source file
        cur = conn.execute(
            "SELECT embedding FROM library_chunks WHERE library_file_id = ?",
            (library_file_id,),
        )
        rows = cur.fetchall()

        if not rows:
            return []

        # Compute average embedding
        embeddings = [
            np.frombuffer(r["embedding"], dtype=np.float32)
            for r in rows
            if r["embedding"]
        ]
        if not embeddings:
            return []

        avg_embedding = np.mean(embeddings, axis=0)

        # Get all other files
        cur = conn.execute(
            """
            SELECT DISTINCT lf.id, lf.filename, lf.mime_type
            FROM library_files lf
            JOIN library_chunks lc ON lf.id = lc.library_file_id
            WHERE lf.id != ?
        """,
            (library_file_id,),
        )

        files = []
        for row in cur.fetchall():
            # Get this file's chunks
            cur2 = conn.execute(
                "SELECT embedding FROM library_chunks WHERE library_file_id = ?",
                (row["id"],),
            )
            file_embeddings = [
                np.frombuffer(r["embedding"], dtype=np.float32)
                for r in cur2.fetchall()
                if r["embedding"]
            ]
            if not file_embeddings:
                continue

            file_avg = np.mean(file_embeddings, axis=0)
            score = self._cosine_similarity(avg_embedding, file_avg)

            files.append(
                {
                    "library_file_id": row["id"],
                    "filename": row["filename"],
                    "mime_type": row["mime_type"],
                    "similarity": round(score, 4),
                }
            )

        files.sort(key=lambda x: x["similarity"], reverse=True)
        return files[:limit]
