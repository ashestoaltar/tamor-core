# api/services/agents/archivist.py
"""
Archivist Agent (Phase 6.2)

Purpose: Memory governance and lifecycle management
- Decides what to remember from conversations
- Manages memory categories and relevance
- Handles memory consolidation and cleanup
- Respects user privacy and consent settings

Constraints:
- Must respect user's governance settings
- Cannot store without consent where required
- Should consolidate duplicate/similar memories
"""

import logging
import time
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentOutput, RequestContext
from services import memory_service

logger = logging.getLogger(__name__)


ARCHIVIST_SYSTEM_PROMPT = """You are an Archivist Agent. Your role is to identify valuable information from conversations worth remembering.

## Your Responsibilities
1. Identify facts, preferences, and context worth storing as memories
2. Categorize memories appropriately
3. Determine importance/relevance scores
4. Avoid storing sensitive or inappropriate information
5. Consolidate similar or duplicate information

## Memory Categories
- identity: User's name, role, background
- preference: Likes, dislikes, working style preferences
- project: Project-specific context, goals, constraints
- skill: User's skills, expertise areas
- relationship: People, teams, organizations the user works with
- general: Other useful context

## What to Remember
- User preferences ("I prefer TypeScript over JavaScript")
- Identity facts ("I work at Acme Corp")
- Project context ("This project uses React 18")
- Working style ("I like detailed explanations")
- Technical choices ("We use PostgreSQL for the database")

## What NOT to Remember
- Temporary information (one-time requests)
- Sensitive data (passwords, API keys, personal IDs)
- Trivial conversation details
- Information the user explicitly says to forget

## Output Format
Respond with a JSON object:
{
    "memories_to_store": [
        {
            "content": "The fact or preference to remember",
            "category": "preference|identity|project|skill|relationship|general",
            "importance": 0.0-1.0,
            "reason": "Why this is worth remembering"
        }
    ],
    "memories_to_update": [
        {
            "existing_id": 123,
            "new_content": "Updated content",
            "reason": "Why updating"
        }
    ],
    "memories_to_forget": [
        {
            "existing_id": 456,
            "reason": "Why this should be removed"
        }
    ],
    "analysis": "Brief explanation of memory decisions"
}

If nothing is worth remembering, return empty arrays with an explanation."""


