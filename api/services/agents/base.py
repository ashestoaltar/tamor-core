# api/services/agents/base.py
"""
Base Agent Interface (Phase 6.2)

All agents inherit from BaseAgent and implement:
- can_handle(): whether this agent can process the given intent
- run(): execute the agent's task and return structured output

Agents are stateless per-turn. Any persistent artifacts are saved to DB separately.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RequestContext:
    """
    Context passed to all agents by the Router.
    Contains everything an agent needs to do its job.
    """
    user_message: str
    conversation_id: Optional[int] = None
    project_id: Optional[int] = None
    user_id: Optional[int] = None
    history: List[Dict[str, str]] = field(default_factory=list)
    memories: List[Dict[str, Any]] = field(default_factory=list)
    mode: str = "Auto"

    # Retrieved context (populated by Router before agent runs)
    retrieved_chunks: List[Dict[str, Any]] = field(default_factory=list)

    # Scripture context (populated by chat_api when references detected)
    scripture_context: Optional[str] = None

    # Library context (populated by chat_api for relevant library content)
    library_context: Optional[str] = None

    # Project files context (populated by chat_api for project documents)
    project_files_context: Optional[str] = None

    # Previous agent outputs in the pipeline (for chaining)
    prior_outputs: List["AgentOutput"] = field(default_factory=list)


@dataclass
class Citation:
    """A source reference for a claim or piece of content."""
    file_id: Optional[int] = None
    filename: Optional[str] = None
    chunk_index: Optional[int] = None
    page: Optional[int] = None
    snippet: str = ""
    relevance_score: Optional[float] = None


@dataclass
class AgentOutput:
    """
    Structured output from an agent.

    Agents return this, and the Router decides what to do with it:
    - Pass to next agent
    - Store artifacts
    - Return to user
    """
    # The main content (structured dict for Researcher, prose for Writer)
    content: Any

    # Agent identification
    agent_name: str

    # Whether this output is ready for user display
    is_final: bool = False

    # Storable objects (research notes, outlines, drafts)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)

    # Source references
    citations: List[Citation] = field(default_factory=list)

    # Processing metadata
    tokens_used: int = 0
    processing_ms: int = 0

    # Error state
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "agent_name": self.agent_name,
            "content": self.content,
            "is_final": self.is_final,
            "artifacts": self.artifacts,
            "citations": [
                {
                    "file_id": c.file_id,
                    "filename": c.filename,
                    "chunk_index": c.chunk_index,
                    "page": c.page,
                    "snippet": c.snippet[:200] if c.snippet else "",
                    "relevance_score": c.relevance_score,
                }
                for c in self.citations
            ],
            "tokens_used": self.tokens_used,
            "processing_ms": self.processing_ms,
            "error": self.error,
        }


class BaseAgent(ABC):
    """
    Abstract base class for all agents.

    Agents are stateless processors. They receive context, do their job,
    and return structured output. They never:
    - Call other agents directly
    - Store state between turns
    - Make decisions about routing
    """

    name: str = "base"
    description: str = "Base agent"

    @abstractmethod
    def can_handle(self, ctx: RequestContext, intent: str) -> bool:
        """
        Check if this agent can handle the given intent.

        Args:
            ctx: The request context
            intent: Classified intent string (e.g., "research", "write", "code")

        Returns:
            True if this agent should process this request
        """
        pass

    @abstractmethod
    def run(self, ctx: RequestContext, input_payload: Optional[Dict] = None) -> AgentOutput:
        """
        Execute the agent's task.

        Args:
            ctx: The request context (includes retrieved chunks, memories, etc.)
            input_payload: Optional input from a previous agent in the pipeline

        Returns:
            AgentOutput with content, artifacts, and citations
        """
        pass

    def _build_system_prompt(self, ctx: RequestContext) -> str:
        """
        Build the system prompt for this agent.
        Override in subclasses for agent-specific prompts.
        """
        return f"You are the {self.name} agent. {self.description}"

    def _format_retrieved_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Format retrieved chunks for inclusion in prompt."""
        if not chunks:
            return ""

        lines = ["## Retrieved Sources\n"]
        for i, chunk in enumerate(chunks, 1):
            filename = chunk.get("filename", "unknown")
            content = chunk.get("content", "")[:500]
            page = chunk.get("page")

            header = f"[{i}] {filename}"
            if page:
                header += f" (page {page})"

            lines.append(f"{header}\n{content}\n")

        return "\n".join(lines)

    def _format_prior_outputs(self, outputs: List[AgentOutput]) -> str:
        """Format outputs from previous agents in the pipeline."""
        if not outputs:
            return ""

        lines = ["## Previous Agent Outputs\n"]
        for output in outputs:
            lines.append(f"### From {output.agent_name}:\n")
            if isinstance(output.content, dict):
                # Structured output - format key sections
                for key, value in output.content.items():
                    if isinstance(value, list):
                        lines.append(f"**{key}:**")
                        for item in value[:10]:  # Limit items
                            lines.append(f"- {item}")
                    else:
                        lines.append(f"**{key}:** {value}")
            else:
                lines.append(str(output.content))
            lines.append("")

        return "\n".join(lines)
