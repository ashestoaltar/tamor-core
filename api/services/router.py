# api/services/router.py
"""
Agent Router (Phase 6.2)

Central orchestration layer for all chat requests.

Responsibilities:
1. Classify intent (deterministic gates first, then heuristics, then local LLM)
2. Check deterministic paths (hard stops that never go to LLM)
3. Select agent sequence based on intent
4. Execute agents in order, passing outputs between them
5. Compose final response with optional trace metadata

Design principles:
- Router decides, agents execute
- Agents never call each other
- Deterministic paths always take priority
- Local LLM for classification, cloud LLM for generation
- Stateless per-turn (artifacts saved separately)
"""

import hashlib
import json
import logging
import re
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from services.agents import (
    ResearcherAgent,
    WriterAgent,
    EngineerAgent,
    ArchivistAgent,
    PlannerAgent,
    RequestContext,
    AgentOutput,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Classification Cache (LRU)
# ---------------------------------------------------------------------------

class ClassificationCache:
    """
    Simple LRU cache for intent classification results.

    Caches normalized message -> intents mapping to avoid
    repeated local LLM calls for similar queries.
    """

    def __init__(self, max_size: int = 500):
        self._cache: OrderedDict[str, List[str]] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def _normalize(self, message: str) -> str:
        """Normalize message for cache key."""
        # Lowercase, strip whitespace, collapse spaces
        normalized = " ".join(message.lower().split())
        # Hash for consistent key size
        return hashlib.md5(normalized.encode()).hexdigest()

    def get(self, message: str) -> Optional[List[str]]:
        """Get cached intents for message."""
        key = self._normalize(message)
        with self._lock:
            if key in self._cache:
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None

    def set(self, message: str, intents: List[str]) -> None:
        """Cache intents for message."""
        key = self._normalize(message)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self._max_size:
                    # Remove oldest
                    self._cache.popitem(last=False)
            self._cache[key] = intents

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0,
            }


# Global cache instance
_classification_cache = ClassificationCache()

# Model to use for classification (smaller = faster)
CLASSIFICATION_MODEL = "phi3:mini"


