# api/services/agents/writer.py
"""
Writer Agent (Phase 6.2)

Purpose: Prose synthesis and polished output
- Turns research notes into clean writing
- Preserves voice and style
- Cannot invent facts - only synthesizes provided material

Constraints:
- Only uses information from Researcher's output
- Maintains consistent voice/style
- Always attributes claims to sources
"""

import logging
import os
import time
import yaml
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentOutput, Citation, RequestContext
from services.llm_service import get_agent_llm
from services.library.search_service import LibrarySearchService

logger = logging.getLogger(__name__)

# Load writer templates
TEMPLATES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "config",
    "writer_templates.yml"
)

def _load_templates() -> Dict[str, Any]:
    """Load writer templates from config file."""
    try:
        with open(TEMPLATES_PATH, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Failed to load writer templates: {e}")
        return {"templates": {}, "default": "article"}

WRITER_TEMPLATES = _load_templates()


WRITER_SYSTEM_PROMPT = """You are a Writer Agent. Your role is to transform research notes into polished, readable prose.

## Your Responsibilities
1. Take structured research notes and write clear, engaging content
2. Follow the recommended structure when provided
3. Maintain a consistent voice and tone
4. Include citations in the text (e.g., "According to [1]..." or "The document states [2]...")
5. Make the content accessible and well-organized

## Constraints
- ONLY use information from the research notes provided
- NEVER invent facts, quotes, or claims not in the research
- NEVER add information from your own knowledge
- If research is incomplete, note what's missing rather than filling gaps
- Keep citations inline so readers can trace claims

## Style Guidelines
- Clear, direct prose
- Active voice when possible
- Short paragraphs for readability
- Use headers to organize longer pieces
- Match the formality level to the request (article vs summary vs explanation)

## Output
Write the requested content directly. Do not wrap in JSON or markdown code blocks unless specifically asked.
Do NOT include a Sources section - the system will append properly formatted citations automatically."""


class WriterAgent(BaseAgent):
    """
    Writer agent for prose synthesis.

    The Writer takes structured research from the Researcher and produces
    polished, readable output. It cannot invent facts.
    """

    name = "writer"
    description = "Transforms research notes into polished prose, maintaining voice and citing sources."

    def can_handle(self, ctx: RequestContext, intent: str) -> bool:
        """Handle writing, drafting, and explanation intents."""
        writing_intents = {
            "write",
            "draft",
            "compose",
            "explain",
            "article",
            "essay",
            "document",
        }
        return intent.lower() in writing_intents

    def run(self, ctx: RequestContext, input_payload: Optional[Dict] = None) -> AgentOutput:
        """
        Write prose based on research notes.

        Args:
            ctx: Request context (should have prior_outputs from Researcher)
            input_payload: Optional overrides (e.g., style, length)

        Returns:
            AgentOutput with polished prose
        """
        start_time = time.time()

        # Get research from prior outputs
        research_data = self._get_research_data(ctx, input_payload)

        if not research_data:
            return AgentOutput(
                agent_name=self.name,
                content="No research notes available. Please provide sources or run the Researcher first.",
                is_final=True,
                error="No research data",
                processing_ms=int((time.time() - start_time) * 1000),
            )

        # Build the prompt
        system_prompt = WRITER_SYSTEM_PROMPT

        # Phase 8.2.7: GHM frame challenge injection
        if ctx.ghm_frame_challenge:
            system_prompt += f"\n\n{ctx.ghm_frame_challenge}"

        # Add style preferences from memories if available
        style_context = self._extract_style_preferences(ctx.memories)
        if style_context:
            system_prompt += f"\n\n## User Style Preferences\n{style_context}"

        # Format research notes for the writer
        research_text = self._format_research(research_data)

        # Include full library sources if available (for better context)
        sources_text = ""
        if ctx.retrieved_chunks:
            sources_text = self._format_sources(ctx.retrieved_chunks)

        # Determine output type and get template guidance
        template_name = self._detect_output_type(ctx.user_message)
        template_guidance = self._get_template_guidance(template_name)

        user_message = f"""## Writing Request
{ctx.user_message}

{template_guidance}

{research_text}

{sources_text}

Write the requested content following the template structure above. Include inline citations [1], [2], etc."""

        # Call LLM with agent-specific provider routing
        try:
            llm, model, provider_name = get_agent_llm("writer")
            if not llm:
                return AgentOutput(
                    agent_name=self.name,
                    content="No LLM provider available.",
                    is_final=True,
                    error="No LLM provider configured",
                    processing_ms=int((time.time() - start_time) * 1000),
                )

            logger.info(f"Writer using provider: {provider_name}, model: {model}")

            response = llm.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                model=model,
            )

            # Collect citations from research
            citations = self._collect_citations(ctx, research_data)

            processing_ms = int((time.time() - start_time) * 1000)

            return AgentOutput(
                agent_name=self.name,
                content=response,
                is_final=True,  # Writer output is user-facing
                citations=citations,
                artifacts=[
                    {
                        "type": "draft",
                        "data": {
                            "content": response,
                            "output_type": output_type,
                            "word_count": len(response.split()),
                        },
                    }
                ],
                processing_ms=processing_ms,
                provider_used=provider_name,
                model_used=model,
            )

        except Exception as e:
            logger.error(f"Writer agent error: {e}")
            return AgentOutput(
                agent_name=self.name,
                content=f"Error generating content: {str(e)}",
                is_final=True,
                error=str(e),
                processing_ms=int((time.time() - start_time) * 1000),
            )

    def _get_research_data(
        self, ctx: RequestContext, input_payload: Optional[Dict]
    ) -> Optional[Dict[str, Any]]:
        """Extract research data from prior outputs, input payload, or library search."""
        # Check input payload first
        if input_payload and "research" in input_payload:
            return input_payload["research"]

        # Check prior outputs from Researcher
        for output in ctx.prior_outputs:
            if output.agent_name == "researcher" and isinstance(output.content, dict):
                return output.content

        # Fallback: check for raw retrieved chunks (no researcher ran)
        if ctx.retrieved_chunks:
            return self._chunks_to_research_data(ctx.retrieved_chunks)

        # Final fallback: search library directly
        library_chunks = self._search_library(ctx.user_message)
        if library_chunks:
            # Store in context for citation building later
            ctx.retrieved_chunks = library_chunks
            return self._chunks_to_research_data(library_chunks)

        return None

    def _chunks_to_research_data(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert raw chunks to research data format."""
        return {
            "summary": "Sources from library (no prior research analysis)",
            "key_findings": [
                {"finding": c.get("content", "")[:200], "source": f"[{i}]", "confidence": "medium"}
                for i, c in enumerate(chunks[:5], 1)
            ],
            "themes": [],
            "contradictions": [],
            "gaps": [],
            "open_questions": [],
            "recommended_structure": [],
        }

    def _search_library(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search the global library for relevant content."""
        try:
            search_service = LibrarySearchService()
            results = search_service.search(
                query=query,
                scope="library",
                limit=limit,
                min_score=0.3,
            )
            # Convert SearchResult objects to dicts
            return [
                {
                    "library_file_id": r.library_file_id,
                    "file_id": r.library_file_id,
                    "filename": r.filename,
                    "chunk_index": r.chunk_index,
                    "content": r.content,
                    "score": r.score,
                    "page": r.page,
                }
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Writer library search failed: {e}")
            return []

    def _format_sources(self, chunks: List[Dict[str, Any]]) -> str:
        """Format library/retrieved chunks as numbered sources."""
        if not chunks:
            return ""

        lines = ["## Source Materials\n"]
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
            if len(content) > 1500:
                content = content[:1500] + "...[truncated]"

            lines.append(f"{header}\n{content}\n")

        return "\n".join(lines)

    def _format_research(self, research: Dict[str, Any]) -> str:
        """Format research data for the writer prompt."""
        lines = ["## Research Notes\n"]

        # Summary
        if research.get("summary"):
            lines.append(f"### Summary\n{research['summary']}\n")

        # Key findings
        findings = research.get("key_findings", [])
        if findings:
            lines.append("### Key Findings")
            for f in findings:
                if isinstance(f, dict):
                    finding = f.get("finding", "")
                    source = f.get("source", "")
                    confidence = f.get("confidence", "")
                    lines.append(f"- {finding} {source} ({confidence})")
                else:
                    lines.append(f"- {f}")
            lines.append("")

        # Themes
        themes = research.get("themes", [])
        if themes:
            lines.append(f"### Themes\n{', '.join(themes)}\n")

        # Contradictions
        contradictions = research.get("contradictions", [])
        if contradictions:
            lines.append("### Contradictions/Tensions")
            for c in contradictions:
                if isinstance(c, dict):
                    lines.append(f"- {c.get('issue', '')} (sources: {c.get('sources', [])})")
                else:
                    lines.append(f"- {c}")
            lines.append("")

        # Gaps
        gaps = research.get("gaps", [])
        if gaps:
            lines.append(f"### Information Gaps\n" + "\n".join(f"- {g}" for g in gaps) + "\n")

        # Recommended structure
        structure = research.get("recommended_structure", [])
        if structure:
            lines.append("### Recommended Structure")
            for i, section in enumerate(structure, 1):
                lines.append(f"{i}. {section}")
            lines.append("")

        return "\n".join(lines)

    def _detect_output_type(self, message: str) -> str:
        """Detect what kind of output the user wants and return template name."""
        msg = message.lower()
        templates = WRITER_TEMPLATES.get("templates", {})

        # Check for explicit template matches
        if any(w in msg for w in ["torah portion", "parashah", "parsha"]):
            return "torah_portion"
        elif any(w in msg for w in ["deep dive", "research piece", "scholarly"]):
            return "deep_dive"
        elif any(w in msg for w in ["sermon", "teaching", "message"]):
            return "sermon"
        elif any(w in msg for w in ["blog", "blog post"]):
            return "blog_post"
        elif any(w in msg for w in ["summary", "summarize", "overview"]):
            return "summary"
        elif any(w in msg for w in ["article"]):
            return "article"
        else:
            return WRITER_TEMPLATES.get("default", "article")

    def _get_template_guidance(self, template_name: str) -> str:
        """Get writing guidance from a template."""
        templates = WRITER_TEMPLATES.get("templates", {})
        template = templates.get(template_name)

        if not template:
            return ""

        lines = [f"## Writing Template: {template_name.replace('_', ' ').title()}"]
        lines.append(f"*{template.get('description', '')}*\n")

        # Word range
        word_range = template.get("word_range", [])
        if word_range:
            lines.append(f"**Target Length:** {word_range[0]}-{word_range[1]} words\n")

        # Structure
        structure = template.get("structure", [])
        if structure:
            lines.append("**Required Structure:**")
            for section in structure:
                lines.append(f"- {section}")
            lines.append("")

        # Style
        style = template.get("style", {})
        if style:
            lines.append("**Style Guidelines:**")
            if style.get("tone"):
                lines.append(f"- Tone: {style['tone']}")
            if style.get("voice"):
                lines.append(f"- Voice: {style['voice']}")
            if style.get("audience"):
                lines.append(f"- Audience: {style['audience']}")
            lines.append("")

        # Citations
        citations = template.get("citations", {})
        if citations:
            lines.append("**Citation Style:**")
            if citations.get("style"):
                lines.append(f"- {citations['style']}")
            if citations.get("minimum"):
                lines.append(f"- Minimum citations: {citations['minimum']}")

        return "\n".join(lines)

    def _extract_style_preferences(self, memories: List[Dict[str, Any]]) -> str:
        """Extract writing style preferences from user memories."""
        style_prefs = []

        for mem in memories:
            category = mem.get("category", "")
            content = mem.get("content", "").lower()

            if category == "preference":
                if any(w in content for w in ["style", "tone", "voice", "write", "formal", "casual"]):
                    style_prefs.append(mem.get("content", ""))

        return "\n".join(f"- {p}" for p in style_prefs) if style_prefs else ""

    def _collect_citations(
        self, ctx: RequestContext, research: Dict[str, Any]
    ) -> List[Citation]:
        """Collect citations from context and research."""
        citations = []

        # Get citations from prior researcher output
        for output in ctx.prior_outputs:
            if output.agent_name == "researcher":
                citations.extend(output.citations)

        # If no prior citations, build from retrieved chunks
        if not citations and ctx.retrieved_chunks:
            for i, chunk in enumerate(ctx.retrieved_chunks, 1):
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
