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
from services.llm_service import get_llm_client, get_model_name

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

        # Check if we have sources to research
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

        # Call LLM
        try:
            llm = get_llm_client()
            response = llm.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                model=get_model_name(),
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
