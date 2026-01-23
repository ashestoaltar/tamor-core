# api/services/agents/__init__.py
"""
Multi-Agent System (Phase 6.2)

Agents are specialized processors that handle specific types of tasks.
All agents are orchestrated by the Router - they never call each other directly.
"""

from .base import BaseAgent, AgentOutput, RequestContext, Citation
from .researcher import ResearcherAgent
from .writer import WriterAgent
from .engineer import EngineerAgent
from .archivist import ArchivistAgent

__all__ = [
    "BaseAgent",
    "AgentOutput",
    "RequestContext",
    "Citation",
    "ResearcherAgent",
    "WriterAgent",
    "EngineerAgent",
    "ArchivistAgent",
]
