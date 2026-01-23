# api/services/router.py
"""
Agent Router (Phase 6.2)

Central orchestration layer for all chat requests.

Responsibilities:
1. Classify intent (deterministic gates first, then heuristics)
2. Check deterministic paths (hard stops that never go to LLM)
3. Select agent sequence based on intent
4. Execute agents in order, passing outputs between them
5. Compose final response with optional trace metadata

Design principles:
- Router decides, agents execute
- Agents never call each other
- Deterministic paths always take priority
- Stateless per-turn (artifacts saved separately)
"""

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from services.agents import ResearcherAgent, WriterAgent, RequestContext, AgentOutput

logger = logging.getLogger(__name__)


@dataclass
class RouteTrace:
    """Debug/audit trace for a routing decision."""
    trace_id: str
    route_type: str  # "deterministic" | "llm_single" | "agent_pipeline"
    intents_detected: List[str] = field(default_factory=list)
    agent_sequence: List[str] = field(default_factory=list)
    retrieval_used: bool = False
    retrieval_count: int = 0
    timing_ms: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "route_type": self.route_type,
            "intents_detected": self.intents_detected,
            "agent_sequence": self.agent_sequence,
            "retrieval_used": self.retrieval_used,
            "retrieval_count": self.retrieval_count,
            "timing_ms": self.timing_ms,
            "errors": self.errors,
        }


@dataclass
class RouterResult:
    """Result from the router, ready for chat_api to return."""
    content: str
    agent_outputs: List[AgentOutput] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)
    trace: Optional[RouteTrace] = None
    handled_by: str = "router"  # "deterministic" | "llm" | "agent_pipeline"

    def to_response_dict(self, include_trace: bool = False) -> Dict[str, Any]:
        """Convert to API response format."""
        result = {
            "content": self.content,
            "handled_by": self.handled_by,
        }

        if self.citations:
            result["citations"] = self.citations

        if include_trace and self.trace:
            result["router_trace"] = self.trace.to_dict()

        return result


