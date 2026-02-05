# api/services/agents/__init__.py
"""
Multi-Agent System (Phase 6.2)

Agents are specialized processors that handle specific types of tasks.
All agents are orchestrated by the Router - they never call each other directly.

The CodeAgent (Phase N) is a standalone CLI tool for interactive coding.
"""

from .base import BaseAgent, AgentOutput, RequestContext, Citation
from .researcher import ResearcherAgent
from .writer import WriterAgent
from .engineer import EngineerAgent
from .archivist import ArchivistAgent
from .planner import PlannerAgent
from .code_agent import CodeAgent, AgentConfig, run_code_agent
from .code_tools import PathSandbox, TOOL_DEFINITIONS, build_tool_dispatch

__all__ = [
    # Base classes
    "BaseAgent",
    "AgentOutput",
    "RequestContext",
    "Citation",
    # Router-managed agents
    "ResearcherAgent",
    "WriterAgent",
    "EngineerAgent",
    "ArchivistAgent",
    "PlannerAgent",
    # Standalone code agent
    "CodeAgent",
    "AgentConfig",
    "run_code_agent",
    "PathSandbox",
    "TOOL_DEFINITIONS",
    "build_tool_dispatch",
]
