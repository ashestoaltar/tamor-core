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
import re
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


def _load_writer_persona() -> str:
    """Load Writer persona from modes.json."""
    import os
    modes_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config",
        "modes.json"
    )
    try:
        import json
        with open(modes_path, "r") as f:
            modes = json.load(f)
        return modes.get("Writer", {}).get("persona", "")
    except Exception:
        return ""

# Load persona at module level
_WRITER_PERSONA = _load_writer_persona()

WRITER_SYSTEM_PROMPT = _WRITER_PERSONA if _WRITER_PERSONA else """You are a Writer Agent. Your role is to transform research notes into polished, readable prose.

Write like a real person, not like an AI. Be direct. Lead with substance. No filler phrases, no generic analogies, no artificial warmth.

## Hard Rules
- ONLY use information from the provided sources
- NEVER invent facts or add from your own knowledge
- Include inline citations: "According to [1]..." or "The text states [2]..."
- Do NOT include structural scaffolding like "Opening:", "Main Body:", "Conclusion:"
- Do NOT include word count targets or meta-commentary
- Do NOT wrap in JSON or markdown code blocks
- The reader should forget they're reading AI output"""


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

        # Detect explicit length constraints (these override templates)
        length_constraint = self._detect_length_constraint(ctx.user_message)

        # Format research notes for the writer
        # Suppress recommended_structure when user specified explicit length
        research_text = self._format_research(
            research_data,
            suppress_structure=length_constraint is not None
        )

        # Include full library sources if available (for better context)
        sources_text = ""
        if ctx.retrieved_chunks:
            sources_text = self._format_sources(ctx.retrieved_chunks)

        # Determine output type and get template guidance
        template_name = self._detect_output_type(ctx.user_message)
        # Skip template guidance if user specified explicit length
        template_guidance = "" if length_constraint else self._get_template_guidance(template_name)

        # Build length constraint section
        length_section = length_constraint["constraint_text"] if length_constraint else ""

        user_message = f"""## Writing Request
{ctx.user_message}

{length_section}

{template_guidance}

{research_text}

{sources_text}

Write the requested content. Include inline citations [1], [2], etc."""

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
                            "template": template_name,
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

    def _format_research(self, research: Dict[str, Any], suppress_structure: bool = False) -> str:
        """Format research data for the writer prompt.

        Args:
            research: Research data dict from Researcher agent
            suppress_structure: If True, omit "Recommended Structure" section
                               (used when user specified explicit length constraint)
        """
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

        # Recommended structure (skip if user specified explicit length constraint)
        if not suppress_structure:
            structure = research.get("recommended_structure", [])
            if structure:
                lines.append("### Recommended Structure")
                for i, section in enumerate(structure, 1):
                    lines.append(f"{i}. {section}")
                lines.append("")

        return "\n".join(lines)

    def _detect_length_constraint(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Detect explicit length constraints from user message.

        These are HARD constraints that override templates and research structure.
        Returns dict with min_words, max_words, and constraint_text for prompt.
        """
        msg = message.lower()

        # "a paragraph" - single paragraph, 100-200 words
        if re.search(r"\b(a|one|single)\s+paragraph\b", msg):
            return {
                "min_words": 80,
                "max_words": 200,
                "format": "single paragraph",
                "constraint_text": (
                    "## HARD LENGTH CONSTRAINT\n"
                    "The user requested A PARAGRAPH. This means:\n"
                    "- ONE paragraph only, 100-200 words maximum\n"
                    "- NO headers, NO sections, NO multi-paragraph structure\n"
                    "- Exceed 200 words = FAILURE\n"
                    "This constraint OVERRIDES all templates and structure suggestions."
                )
            }

        # "brief" - 400-800 words
        if re.search(r"\b(brief|briefly)\b", msg):
            return {
                "min_words": 300,
                "max_words": 800,
                "format": "brief",
                "constraint_text": (
                    "## HARD LENGTH CONSTRAINT\n"
                    "The user requested BRIEF output. This means:\n"
                    "- 400-800 words maximum\n"
                    "- Exceed 800 words = FAILURE\n"
                    "This constraint OVERRIDES all templates and structure suggestions."
                )
            }

        # "short" - 800-1200 words
        if re.search(r"\bshort\b", msg):
            return {
                "min_words": 600,
                "max_words": 1200,
                "format": "short",
                "constraint_text": (
                    "## HARD LENGTH CONSTRAINT\n"
                    "The user requested SHORT output. This means:\n"
                    "- 800-1,200 words maximum\n"
                    "- Exceed 1,200 words = FAILURE\n"
                    "This constraint OVERRIDES all templates and structure suggestions."
                )
            }

        return None

    def _detect_output_type(self, message: str) -> str:
        """Detect what kind of output the user wants and return template name."""
        msg = message.lower()
        templates = WRITER_TEMPLATES.get("templates", {})

        # Check for explicit template matches (order matters - most specific first)
        if any(w in msg for w in ["torah portion", "parashah", "parsha"]):
            return "torah_portion"
        elif any(w in msg for w in ["deep dive", "research piece", "scholarly article"]):
            return "deep_dive"
        elif any(w in msg for w in ["sermon", "homily", "preach", "pulpit", "for sunday", "sunday message"]):
            # Only sermon when explicitly requested
            return "sermon"
        elif any(w in msg for w in ["blog", "blog post"]):
            return "blog_post"
        elif any(w in msg for w in ["summary", "summarize", "brief overview"]):
            return "summary"
        else:
            # Default to article for: "teaching", "short teaching", "article", "piece",
            # "write about", "write on", or anything else
            return "article"

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
