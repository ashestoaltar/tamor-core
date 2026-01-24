# api/services/library/context_service.py

"""
Library context injection for chat.

Finds relevant library content based on user message and injects
into LLM context for grounded responses.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .search_service import LibrarySearchService, SearchResult


@dataclass
class ContextChunk:
    """A chunk of context to inject."""

    source: str  # Filename
    source_id: int  # Library file ID
    content: str  # The text
    page: Optional[int]  # Page number if available
    relevance: float  # Search score

    def to_citation(self) -> str:
        """Format as citation string."""
        if self.page:
            return f"{self.source}, p.{self.page}"
        return self.source


class LibraryContextService:
    """Service for injecting library content into chat context."""

    def __init__(self):
        self.search = LibrarySearchService()

    def get_context_for_message(
        self,
        message: str,
        project_id: Optional[int] = None,
        max_chunks: int = 5,
        max_chars: int = 4000,
        min_score: float = 0.4,
    ) -> Dict[str, Any]:
        """
        Find relevant library content for a chat message.

        Args:
            message: User's message
            project_id: If set, prioritize project's library refs
            max_chunks: Maximum chunks to include
            max_chars: Maximum total characters
            min_score: Minimum relevance score

        Returns:
            {
                'chunks': List[ContextChunk],
                'context_text': str,  # Formatted for injection
                'sources': List[str]  # Unique sources cited
            }
        """
        # Determine scope
        scope = "all" if project_id else "library"

        # Search
        results = self.search.search(
            query=message,
            scope=scope,
            project_id=project_id,
            limit=max_chunks * 2,  # Get extra, filter by size
            min_score=min_score,
        )

        if not results:
            return {"chunks": [], "context_text": "", "sources": []}

        # Build context chunks respecting size limit
        chunks = []
        total_chars = 0
        seen_content = set()  # Deduplicate

        for result in results:
            # Skip duplicates (same content from overlapping chunks)
            content_hash = hash(result.content[:100])
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)

            # Check size limit
            if total_chars + len(result.content) > max_chars:
                # Try to fit a truncated version
                remaining = max_chars - total_chars
                if remaining < 200:
                    break
                content = result.content[:remaining] + "..."
            else:
                content = result.content

            chunks.append(
                ContextChunk(
                    source=result.filename,
                    source_id=result.library_file_id,
                    content=content,
                    page=result.page,
                    relevance=result.score,
                )
            )

            total_chars += len(content)

            if len(chunks) >= max_chunks:
                break

        # Format context text
        context_text = self._format_context(chunks)

        # Get unique sources
        sources = list(dict.fromkeys(c.source for c in chunks))

        return {"chunks": chunks, "context_text": context_text, "sources": sources}

    def _format_context(self, chunks: List[ContextChunk]) -> str:
        """Format chunks as context text for LLM injection."""
        if not chunks:
            return ""

        lines = ["[Library Context]", ""]

        for chunk in chunks:
            citation = chunk.to_citation()
            lines.append(f"From {citation}:")
            lines.append(chunk.content)
            lines.append("")

        lines.append("[End Library Context]")

        return "\n".join(lines)

    def build_system_prompt_addition(
        self,
        context_text: str,
        sources: List[str],
    ) -> str:
        """
        Build the addition to system prompt with library context.

        Includes instructions for the LLM on how to use the context.
        """
        if not context_text:
            return ""

        source_list = ", ".join(sources[:5])
        if len(sources) > 5:
            source_list += f", and {len(sources) - 5} more"

        return f"""
The user has a research library. Relevant excerpts from their library
are provided below. When answering:

1. Draw on this context when relevant
2. Cite sources by filename and page when quoting or paraphrasing
3. Distinguish between what the sources say and your own analysis
4. If the context doesn't address the question, say so and answer from general knowledge

Sources available: {source_list}

{context_text}
"""

    def get_context_for_references(
        self,
        file_ids: List[int],
        query: Optional[str] = None,
        max_chunks_per_file: int = 3,
    ) -> Dict[str, Any]:
        """
        Get context from specific library files.

        Useful when user explicitly mentions sources to consult.

        Args:
            file_ids: Library file IDs to draw from
            query: Optional query to find most relevant chunks
            max_chunks_per_file: Max chunks from each file
        """
        chunks = []

        for file_id in file_ids:
            if query:
                # Search within file
                results = self.search.search_by_file(
                    query=query,
                    library_file_id=file_id,
                    limit=max_chunks_per_file,
                )
            else:
                # Get first chunks (beginning of document)
                from utils.db import get_db

                conn = get_db()
                cur = conn.execute(
                    """
                    SELECT
                        lc.content, lc.page, lf.filename
                    FROM library_chunks lc
                    JOIN library_files lf ON lc.library_file_id = lf.id
                    WHERE lc.library_file_id = ?
                    ORDER BY lc.chunk_index
                    LIMIT ?
                """,
                    (file_id, max_chunks_per_file),
                )

                results = []
                for row in cur.fetchall():
                    results.append(
                        SearchResult(
                            library_file_id=file_id,
                            filename=row["filename"],
                            chunk_index=0,
                            content=row["content"],
                            score=1.0,
                            page=row["page"],
                        )
                    )

            for result in results:
                chunks.append(
                    ContextChunk(
                        source=result.filename,
                        source_id=result.library_file_id,
                        content=result.content,
                        page=result.page,
                        relevance=result.score,
                    )
                )

        context_text = self._format_context(chunks)
        sources = list(dict.fromkeys(c.source for c in chunks))

        return {"chunks": chunks, "context_text": context_text, "sources": sources}