class AgentRouter:
    """
    Main router that orchestrates all chat requests.

    Usage:
        router = AgentRouter()
        result = router.route(ctx, include_trace=debug_mode)
    """

    def __init__(self):
        # Initialize available agents
        self.agents = {
            "researcher": ResearcherAgent(),
            "writer": WriterAgent(),
        }

        # Intent patterns for heuristic classification
        self._init_intent_patterns()

    def _init_intent_patterns(self):
        """Initialize regex patterns for intent detection."""
        self.intent_patterns = {
            # Tier 0: Deterministic gates (handled separately)
            "deterministic_lookup": [
                r"\b(drawing|dwg|part)\s*(number|#|num)?\s*[:=]?\s*[A-Z0-9-]+",
                r"\bhow many (tasks|reminders|files)\b",
                r"\blist (my )?(tasks|reminders)\b",
            ],
            "pipeline_action": [
                r"\b(run|execute|start)\s+(pipeline|workflow)\b",
                r"\b(export|convert|transform)\s+(to|as)\b",
                r"\btranscribe\b",
            ],

            # Tier 1: Agent routing patterns
            "research": [
                r"\b(research|analyze|find|search|look up|investigate)\b",
                r"\bwhat (do|does|did|is|are|was|were)\b.*\b(say|mention|state|indicate)\b",
                r"\baccording to\b",
                r"\bin the (document|file|source|transcript)",
                r"\bcompare\b.*\b(and|with|to)\b",
            ],
            "write": [
                r"\b(write|draft|compose|create)\s+(an?\s+)?(article|essay|summary|document|post|outline)",
                r"\b(summarize|explain)\b.*\b(in|as)\s+(an?\s+)?(article|essay|paragraph)",
                r"\bwrite\s+(about|on)\b",
            ],
            "summarize": [
                r"\bsummarize\b",
                r"\bgive\s+(me\s+)?(a\s+)?summary\b",
                r"\bwhat('s| is) the (main|key|gist)\b",
                r"\btl;?dr\b",
            ],
            "explain": [
                r"\bexplain\b",
                r"\bwhat (is|are|does)\b",
                r"\bhow (do|does|did|to)\b",
                r"\bwhy (is|are|does|did)\b",
            ],
            "code": [
                r"\b(write|create|generate|fix|debug)\s+(code|function|class|script)\b",
                r"\bimplement\b",
                r"\b(add|update|modify)\s+(a\s+)?(feature|endpoint|component)\b",
            ],
        }

    def route(
        self,
        ctx: RequestContext,
        include_trace: bool = False,
    ) -> RouterResult:
        """
        Main routing entrypoint.

        Args:
            ctx: Request context with message, history, memories, etc.
            include_trace: Whether to include debug trace in result

        Returns:
            RouterResult with content and optional trace
        """
        start_time = time.time()
        trace = RouteTrace(
            trace_id=str(uuid.uuid4())[:8],
            route_type="unknown",
        )

        try:
            # Step 1: Check deterministic gates
            deterministic_result = self._check_deterministic(ctx)
            if deterministic_result:
                trace.route_type = "deterministic"
                trace.timing_ms["total"] = int((time.time() - start_time) * 1000)
                return RouterResult(
                    content=deterministic_result,
                    trace=trace if include_trace else None,
                    handled_by="deterministic",
                )

            # Step 2: Classify intent
            intents = self._classify_intent(ctx.user_message)
            trace.intents_detected = intents

            # Step 3: Decide routing strategy
            agent_sequence = self._select_agent_sequence(intents, ctx)
            trace.agent_sequence = agent_sequence

            # Step 4: Run retrieval if needed
            if agent_sequence and ctx.project_id:
                ctx = self._run_retrieval(ctx, intents)
                trace.retrieval_used = bool(ctx.retrieved_chunks)
                trace.retrieval_count = len(ctx.retrieved_chunks)

            # Step 5: Execute agent pipeline or fall back to single LLM
            if agent_sequence:
                trace.route_type = "agent_pipeline"
                result = self._execute_pipeline(ctx, agent_sequence, trace)
            else:
                trace.route_type = "llm_single"
                result = self._execute_single_llm(ctx, trace)

            trace.timing_ms["total"] = int((time.time() - start_time) * 1000)
            result.trace = trace if include_trace else None
            return result

        except Exception as e:
            logger.error(f"Router error: {e}", exc_info=True)
            trace.errors.append(str(e))
            trace.timing_ms["total"] = int((time.time() - start_time) * 1000)
            return RouterResult(
                content=f"I encountered an error processing your request. Please try again.",
                trace=trace if include_trace else None,
                handled_by="error",
            )

    def _check_deterministic(self, ctx: RequestContext) -> Optional[str]:
        """
        Check for deterministic gates that bypass LLM entirely.

        Returns response string if handled, None otherwise.
        """
        msg = ctx.user_message.lower().strip()

        # Drawing number lookup pattern
        for pattern in self.intent_patterns.get("deterministic_lookup", []):
            if re.search(pattern, msg, re.IGNORECASE):
                # This would call a deterministic lookup service
                # For now, return None to let it fall through
                # In production: return deterministic_lookup_service.lookup(ctx)
                pass

        # Pipeline/action patterns - don't handle yet, let existing code handle
        for pattern in self.intent_patterns.get("pipeline_action", []):
            if re.search(pattern, msg, re.IGNORECASE):
                # Return None to let existing handlers process
                pass

        return None

    def _classify_intent(self, message: str) -> List[str]:
        """
        Classify user intent using heuristic patterns.

        Returns list of detected intents, most specific first.
        """
        msg = message.lower()
        detected = []

        # Check patterns in priority order
        priority_order = ["write", "research", "summarize", "explain", "code"]

        for intent in priority_order:
            patterns = self.intent_patterns.get(intent, [])
            for pattern in patterns:
                if re.search(pattern, msg, re.IGNORECASE):
                    if intent not in detected:
                        detected.append(intent)
                    break

        return detected

    def _select_agent_sequence(
        self, intents: List[str], ctx: RequestContext
    ) -> List[str]:
        """
        Select which agents to run based on classified intents.

        Returns ordered list of agent names.
        """
        if not intents:
            return []  # Fall back to single LLM

        primary_intent = intents[0]

        # Writing tasks: Researcher → Writer
        if primary_intent == "write":
            return ["researcher", "writer"]

        # Research tasks: Researcher only (or + Writer if "summarize" also detected)
        if primary_intent == "research":
            if "summarize" in intents or "write" in intents:
                return ["researcher", "writer"]
            return ["researcher"]

        # Summarization: Researcher → Writer (for polish)
        if primary_intent == "summarize":
            if ctx.project_id:  # Has files to summarize
                return ["researcher", "writer"]
            return []  # No files, use single LLM

        # Explanation: Could use Researcher if project context exists
        if primary_intent == "explain":
            if ctx.project_id:
                return ["researcher", "writer"]
            return []  # General explanation, use single LLM

        # Code: Not handled by these agents yet (Phase 6.2 expansion)
        if primary_intent == "code":
            return []  # Fall back to single LLM for now

        return []

    def _run_retrieval(
        self, ctx: RequestContext, intents: List[str]
    ) -> RequestContext:
        """
        Run semantic retrieval to populate ctx.retrieved_chunks.

        For research/write intents, ensures coverage across all project files
        by retrieving more chunks and diversifying by file.
        """
        if not ctx.project_id or not ctx.user_id:
            return ctx

        try:
            from services.file_semantic_service import semantic_search_project_files
            from utils.db import get_db

            is_broad_query = "research" in intents or "write" in intents or "summarize" in intents

            if is_broad_query:
                # For broad queries, ensure we get chunks from ALL files
                # First, find how many files are in the project
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    "SELECT COUNT(*) FROM project_files WHERE project_id = ?",
                    (ctx.project_id,)
                )
                file_count = cur.fetchone()[0]
                conn.close()

                # Get enough chunks to cover all files (5 per file minimum)
                top_k = max(50, file_count * 10)
            else:
                top_k = 10

            result = semantic_search_project_files(
                project_id=ctx.project_id,
                user_id=ctx.user_id,
                query=ctx.user_message,
                top_k=top_k,
                include_answer=False,
            )

            chunks = result.get("results", [])

            # For broad queries, ensure we have chunks from each file
            if is_broad_query and chunks:
                chunks = self._diversify_chunks(chunks, max_per_file=5, total_max=25)

            ctx.retrieved_chunks = chunks

        except Exception as e:
            logger.warning(f"Retrieval failed: {e}")
            ctx.retrieved_chunks = []

        return ctx

    def _diversify_chunks(
        self, chunks: List[Dict[str, Any]], max_per_file: int = 5, total_max: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Ensure chunk diversity across files.

        Takes top chunks but limits per-file count to ensure all files
        are represented.
        """
        from collections import defaultdict

        # Group by file
        by_file: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for chunk in chunks:
            file_id = chunk.get("file_id")
            if file_id is not None:
                by_file[file_id].append(chunk)

        # Take top N from each file (already sorted by relevance)
        diversified = []
        for file_id, file_chunks in by_file.items():
            diversified.extend(file_chunks[:max_per_file])

        # Sort by score descending and limit total
        diversified.sort(key=lambda c: c.get("score", 0), reverse=True)
        return diversified[:total_max]

    def _execute_pipeline(
        self, ctx: RequestContext, agent_sequence: List[str], trace: RouteTrace
    ) -> RouterResult:
        """
        Execute a sequence of agents, passing outputs between them.
        """
        outputs: List[AgentOutput] = []

        for agent_name in agent_sequence:
            agent = self.agents.get(agent_name)
            if not agent:
                trace.errors.append(f"Unknown agent: {agent_name}")
                continue

            step_start = time.time()

            # Pass prior outputs to context
            ctx.prior_outputs = outputs

            # Run agent
            output = agent.run(ctx)
            outputs.append(output)

            trace.timing_ms[agent_name] = int((time.time() - step_start) * 1000)

            # Check for errors
            if output.error:
                trace.errors.append(f"{agent_name}: {output.error}")
                # Continue anyway - let next agent work with partial data

        # Compose final result from last output
        final_output = outputs[-1] if outputs else None

        if not final_output:
            return RouterResult(
                content="No agent produced output.",
                handled_by="agent_pipeline",
            )

        # Collect all citations
        all_citations = []
        for output in outputs:
            for citation in output.citations:
                all_citations.append({
                    "file_id": citation.file_id,
                    "filename": citation.filename,
                    "page": citation.page,
                    "snippet": citation.snippet,
                })

        # Format content
        if final_output.is_final:
            content = final_output.content if isinstance(final_output.content, str) else str(final_output.content)
            # Append formatted citations if we have them
            if all_citations:
                content = self._append_formatted_citations(content, all_citations)
        else:
            # Non-final output (e.g., researcher only) - format for display
            content = self._format_research_output(final_output)

        return RouterResult(
            content=content,
            agent_outputs=outputs,
            citations=all_citations,
            handled_by="agent_pipeline",
        )

    def _execute_single_llm(self, ctx: RequestContext, trace: RouteTrace) -> RouterResult:
        """
        Fall back to single LLM call (existing behavior).
        """
        # This path returns None to signal chat_api should use its existing logic
        # In future, we could move all LLM calls here
        return RouterResult(
            content="",  # Empty signals "use existing flow"
            handled_by="llm_single_passthrough",
        )

    def _append_formatted_citations(self, content: str, citations: List[Dict[str, Any]]) -> str:
        """
        Append properly formatted citations to the content.

        Format: filename (p. X) or filename if no page
        """
        if not citations:
            return content

        # Deduplicate citations by file_id, collecting all pages
        seen_files: Dict[int, Dict[str, Any]] = {}
        for c in citations:
            file_id = c.get("file_id")
            if file_id is None:
                continue

            if file_id not in seen_files:
                seen_files[file_id] = {
                    "filename": c.get("filename", "unknown"),
                    "pages": set(),
                }

            page = c.get("page")
            if page:
                seen_files[file_id]["pages"].add(page)

        if not seen_files:
            return content

        # Format citations
        lines = ["\n\n---\n**Sources:**"]
        for i, (file_id, info) in enumerate(seen_files.items(), 1):
            filename = info["filename"]
            pages = sorted(info["pages"])

            if pages:
                if len(pages) == 1:
                    page_str = f"p. {pages[0]}"
                else:
                    page_str = f"pp. {', '.join(str(p) for p in pages)}"
                lines.append(f"[{i}] {filename} ({page_str})")
            else:
                lines.append(f"[{i}] {filename}")

        return content + "\n".join(lines)

    def _format_research_output(self, output: AgentOutput) -> str:
        """Format researcher output for user display."""
        if not isinstance(output.content, dict):
            return str(output.content)

        research = output.content
        lines = []

        if research.get("summary"):
            lines.append(f"**Summary:** {research['summary']}\n")

        findings = research.get("key_findings", [])
        if findings:
            lines.append("**Key Findings:**")
            for f in findings[:10]:
                if isinstance(f, dict):
                    lines.append(f"- {f.get('finding', '')} {f.get('source', '')}")
                else:
                    lines.append(f"- {f}")
            lines.append("")

        themes = research.get("themes", [])
        if themes:
            lines.append(f"**Themes:** {', '.join(themes)}\n")

        gaps = research.get("gaps", [])
        if gaps:
            lines.append("**Information Gaps:**")
            for g in gaps:
                lines.append(f"- {g}")
            lines.append("")

        return "\n".join(lines)


# Singleton instance
_router_instance: Optional[AgentRouter] = None


def get_router() -> AgentRouter:
    """Get or create the router singleton."""
    global _router_instance
    if _router_instance is None:
        _router_instance = AgentRouter()
    return _router_instance


def route_chat(ctx: RequestContext, include_trace: bool = False) -> RouterResult:
    """
    Convenience function for routing a chat request.

    Args:
        ctx: Request context
        include_trace: Whether to include debug trace

    Returns:
        RouterResult with content and optional trace
    """
    return get_router().route(ctx, include_trace=include_trace)
