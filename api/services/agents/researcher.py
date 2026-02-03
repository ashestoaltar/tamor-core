# api/services/agents/researcher.py
"""
Researcher Agent (Phase 6.2)

Purpose: Source gathering and structured analysis
- Pulls relevant excerpts from project files
- Surfaces citations, contradictions, open questions
- Produces structured notes

Constraints:
- Never writes final prose
- Always cites sources
- Cannot invent facts
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentOutput, Citation, RequestContext
from services.llm_service import get_agent_llm
from services.ghm import get_research_directives_prompt
from services.library.search_service import LibrarySearchService

logger = logging.getLogger(__name__)


RESEARCHER_SYSTEM_PROMPT = """You are a Research Agent. Your role is to gather, analyze, and organize information from provided sources.

## Your Responsibilities
1. Extract relevant information from the provided sources
2. Identify key facts, claims, and evidence
3. Note contradictions or inconsistencies between sources
4. Flag gaps or missing information
5. Organize findings into structured notes

## Constraints
- ONLY use information from the provided sources
- NEVER invent or hallucinate facts
- NEVER write final prose or articles (that's the Writer's job)
- ALWAYS cite which source each piece of information comes from
- If sources don't contain relevant information, say so explicitly

## Output Format
Respond with a JSON object containing:
{
    "summary": "Brief overview of what the sources contain",
    "key_findings": [
        {"finding": "...", "source": "[1]", "confidence": "high|medium|low"}
    ],
    "themes": ["theme1", "theme2"],
    "contradictions": [
        {"issue": "...", "sources": ["[1]", "[2]"]}
    ],
    "gaps": ["What's missing or unclear"],
    "open_questions": ["Questions that remain unanswered"],
    "recommended_structure": ["Suggested outline for writing"]
}

Be thorough but concise. Focus on actionable insights."""


class ResearcherAgent(BaseAgent):
    """
    Researcher agent for source gathering and analysis.

    The Researcher examines provided sources (project files, retrieved chunks)
    and produces structured notes that the Writer can use.
    """

    name = "researcher"
    description = "Gathers and analyzes information from sources, producing structured research notes with citations."

    def can_handle(self, ctx: RequestContext, intent: str) -> bool:
        """Handle research, analysis, and summarization intents."""
        research_intents = {
            "research",
            "analyze",
            "summarize",
            "find",
            "extract",
            "compare",
            "review",
        }
        return intent.lower() in research_intents

    def run(self, ctx: RequestContext, input_payload: Optional[Dict] = None) -> AgentOutput:
        """
        Execute research on the provided context.

        Args:
            ctx: Request context with retrieved chunks
            input_payload: Optional specific research questions

        Returns:
            AgentOutput with structured research notes
        """
        start_time = time.time()

        # Check if we have sources to research OR if it's a scholarly question
        is_scholarly = self._is_theological_research(ctx)

        # For scholarly questions without project context, use Scholar mode
        # This uses the Scholar persona and queries the global library
        # Takes priority over the generic structured research path
        if is_scholarly and not ctx.project_id:
            return self._run_scholarly_research(ctx, start_time)

        # For non-scholarly questions without any sources, return early
        if not ctx.retrieved_chunks and not ctx.project_id:
            return AgentOutput(
                agent_name=self.name,
                content={
                    "summary": "No sources available for research.",
                    "key_findings": [],
                    "themes": [],
                    "contradictions": [],
                    "gaps": ["No project files or retrieved content to analyze"],
                    "open_questions": [],
                    "recommended_structure": [],
                },
                is_final=False,
                error="No sources available",
            )

        # Build the prompt
        system_prompt = RESEARCHER_SYSTEM_PROMPT

        # Phase 8.2.7: GHM frame challenge injection
        if ctx.ghm_frame_challenge:
            system_prompt += f"\n\n{ctx.ghm_frame_challenge}"

        # Phase 8.2.8: Research directives for theological research
        # Inject when GHM is active or when sources suggest theological content
        if ctx.ghm_frame_challenge or self._is_theological_research(ctx):
            research_directives = get_research_directives_prompt()
            if research_directives:
                system_prompt += f"\n\n{research_directives}"

        # Add memory context if available
        if ctx.memories:
            memory_context = self._format_memories(ctx.memories)
            system_prompt += f"\n\n## User Context\n{memory_context}"

        # Format retrieved sources
        sources_text = self._format_sources(ctx.retrieved_chunks)

        # Build user message
        user_message = f"""## Research Request
{ctx.user_message}

{sources_text}