@dataclass
class RouteTrace:
    """Debug/audit trace for a routing decision."""
    trace_id: str
    route_type: str  # "deterministic" | "llm_single" | "agent_pipeline"
    intents_detected: List[str] = field(default_factory=list)
    intent_source: str = "heuristic"  # "heuristic" | "local_llm" | "none"
    agent_sequence: List[str] = field(default_factory=list)
    provider_used: str = ""  # "xai" | "anthropic" | "openai" | "ollama" | "none"
    model_used: str = ""  # The actual model name used
    retrieval_used: bool = False
    retrieval_count: int = 0
    timing_ms: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "route_type": self.route_type,
            "intents_detected": self.intents_detected,
            "intent_source": self.intent_source,
            "agent_sequence": self.agent_sequence,
            "provider_used": self.provider_used,
            "model_used": self.model_used,
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
            "engineer": EngineerAgent(),
            "archivist": ArchivistAgent(),
            "planner": PlannerAgent(),
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
                # Theological/biblical research patterns
                r"\b(matthew|mark|luke|john|genesis|exodus|leviticus|deuteronomy|psalm|proverb|isaiah|jeremiah|ezekiel|daniel|romans|corinthians|galatians|ephesians|hebrews|revelation)\s+\d",
                r"\b(torah|gospel|epistle|scripture|biblical|talmud|midrash)\b",
                r"\b(hebrew|greek)\s+(word|term|meaning|root)\b",
                r"\brelationship\s+between\b.*\b(and|teaching|doctrine)\b",
            ],
            "write": [
                r"^(write|draft|compose)\s+(me\s+)?(an?\s+)?(\w+\s+)?(article|essay|summary|document|post|outline|teaching|sermon|paragraph|piece|response|explanation|blog)",
                r"\b(write|draft|compose|create)\s+(an?\s+)?(\w+\s+)?(article|essay|summary|document|post|outline|teaching|sermon|paragraph|piece|response|explanation|blog)",
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
                r"\b(write|create|generate|fix|debug)\s+(\w+\s+)*(code|function|class|script|method)\b",
                r"\bimplement\b",
                r"\b(add|update|modify)\s+(a\s+)?(\w+\s+)*(feature|endpoint|component|function)\b",
                r"\b(code|patch|refactor)\b.*\b(for|to|that)\b",
                r"\bbuild\s+(a\s+)?(\w+\s+)*(component|feature|api|service)\b",
                # Removed overly broad "write me" pattern - was matching prose requests
            ],
            "memory": [
                r"\bremember\s+(that|this|my)\b",
                r"\bdon'?t\s+forget\b",
                r"\bforget\s+(that|this|my)\b",
                r"\bi\s+prefer\b",
                r"\bmy\s+(name|preference|favorite)\b",
                r"\bstore\s+(this|that)\s+(in\s+)?memory\b",
            ],
            "plan": [
                r"\b(plan|organize|break\s*down)\s+(a\s+)?(project|writing|article|series)\b",
                r"\bcreate\s+(a\s+)?(project\s+)?plan\b",
                r"\bhelp\s+me\s+(plan|organize)\b",
                r"\b(multi-?step|complex)\s+(project|writing)\b",
                r"\bsteps\s+(to|for)\s+(write|create|produce)\b",
                # Complex writing requests that need planning
                r"\bi'?d?\s+like\s+to\s+(write|create|draft)\s+(an?\s+)?(article|essay|piece|series)\b",
                r"\b(write|create|draft)\s+(an?\s+)?(article|essay|piece)\s+(exploring|examining|investigating|connecting|comparing)\b",
                r"\bhow\s+.+\s+connects?\s+to\b.*\b(article|essay|piece|write)\b",
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

            # Step 2: Classify intent (heuristics first, then local LLM fallback)
            classify_start = time.time()
            intents = self._classify_intent(ctx.user_message, trace)
            trace.intents_detected = intents
            trace.timing_ms["classify"] = int((time.time() - classify_start) * 1000)

            # Step 3: Decide routing strategy
            agent_sequence = self._select_agent_sequence(intents, ctx)
            trace.agent_sequence = agent_sequence

            # Step 4: Run retrieval if needed
            # Run for project context OR for research intents (library search)
            is_research_intent = any(i in intents for i in ["research", "write", "summarize", "explain"])
            if agent_sequence and (ctx.project_id or is_research_intent):
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

    def _references_project(self, message: str) -> bool:
        """Check if the message references project-specific context."""
        msg = message.lower()
        # Patterns that suggest the user wants project context
        project_indicators = [
            r"\b(the|this|my|our)\s+(code|codebase|project|repo|file|function|class|module)\b",
            r"\b(fix|update|modify|refactor|change)\s+(the|this|my)\b",
            r"\bin\s+(the|this|my)\s+\w+\.(py|js|ts|jsx|tsx|go|rs)\b",
            r"\b(based on|following|using)\s+(the|this|our)\s+(pattern|style|convention)\b",
            r"\badd\s+(to|into)\s+(the|this|my)\b",
            r"\b(existing|current)\s+\w+",
        ]
        for pattern in project_indicators:
            if re.search(pattern, msg, re.IGNORECASE):
                return True
        return False

    def _is_scholarly_question(self, message: str) -> bool:
        """
        Check if the message is a scholarly/theological question.

        These questions should route to the researcher agent (xAI/Grok)
        even without project context, as they benefit from Grok's
        theological research capabilities.
        """
        msg = message.lower()
        scholarly_indicators = [
            # Biblical books and references
            r"\b(matthew|mark|luke|john|acts|romans|corinthians|galatians|ephesians|philippians|colossians|thessalonians|timothy|titus|philemon|hebrews|james|peter|jude|revelation)\s+\d",
            r"\b(genesis|exodus|leviticus|numbers|deuteronomy|joshua|judges|ruth|samuel|kings|chronicles|ezra|nehemiah|esther|job|psalm|proverbs|ecclesiastes|song|isaiah|jeremiah|lamentations|ezekiel|daniel|hosea|joel|amos|obadiah|jonah|micah|nahum|habakkuk|zephaniah|haggai|zechariah|malachi)\b",
            # Theological terms
            r"\b(torah|tanakh|talmud|midrash|mishnah|gemara|targum)\b",
            r"\b(gospel|epistle|scripture|biblical|covenant|commandment|sabbath|passover|pentecost|tabernacle|temple)\b",
            r"\b(hebrew|greek|aramaic)\s+(word|term|meaning|root|text)\b",
            r"\b(law|grace|faith|works|righteousness|justification|sanctification|atonement|redemption|salvation)\b.*\b(bible|scripture|paul|jesus|moses|god)\b",
            # Hermeneutical patterns
            r"\b(exegesis|hermeneutic|interpretation|context|original|meaning)\b.*\b(text|passage|verse|scripture)\b",
            r"\bwhat\s+(does|did)\s+(jesus|paul|moses|david|peter|james)\s+(say|teach|mean)\b",
            r"\b(christian|jewish|messianic)\s+(teaching|doctrine|tradition|interpretation)\b",
            # Direct theological questions
            r"\brelationship\s+between\b.*\b(law|grace|faith|works|old testament|new testament)\b",
            r"\b(fulfilled|abolish|fulfill)\b.*\b(law|commandment|torah)\b",
        ]
        for pattern in scholarly_indicators:
            if re.search(pattern, msg, re.IGNORECASE):
                return True
        return False

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

    def _classify_intent_heuristic(self, message: str) -> List[str]:
        """
        Classify user intent using heuristic patterns.

        Returns list of detected intents, most specific first.
        """
        msg = message.lower()
        detected = []

        # Check patterns in priority order
        # plan before write: complex writing requests should be planned first
        priority_order = ["memory", "plan", "code", "write", "research", "summarize", "explain"]

        for intent in priority_order:
            patterns = self.intent_patterns.get(intent, [])
            for pattern in patterns:
                if re.search(pattern, msg, re.IGNORECASE):
                    if intent not in detected:
                        detected.append(intent)
                    break

        return detected

    def _classify_intent_local_llm(self, message: str, use_cache: bool = True) -> Tuple[List[str], bool]:
        """
        Classify user intent using local LLM (Ollama).

        Uses phi3:mini for faster inference and caches results.
        Used as fallback when heuristics don't match.

        Returns:
            (intents, from_cache) tuple
        """
        # Check cache first
        if use_cache:
            cached = _classification_cache.get(message)
            if cached is not None:
                return (cached, True)

        try:
            from services.llm_service import get_local_llm_client

            client = get_local_llm_client()
            if not client:
                return ([], False)

            prompt = f"""Classify the following user message into one or more intent categories.

Categories:
- research: Looking up information, analyzing sources, comparing documents
- write: Creating prose content, articles, summaries, essays
- summarize: Condensing content, getting the gist, TL;DR
- explain: Understanding concepts, how things work, why something is
- code: Writing, fixing, or modifying code, implementing features
- memory: Storing preferences, remembering information, forgetting things
- general: General conversation, greetings, chitchat

User message: "{message}"

Respond with ONLY a JSON array of intent strings, most specific first.
Example: ["research", "summarize"]
Example: ["code"]
Example: ["general"]

JSON array:"""

            # Use phi3:mini for faster classification
            response = client.generate(prompt, model=CLASSIFICATION_MODEL, temperature=0.1)

            # Parse JSON from response
            response = response.strip()
            # Handle markdown code blocks
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
                response = response.strip()

            intents = json.loads(response)

            # Validate intents
            valid_intents = ["research", "write", "summarize", "explain", "code", "memory"]
            filtered = [i for i in intents if i in valid_intents]

            # Cache the result
            if use_cache and filtered:
                _classification_cache.set(message, filtered)

            return (filtered, False)

        except Exception as e:
            logger.warning(f"Local LLM classification failed: {e}")
            return ([], False)

    def _classify_intent(self, message: str, trace: Optional[RouteTrace] = None) -> List[str]:
        """
        Classify user intent, trying heuristics first, then local LLM.

        Returns list of detected intents, most specific first.
        """
        # Try heuristics first (fast)
        intents = self._classify_intent_heuristic(message)

        if intents:
            if trace:
                trace.intent_source = "heuristic"
            return intents

        # Fall back to local LLM if available (with caching)
        intents, from_cache = self._classify_intent_local_llm(message)

        if intents:
            if trace:
                trace.intent_source = "local_llm_cache" if from_cache else "local_llm"
            return intents

        if trace:
            trace.intent_source = "none"
        return []

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

        # Writing tasks: Researcher → Writer (with project OR scholarly topic)
        if primary_intent == "write":
            is_scholarly = self._is_scholarly_question(ctx.user_message)
            if ctx.project_id or is_scholarly:
                return ["researcher", "writer"]
            # Simple writing without theological content - just Writer
            return ["writer"]

        # Research tasks: Researcher (with project context OR scholarly question)
        if primary_intent == "research":
            # Scholarly/theological questions route to researcher even without project
            # This enables xAI/Grok for theological research
            is_scholarly = self._is_scholarly_question(ctx.user_message)
            if ctx.project_id or is_scholarly:
                if "summarize" in intents or "write" in intents:
                    return ["researcher", "writer"]
                return ["researcher"]
            return []  # No project and not scholarly, use single LLM

        # Summarization: Researcher → Writer (for polish)
        if primary_intent == "summarize":
            if ctx.project_id:  # Has files to summarize
                return ["researcher", "writer"]
            return []  # No files, use single LLM

        # Explanation: Use Researcher if project context OR scholarly question
        if primary_intent == "explain":
            is_scholarly = self._is_scholarly_question(ctx.user_message)
            if ctx.project_id or is_scholarly:
                return ["researcher", "writer"]
            return []  # General explanation, use single LLM

        # Code: Route to Engineer (with Researcher only if referencing project)
        if primary_intent == "code":
            if ctx.project_id and self._references_project(ctx.user_message):
                return ["researcher", "engineer"]
            return ["engineer"]

        # Memory: Route to Archivist
        if primary_intent == "memory":
            return ["archivist"]

        # Planning: Route to Planner
        # Planner works without project - will prompt user to create one if needed
        if primary_intent == "plan":
            return ["planner"]

        return []

    def _run_retrieval(
        self, ctx: RequestContext, intents: List[str]
    ) -> RequestContext:
        """
        Run semantic retrieval to populate ctx.retrieved_chunks.

        For research/write intents, ensures coverage across all project files
        by retrieving more chunks and diversifying by file.

        Also searches global library for supplemental sources.
        """
        project_chunks = []
        library_chunks = []

        # Step 1: Search project files if project context exists
        if ctx.project_id and ctx.user_id:
            try:
                from services.file_semantic_service import semantic_search_project_files
                from utils.db import get_db

                is_broad_query = "research" in intents or "write" in intents or "summarize" in intents

                if is_broad_query:
                    conn = get_db()
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT COUNT(*) FROM project_files WHERE project_id = ?",
                        (ctx.project_id,)
                    )
                    file_count = cur.fetchone()[0]
                    conn.close()
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

                project_chunks = result.get("results", [])

                if is_broad_query and project_chunks:
                    project_chunks = self._diversify_chunks(project_chunks, max_per_file=5, total_max=25)

            except Exception as e:
                logger.warning(f"Project file retrieval failed: {e}")

        # Step 2: Search global library for supplemental sources
        # Do this for research/write/summarize intents regardless of project context
        is_research_intent = any(i in intents for i in ["research", "write", "summarize", "explain"])
        if is_research_intent:
            try:
                from services.library.search_service import LibrarySearchService

                search_service = LibrarySearchService()
                # Use 'all' scope if project exists (marks project refs), else 'library'
                scope = "all" if ctx.project_id else "library"
                results = search_service.search(
                    query=ctx.user_message,
                    scope=scope,
                    project_id=ctx.project_id,
                    limit=10,
                    min_score=0.3,
                )

                # Convert SearchResult to dict format matching project chunks
                for r in results:
                    library_chunks.append({
                        "file_id": r.library_file_id,
                        "filename": r.filename,
                        "chunk_index": r.chunk_index,
                        "content": r.content,
                        "score": r.score,
                        "page": r.page,
                        "source": "library",
                    })

                logger.info(f"Library search returned {len(library_chunks)} results")

            except Exception as e:
                logger.warning(f"Library retrieval failed: {e}")

        # Step 3: Merge results - project chunks first (higher priority), then library
        # Deduplicate by content hash to avoid showing same text twice
        seen_content = set()
        merged = []

        # Project chunks first
        for chunk in project_chunks:
            content_key = chunk.get("content", "")[:200]
            if content_key not in seen_content:
                seen_content.add(content_key)
                chunk["source"] = "project"
                merged.append(chunk)

        # Then library chunks
        for chunk in library_chunks:
            content_key = chunk.get("content", "")[:200]
            if content_key not in seen_content:
                seen_content.add(content_key)
                merged.append(chunk)

        ctx.retrieved_chunks = merged[:30]  # Cap total chunks

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

        # Capture provider info from agent outputs for trace
        # Use the last agent that actually used an LLM
        for output in reversed(outputs):
            if output.provider_used:
                trace.provider_used = output.provider_used
                trace.model_used = output.model_used
                break

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

        # Format content based on agent type
        if final_output.is_final:
            content = final_output.content if isinstance(final_output.content, str) else str(final_output.content)
            # Append formatted citations if we have them
            if all_citations:
                content = self._append_formatted_citations(content, all_citations)
        elif final_output.agent_name == "archivist":
            # Format archivist output for user display
            content = self._format_archivist_output(final_output)
        elif final_output.agent_name == "researcher":
            # Non-final research output - format for display
            content = self._format_research_output(final_output)
        else:
            content = str(final_output.content)

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

    def _format_archivist_output(self, output: AgentOutput) -> str:
        """Format archivist output for user display."""
        if not isinstance(output.content, dict):
            return str(output.content)

        data = output.content
        action = data.get("action", "")

        # Handle explicit memory actions
        if action == "stored":
            content = data.get("content", "")
            category = data.get("category", "general")
            return f"Got it! I'll remember that. (Saved as {category} memory)"

        if action == "preference_stored":
            return "I've noted your preference."

        if action == "forgotten":
            count = data.get("count", 0)
            if count > 0:
                return f"Done. I've removed {count} related memory item{'s' if count > 1 else ''}."
            return "I couldn't find any matching memories to forget."

        if action == "no_action":
            return data.get("reason", "No memory action taken.")

        # Handle background analysis (shouldn't normally be shown)
        analysis = data.get("analysis", "")
        if analysis:
            stored = data.get("memories_stored", 0)
            if stored > 0:
                return f"(Noted {stored} item{'s' if stored > 1 else ''} for future reference)"
            return ""

        return ""