class ArchivistAgent(BaseAgent):
    """
    Archivist agent for memory governance.

    The Archivist examines conversations and decides what information
    should be stored, updated, or removed from long-term memory.
    """

    name = "archivist"
    description = "Manages long-term memory: what to remember, update, or forget."

    def can_handle(self, ctx: RequestContext, intent: str) -> bool:
        """Handle memory-related intents."""
        memory_intents = {
            "remember",
            "forget",
            "memory",
            "store",
            "recall",
            "preference",
        }
        return intent.lower() in memory_intents

    def run(self, ctx: RequestContext, input_payload: Optional[Dict] = None) -> AgentOutput:
        """
        Analyze conversation for memory-worthy information.

        Args:
            ctx: Request context with conversation history
            input_payload: Optional directives (e.g., explicit remember/forget)

        Returns:
            AgentOutput with memory operations to perform
        """
        start_time = time.time()

        # Check if user has memory enabled
        if ctx.user_id:
            settings = memory_service.get_settings(ctx.user_id)
            if not settings.get("auto_save_enabled", True):
                return AgentOutput(
                    agent_name=self.name,
                    content={"analysis": "Auto-save disabled by user settings."},
                    is_final=False,
                    processing_ms=int((time.time() - start_time) * 1000),
                )

        # Check for explicit memory commands
        explicit_action = self._detect_explicit_action(ctx.user_message)

        if explicit_action:
            return self._handle_explicit_action(ctx, explicit_action, start_time)

        # Analyze conversation for implicit memories
        return self._analyze_for_memories(ctx, start_time)

    def _detect_explicit_action(self, message: str) -> Optional[Dict[str, Any]]:
        """Detect explicit memory commands in the message."""
        msg = message.lower()

        # Remember commands
        if any(phrase in msg for phrase in ["remember that", "remember this", "please remember", "don't forget"]):
            return {"action": "remember", "content": message}

        # Forget commands
        if any(phrase in msg for phrase in ["forget that", "forget this", "please forget", "don't remember"]):
            return {"action": "forget", "content": message}

        # Preference statements
        if any(phrase in msg for phrase in ["i prefer", "i like", "i always", "i never", "my preference"]):
            return {"action": "preference", "content": message}

        return None

    def _handle_explicit_action(
        self, ctx: RequestContext, action: Dict[str, Any], start_time: float
    ) -> AgentOutput:
        """Handle explicit memory commands."""
        action_type = action["action"]
        content = action["content"]

        if action_type == "remember":
            # Extract what to remember
            memory_content = self._extract_memory_content(content)
            category = self._detect_category(memory_content)

            if ctx.user_id and memory_content:
                try:
                    memory_id = memory_service.add_memory(
                        content=memory_content,
                        category=category,
                        user_id=ctx.user_id,
                        source="manual",
                    )
                    return AgentOutput(
                        agent_name=self.name,
                        content={
                            "action": "stored",
                            "memory_id": memory_id,
                            "content": memory_content,
                            "category": category,
                        },
                        is_final=False,
                        processing_ms=int((time.time() - start_time) * 1000),
                    )
                except Exception as e:
                    logger.error(f"Failed to store memory: {e}")

        elif action_type == "forget":
            # Find and remove matching memories
            if ctx.user_id:
                # Search for similar memories to forget
                matches = memory_service.search_memories(
                    query=content,
                    user_id=ctx.user_id,
                    limit=3,
                )
                if matches:
                    forgotten = []
                    for mem in matches:
                        if mem.get("score", 0) > 0.7:  # High similarity
                            memory_service.delete_memory(mem["id"], ctx.user_id)
                            forgotten.append(mem["id"])

                    return AgentOutput(
                        agent_name=self.name,
                        content={
                            "action": "forgotten",
                            "memory_ids": forgotten,
                            "count": len(forgotten),
                        },
                        is_final=False,
                        processing_ms=int((time.time() - start_time) * 1000),
                    )

        elif action_type == "preference":
            memory_content = content
            if ctx.user_id:
                try:
                    memory_id = memory_service.add_memory(
                        content=memory_content,
                        category="preference",
                        user_id=ctx.user_id,
                        source="auto",
                    )
                    return AgentOutput(
                        agent_name=self.name,
                        content={
                            "action": "preference_stored",
                            "memory_id": memory_id,
                            "content": memory_content,
                        },
                        is_final=False,
                        processing_ms=int((time.time() - start_time) * 1000),
                    )
                except Exception as e:
                    logger.error(f"Failed to store preference: {e}")

        return AgentOutput(
            agent_name=self.name,
            content={"action": "no_action", "reason": "Could not process memory command"},
            is_final=False,
            processing_ms=int((time.time() - start_time) * 1000),
        )

    def _analyze_for_memories(
        self, ctx: RequestContext, start_time: float
    ) -> AgentOutput:
        """Analyze conversation for implicit memory-worthy information."""
        # For now, use heuristic detection
        # Future: Could use LLM for more sophisticated analysis

        memories_to_store = []
        message = ctx.user_message

        # Check for identity statements
        identity_patterns = [
            ("my name is", "identity"),
            ("i am a", "identity"),
            ("i work at", "identity"),
            ("i'm a", "identity"),
            ("my role is", "identity"),
        ]

        for pattern, category in identity_patterns:
            if pattern in message.lower():
                memories_to_store.append({
                    "content": message,
                    "category": category,
                    "importance": 0.8,
                    "reason": f"Contains identity information ({pattern})",
                })
                break

        # Check for preference statements
        preference_patterns = [
            "i prefer",
            "i like",
            "i always",
            "i never",
            "i usually",
            "my favorite",
        ]

        if any(p in message.lower() for p in preference_patterns):
            memories_to_store.append({
                "content": message,
                "category": "preference",
                "importance": 0.7,
                "reason": "Contains preference information",
            })

        # Check for project context
        project_patterns = [
            "this project",
            "we use",
            "our stack",
            "the codebase",
            "our team",
        ]

        if any(p in message.lower() for p in project_patterns):
            memories_to_store.append({
                "content": message,
                "category": "project",
                "importance": 0.6,
                "reason": "Contains project context",
            })

        # Store detected memories if user_id available
        stored_ids = []
        if ctx.user_id and memories_to_store:
            settings = memory_service.get_settings(ctx.user_id)
            allowed_categories = settings.get("auto_save_categories", [])

            for mem in memories_to_store:
                if mem["category"] in allowed_categories:
                    try:
                        memory_id = memory_service.add_memory(
                            content=mem["content"],
                            category=mem["category"],
                            user_id=ctx.user_id,
                            source="auto",
                        )
                        stored_ids.append(memory_id)
                    except Exception as e:
                        logger.error(f"Failed to auto-store memory: {e}")

        processing_ms = int((time.time() - start_time) * 1000)

        return AgentOutput(
            agent_name=self.name,
            content={
                "memories_detected": len(memories_to_store),
                "memories_stored": len(stored_ids),
                "stored_ids": stored_ids,
                "analysis": f"Found {len(memories_to_store)} potential memories, stored {len(stored_ids)}",
            },
            is_final=False,  # Archivist never produces user-facing output
            processing_ms=processing_ms,
        )

    def _extract_memory_content(self, message: str) -> str:
        """Extract the content to remember from a remember command."""
        # Remove common prefixes
        prefixes = [
            "remember that",
            "remember this:",
            "please remember",
            "don't forget that",
            "don't forget:",
        ]

        content = message
        for prefix in prefixes:
            if content.lower().startswith(prefix):
                content = content[len(prefix):].strip()
                break

        return content

    def _detect_category(self, content: str) -> str:
        """Detect the appropriate category for a memory."""
        content_lower = content.lower()

        if any(w in content_lower for w in ["name", "i am", "i'm a", "work at", "my role"]):
            return "identity"
        elif any(w in content_lower for w in ["prefer", "like", "always", "never", "favorite"]):
            return "preference"
        elif any(w in content_lower for w in ["project", "codebase", "stack", "use", "team"]):
            return "project"
        elif any(w in content_lower for w in ["know how", "expert", "skill", "experience"]):
            return "skill"
        else:
            return "general"