Analyze these sources and provide structured research notes in JSON format."""

        # Call LLM with agent-specific provider routing
        try:
            llm, model, provider_name = get_agent_llm("researcher")
            if not llm:
                return AgentOutput(
                    agent_name=self.name,
                    content={"error": "No LLM provider available"},
                    is_final=False,
                    error="No LLM provider configured",
                    processing_ms=int((time.time() - start_time) * 1000),
                )

            logger.info(f"Researcher using provider: {provider_name}, model: {model}")

            response = llm.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                model=model,
            )

            # Parse JSON response
            research_data = self._parse_response(response)

            # Build citations from sources
            citations = self._build_citations(ctx.retrieved_chunks, research_data)

            processing_ms = int((time.time() - start_time) * 1000)

            return AgentOutput(
                agent_name=self.name,
                content=research_data,
                is_final=False,  # Research is never final - Writer formats it
                citations=citations,
                artifacts=[
                    {
                        "type": "research_notes",
                        "data": research_data,
                    }
                ],
                processing_ms=processing_ms,
                provider_used=provider_name,
                model_used=model,
            )

        except Exception as e:
            logger.error(f"Researcher agent error: {e}")
            return AgentOutput(
                agent_name=self.name,
                content={"error": str(e)},
                is_final=False,
                error=str(e),
                processing_ms=int((time.time() - start_time) * 1000),
            )

    def _format_sources(self, chunks: List[Dict[str, Any]]) -> str:
        """Format retrieved chunks as numbered sources."""
        if not chunks:
            return "## Sources\nNo sources provided."

        lines = ["## Sources\n"]
        for i, chunk in enumerate(chunks, 1):
            filename = chunk.get("filename", "unknown")
            content = chunk.get("content", "")
            page = chunk.get("page")
            score = chunk.get("score")

            header = f"[{i}] {filename}"
            if page:
                header += f" (page {page})"
            if score:
                header += f" [relevance: {score:.2f}]"

            # Truncate very long chunks
            if len(content) > 2000:
                content = content[:2000] + "...[truncated]"

            lines.append(f"{header}\n{content}\n")

        return "\n".join(lines)

    def _format_memories(self, memories: List[Dict[str, Any]]) -> str:
        """Format relevant memories for context."""
        if not memories:
            return ""

        lines = []
        for mem in memories[:5]:  # Limit to 5 most relevant
            category = mem.get("category", "general")
            content = mem.get("content", "")
            lines.append(f"- [{category}] {content}")

        return "\n".join(lines)

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response as JSON, with fallback."""
        # Try to extract JSON from response
        text = response.strip()

        # Handle markdown code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fallback: return as unstructured finding
            logger.warning("Failed to parse researcher response as JSON")
            return {
                "summary": text[:500],
                "key_findings": [{"finding": text, "source": "response", "confidence": "low"}],
                "themes": [],
                "contradictions": [],
                "gaps": ["Could not parse structured response"],
                "open_questions": [],
                "recommended_structure": [],
            }

    def _build_citations(
        self, chunks: List[Dict[str, Any]], research_data: Dict[str, Any]
    ) -> List[Citation]:
        """Build citation objects from chunks."""
        citations = []

        for i, chunk in enumerate(chunks, 1):
            citations.append(
                Citation(
                    file_id=chunk.get("file_id"),
                    filename=chunk.get("filename"),
                    chunk_index=chunk.get("chunk_index"),
                    page=chunk.get("page"),
                    snippet=chunk.get("content", "")[:200],
                    relevance_score=chunk.get("score"),
                )
            )

        return citations

    def _run_scholarly_research(self, ctx: RequestContext, start_time: float) -> AgentOutput:
        """
        Handle scholarly/theological research questions without project context.

        Uses xAI/Grok with the Scholar mode persona from modes.json.
        Uses library sources from ctx.retrieved_chunks if available,
        otherwise searches global library directly.
        """
        # Use retrieved_chunks if router already populated them, otherwise search library
        library_results = []
        if ctx.retrieved_chunks:
            # Router already did library search - convert chunk dicts to a usable format
            logger.info(f"Using {len(ctx.retrieved_chunks)} chunks from router retrieval")
            # retrieved_chunks are dicts, use them directly for formatting
            library_results = ctx.retrieved_chunks
        else:
            # No chunks from router - do our own library search
            try:
                search_service = LibrarySearchService()
                search_results = search_service.search(
                    query=ctx.user_message,
                    scope="library",
                    limit=15,
                    min_score=0.3,
                )
                # Convert SearchResult objects to dicts for consistent formatting
                library_results = [
                    {
                        "library_file_id": r.library_file_id,
                        "filename": r.filename,
                        "chunk_index": r.chunk_index,
                        "content": r.content,
                        "score": r.score,
                        "page": r.page,
                    }
                    for r in search_results
                ]
                logger.info(f"Library search returned {len(library_results)} results for scholarly research")
            except Exception as e:
                logger.warning(f"Library search failed: {e}")

        # Load Scholar mode persona from modes.json
        system_prompt = self._load_scholar_persona()

        # Append research directives if configured
        research_directives = get_research_directives_prompt()
        if research_directives:
            system_prompt += f"\n\n{research_directives}"

        # Append GHM frame challenge if present
        if ctx.ghm_frame_challenge:
            system_prompt += f"\n\n{ctx.ghm_frame_challenge}"

        # Append memory context if available
        if ctx.memories:
            memory_context = self._format_memories(ctx.memories)
            system_prompt += f"\n\n## User Context\n{memory_context}"

        # Build user message with library sources if found
        if library_results:
            sources_text = self._format_library_sources(library_results)
            user_message = f"""## Question
{ctx.user_message}

{sources_text}

Use the library sources above where relevant. Cite them by filename when drawing from them. If the sources don't address the question, you may draw on your broader knowledge but note that you're doing so."""
        else:
            user_message = ctx.user_message

        try:
            llm, model, provider_name = get_agent_llm("researcher")
            if not llm:
                return AgentOutput(
                    agent_name=self.name,
                    content={"error": "No LLM provider available"},
                    is_final=False,
                    error="No LLM provider configured",
                    processing_ms=int((time.time() - start_time) * 1000),
                )

            logger.info(f"Researcher (scholarly mode) using provider: {provider_name}, model: {model}")

            response = llm.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                model=model,
            )

            processing_ms = int((time.time() - start_time) * 1000)

            # Build citations from library results
            citations = self._build_library_citations(library_results)

            # For scholarly research, the response IS the final content
            # (no Writer needed for reformatting)
            return AgentOutput(
                agent_name=self.name,
                content=response,
                is_final=True,  # Scholarly research is final, no Writer needed
                citations=citations,
                artifacts=[],
                processing_ms=processing_ms,
                provider_used=provider_name,
                model_used=model,
            )

        except Exception as e:
            logger.error(f"Researcher agent (scholarly) error: {e}")
            return AgentOutput(
                agent_name=self.name,
                content={"error": str(e)},
                is_final=False,
                error=str(e),
                processing_ms=int((time.time() - start_time) * 1000),
            )

    def _format_library_sources(self, results) -> str:
        """Format library search results as numbered sources for the prompt.

        Accepts either SearchResult objects or dicts with same keys.
        """
        if not results:
            return "## Library Sources\nNo relevant sources found in library."

        lines = ["## Library Sources\n"]
        for i, result in enumerate(results, 1):
            # Handle both SearchResult objects and dicts
            if hasattr(result, 'filename'):
                filename = result.filename
                page = result.page
                score = result.score
                content = result.content
            else:
                filename = result.get("filename", "unknown")
                page = result.get("page")
                score = result.get("score", 0)
                content = result.get("content", "")

            header = f"[{i}] {filename}"
            if page:
                header += f" (page {page})"
            if score:
                header += f" [relevance: {score:.2f}]"

            # Truncate very long chunks
            if len(content) > 1500:
                content = content[:1500] + "...[truncated]"

            lines.append(f"{header}\n{content}\n")

        return "\n".join(lines)

    def _build_library_citations(self, results) -> List[Citation]:
        """Build Citation objects from library search results.

        Accepts either SearchResult objects or dicts with same keys.
        """
        citations = []
        for result in results:
            # Handle both SearchResult objects and dicts
            if hasattr(result, 'filename'):
                file_id = result.library_file_id
                filename = result.filename
                chunk_index = result.chunk_index
                page = result.page
                content = result.content
                score = result.score
            else:
                file_id = result.get("library_file_id") or result.get("file_id")
                filename = result.get("filename", "unknown")
                chunk_index = result.get("chunk_index")
                page = result.get("page")
                content = result.get("content", "")
                score = result.get("score", 0)

            citations.append(
                Citation(
                    file_id=file_id,
                    filename=filename,
                    chunk_index=chunk_index,
                    page=page,
                    snippet=content[:200] if content else "",
                    relevance_score=score,
                )
            )
        return citations

    def _load_scholar_persona(self) -> str:
        """Load the Scholar mode persona from modes.json."""
        import os

        modes_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config",
            "modes.json"
        )

        try:
            with open(modes_path, "r") as f:
                modes = json.load(f)
            return modes.get("Scholar", {}).get("persona", "")
        except Exception as e:
            logger.warning(f"Failed to load Scholar persona: {e}")
            # Minimal fallback
            return "You are a biblical and theological research assistant."

    def _is_theological_research(self, ctx: RequestContext) -> bool:
        """
        Detect if this research request involves theological content.

        Uses simple keyword detection on user message and source filenames.
        """
        theological_keywords = {
            'scripture', 'bible', 'torah', 'gospel', 'covenant', 'law',
            'sabbath', 'feast', 'passover', 'pentecost', 'tabernacles',
            'prophecy', 'messiah', 'apostle', 'church', 'israel',
            'hebrew', 'greek', 'aramaic', 'septuagint', 'tanakh',
            'jesus', 'paul', 'moses', 'abraham', 'david',
            'genesis', 'exodus', 'leviticus', 'deuteronomy', 'romans',
            'galatians', 'hebrews', 'matthew', 'acts', 'revelation',
        }

        # Check user message
        message_lower = ctx.user_message.lower()
        if any(kw in message_lower for kw in theological_keywords):
            return True

        # Check source filenames
        for chunk in (ctx.retrieved_chunks or []):
            filename = (chunk.get('filename') or '').lower()
            if any(kw in filename for kw in theological_keywords):
                return True

        return False