# Singleton instance
_router_instance: Optional[AgentRouter] = None
_model_warmed: bool = False
_warming_lock = threading.Lock()


def _warm_classification_model() -> None:
    """
    Pre-warm the classification model by running a dummy query.

    This loads the model into memory so first real query is fast.
    Runs in background thread to not block startup.
    """
    global _model_warmed

    with _warming_lock:
        if _model_warmed:
            return
        _model_warmed = True

    try:
        from services.llm_service import get_local_llm_client

        client = get_local_llm_client()
        if not client:
            return

        logger.info(f"Pre-warming classification model ({CLASSIFICATION_MODEL})...")
        start = time.time()

        # Simple query to load model into memory
        client.generate(
            "Classify: hello",
            model=CLASSIFICATION_MODEL,
            temperature=0.1,
        )

        elapsed = time.time() - start
        logger.info(f"Classification model warmed in {elapsed:.1f}s")

    except Exception as e:
        logger.warning(f"Failed to warm classification model: {e}")


def get_router() -> AgentRouter:
    """Get or create the router singleton."""
    global _router_instance

    if _router_instance is None:
        _router_instance = AgentRouter()
        # Pre-warm in background thread
        threading.Thread(target=_warm_classification_model, daemon=True).start()

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


def get_classification_cache_stats() -> Dict[str, Any]:
    """Get classification cache statistics."""
    return _classification_cache.stats()
