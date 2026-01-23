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
import time
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentOutput, Citation, RequestContext
from services.llm_service import get_llm_client, get_model_name

logger = logging.getLogger(__name__)


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

        # Add style preferences from memories if available
        style_context = self._extract_style_preferences(ctx.memories)
        if style_context:
            system_prompt += f"\n\n## User Style Preferences\n{style_context}"

        # Format research notes for the writer
        research_text = self._format_research(research_data)

        # Determine output type from user message
        output_type = self._detect_output_type(ctx.user_message)

        user_message = f"""## Writing Request
{ctx.user_message}

## Output Type
{output_type}

{research_text}

Write the requested content based on these research notes. Include inline citations [1], [2], etc."""

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
        """Extract research data from prior outputs or input payload."""
        # Check input payload first
        if input_payload and "research" in input_payload:
            return input_payload["research"]

        # Check prior outputs from Researcher
        for output in ctx.prior_outputs:
            if output.agent_name == "researcher" and isinstance(output.content, dict):
                return output.content

        # Fallback: check for raw retrieved chunks (no researcher ran)
        if ctx.retrieved_chunks:
            return {
                "summary": "Direct sources provided (no prior research analysis)",
                "key_findings": [
                    {"finding": c.get("content", "")[:200], "source": f"[{i}]", "confidence": "medium"}
                    for i, c in enumerate(ctx.retrieved_chunks[:5], 1)
                ],
                "themes": [],
                "contradictions": [],
                "gaps": [],
                "open_questions": [],
                "recommended_structure": [],
            }

        return None

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
        """Detect what kind of output the user wants."""
        msg = message.lower()

        if any(w in msg for w in ["article", "blog", "post"]):
            return "Article (800-1200 words, engaging, with introduction and conclusion)"
        elif any(w in msg for w in ["summary", "summarize", "overview"]):
            return "Summary (200-400 words, key points only)"
        elif any(w in msg for w in ["explain", "explanation"]):
            return "Explanation (clear, educational, step-by-step if needed)"
        elif any(w in msg for w in ["outline", "structure"]):
            return "Outline (hierarchical structure with brief descriptions)"
        elif any(w in msg for w in ["draft", "first draft"]):
            return "Draft (complete but may need revision)"
        elif any(w in msg for w in ["brief", "short", "quick"]):
            return "Brief (100-200 words, essential points only)"
        else:
            return "Standard response (appropriate length for the request)"

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
