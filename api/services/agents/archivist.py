# api/services/agents/archivist.py
"""
Archivist Agent (Phase 9.1 — Tiered Memory)

Purpose: LLM-driven memory governance and lifecycle management.
Replaces regex-based auto-classification with intelligent analysis.

The archivist:
- Decides what to remember from conversations (using LLM judgment)
- Assigns memory tiers (core/long_term/episodic)
- Extracts entity relationships
- Consolidates similar/duplicate memories
- Handles explicit remember/forget commands
- Respects user governance settings
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentOutput, RequestContext
from services import memory_service as mem_svc

logger = logging.getLogger(__name__)


ARCHIVIST_SYSTEM_PROMPT = """You are the Archivist — Tamor's memory manager. You analyze conversations to decide what is worth remembering about the user.

Tamor is a personal AI companion for a small household (Chuck and his wife Stephanie), not a mass-market product. Your job is to know them as *people* — not just as users performing tasks. The goal is for Tamor to feel like a trusted companion who genuinely understands them, not a well-informed stranger.

## Memory Tiers

You assign memories to tiers:

- **core**: Who they are as people. Identity, deeply-held values, beliefs, personality traits, humor style, relationship dynamics. Max ~15. Changes rarely but deepens over time.
- **long_term**: Useful knowledge, preferences, project context, relationships, interests, opinions. Grows over time, subject to natural decay.
- **episodic**: Session-specific context, what was discussed/decided. Fades naturally.

## What to Remember

### The Person (highest priority — this is what makes Tamor *theirs*)
- Identity and self-description ("My name is Chuck", "I'm a mechanical engineer")
- Faith, beliefs, and worldview ("Torah-observant", "values covenant faithfulness")
- Values and convictions ("I value clarity and depth", "honesty over politeness")
- Personality traits and temperament ("self-starter", "low tolerance for inefficiency")
- Humor style ("dry humor", "appreciates sarcasm", "laughs at X")
- Emotional patterns ("gets energized by deep technical problems", "frustrated by bureaucracy")
- Interests outside work (music, hobbies, what they enjoy, what they watch/read)
- Relationships and family dynamics ("wife Stephanie", "how they interact differently with Tamor")
- Communication style ("direct, informal", "doesn't bother correcting typos", "substance over polish")
- What motivates and what drains them

### Knowledge and Decisions
- Preferences ("I prefer concise 3-5 paragraph responses", "I like Hebrew terms explained")
- Project context ("Tamor uses Flask + React", "Library has 5000+ files")
- People and relationships ("studies Tim Hegg's work", "Bill Cloud's ministry")
- Decisions made and *why* ("chose BGE-M3 for multilingual support", "picked xAI for cost")
- What was tried and didn't work — dead ends ("tried Marker PDF but too slow for routine use")
- Recurring friction points and patterns ("CAD export format issues come up repeatedly")
- Skills and confidence levels ("expert in VBA/AutoCAD", "learning React")

### Context
- Working patterns ("usually works late evenings", "prefers screen sessions for long tasks")
- Current project status and priorities
- Goals — both short-term and long-term

## What NOT to Remember

- Trivial conversation filler ("ok", "thanks", "got it")
- Temporary instructions ("run this command", "check that file")
- Information already in core memories (don't duplicate)
- Raw LLM responses or code blocks (too verbose for memory)
- Sensitive data (passwords, API keys, tokens)

## Memory Quality

Memories should be **concise facts**, not full conversation transcripts. Distill the essence:
- BAD: storing a 2000-word Tamor response about Torah study
- GOOD: "Chuck is developing a Foundations Series on Torah, covenant, and church drift"
- BAD: storing an entire lesson outline
- GOOD: "Chuck wants Hebrew key terms anchored in original language context in his teachings"

## Entity Extraction

For each memory, identify related entities:
- People: family members, scholars, teachers, collaborators
- Projects: Tamor, Foundations Series, Ashes to Altar, Light Upon Ruin
- Tools: Flask, React, SQLite, Ollama, Piper, AutoCAD
- Concepts: Torah observance, epistemic honesty, covenant faithfulness
- Organizations: TorahResource, Lion & Lamb, 119 Ministries, Anchor Industries

## Consolidation

When you detect memories that overlap or repeat the same fact:
- Recommend merging them into a single, clearer memory
- Increase confidence on the consolidated version
- Mark originals for deletion

## Output Format

Respond with ONLY a JSON object (no markdown, no explanation):
{
    "memories_to_store": [
        {
            "content": "Clear, concise fact to remember",
            "category": "identity|personality|values|preference|relationship|project|theology|engineering|music|interest|general",
            "tier": "core|long_term|episodic",
            "confidence": 0.0-1.0,
            "entities": [{"name": "entity name", "type": "person|project|tool|concept|organization", "relationship": "about|uses|teaches|created_by|studies_with"}],
            "reason": "Brief reason for remembering"
        }
    ],
    "memories_to_update": [
        {
            "id": 123,
            "new_content": "Updated content",
            "new_confidence": 0.0-1.0,
            "reason": "Why updating"
        }
    ],
    "memories_to_forget": [
        {
            "id": 456,
            "reason": "Why this should be removed"
        }
    ],
    "consolidations": [
        {
            "source_ids": [1, 2, 3],
            "merged_content": "Single clear memory combining all sources",
            "tier": "long_term",
            "confidence": 0.8,
            "reason": "These all say the same thing"
        }
    ],
    "analysis": "Brief explanation of memory decisions"
}

If nothing is worth remembering, return empty arrays with an analysis explaining why."""


class ArchivistAgent(BaseAgent):
    """
    LLM-powered Archivist agent for tiered memory governance.

    Uses the LLM to analyze conversations and make intelligent decisions
    about what to remember, update, consolidate, or forget.
    """

    name = "archivist"
    description = "Manages long-term memory: what to remember, update, or forget."

    def can_handle(self, ctx: RequestContext, intent: str) -> bool:
        """Handle memory-related intents."""
        memory_intents = {"remember", "forget", "memory", "store", "recall", "preference"}
        return intent.lower() in memory_intents

    def run(self, ctx: RequestContext, input_payload: Optional[Dict] = None) -> AgentOutput:
        """
        Analyze conversation for memory-worthy information.

        For explicit commands (remember/forget), handles immediately.
        For general analysis, uses LLM to evaluate what's worth remembering.
        """
        start_time = time.time()

        # Check if user has memory enabled
        if ctx.user_id:
            settings = mem_svc.get_settings(ctx.user_id)
            if not settings.get("auto_save_enabled", True):
                return AgentOutput(
                    agent_name=self.name,
                    content={"analysis": "Auto-save disabled by user settings."},
                    is_final=False,
                    processing_ms=int((time.time() - start_time) * 1000),
                )

        # Check for explicit memory commands (fast path, no LLM needed)
        explicit_action = self._detect_explicit_action(ctx.user_message)
        if explicit_action:
            return self._handle_explicit_action(ctx, explicit_action, start_time)

        # Use LLM to analyze conversation for memories
        return self._llm_analyze(ctx, start_time)

    def _detect_explicit_action(self, message: str) -> Optional[Dict[str, Any]]:
        """Detect explicit memory commands in the message."""
        msg = message.lower()

        if any(phrase in msg for phrase in ["remember that", "remember this", "please remember", "don't forget"]):
            return {"action": "remember", "content": message}

        if any(phrase in msg for phrase in ["forget that", "forget this", "please forget", "don't remember"]):
            return {"action": "forget", "content": message}

        return None

    def _handle_explicit_action(
        self, ctx: RequestContext, action: Dict[str, Any], start_time: float
    ) -> AgentOutput:
        """Handle explicit remember/forget commands."""
        action_type = action["action"]
        content = action["content"]

        if action_type == "remember":
            memory_content = self._extract_memory_content(content)

            if ctx.user_id and memory_content:
                try:
                    # Use LLM to classify the explicit memory if possible, otherwise default
                    tier = "long_term"
                    category = "general"
                    confidence = 0.8  # Explicit memories get high confidence

                    # Simple heuristic for tier/category on explicit memories
                    lower = memory_content.lower()
                    if any(w in lower for w in ["my name", "i am", "i'm a", "my role"]):
                        category = "identity"
                        tier = "core"
                        confidence = 0.95
                    elif any(w in lower for w in ["i value", "i believe", "my faith", "i'm convicted"]):
                        category = "values"
                        tier = "core"
                        confidence = 0.9
                    elif any(w in lower for w in ["my wife", "my husband", "my family"]):
                        category = "relationship"
                        tier = "core"
                        confidence = 0.9
                    elif any(w in lower for w in ["my humor", "i find funny", "makes me laugh", "my personality"]):
                        category = "personality"
                        tier = "core"
                        confidence = 0.85
                    elif any(w in lower for w in ["prefer", "like", "always", "never"]):
                        category = "preference"
                        confidence = 0.85

                    memory_id = mem_svc.add_memory(
                        content=memory_content,
                        category=category,
                        user_id=ctx.user_id,
                        source="manual",
                        memory_tier=tier,
                        confidence=confidence,
                    )
                    return AgentOutput(
                        agent_name=self.name,
                        content={
                            "action": "stored",
                            "memory_id": memory_id,
                            "content": memory_content,
                            "category": category,
                            "tier": tier,
                        },
                        is_final=False,
                        processing_ms=int((time.time() - start_time) * 1000),
                    )
                except Exception as e:
                    logger.error(f"Failed to store memory: {e}")

        elif action_type == "forget":
            if ctx.user_id:
                matches = mem_svc.search_memories(query=content, user_id=ctx.user_id, limit=3)
                forgotten = []
                for mem in matches:
                    if mem.get("score", 0) > 0.5:
                        mem_svc.delete_memory(mem["id"], ctx.user_id)
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

        return AgentOutput(
            agent_name=self.name,
            content={"action": "no_action", "reason": "Could not process memory command"},
            is_final=False,
            processing_ms=int((time.time() - start_time) * 1000),
        )

    def _llm_analyze(self, ctx: RequestContext, start_time: float) -> AgentOutput:
        """
        Use LLM to analyze conversation for memory-worthy information.

        This is the core upgrade from Phase 6.1 → Phase 9.1.
        """
        try:
            from services.llm_service import get_agent_llm

            llm_client = get_agent_llm("archivist")
            if not llm_client:
                logger.warning("No LLM available for archivist, falling back to heuristic")
                return self._heuristic_analyze(ctx, start_time)

            # Build context for the LLM
            existing_memories = mem_svc.list_memories(user_id=ctx.user_id, limit=30)
            existing_summary = self._summarize_existing_memories(existing_memories)

            # Build conversation excerpt (last few messages)
            conversation_text = self._build_conversation_excerpt(ctx)

            user_prompt = f"""Analyze this conversation for memories worth storing.

## Existing Memories (avoid duplicates)
{existing_summary}

## Current Conversation
{conversation_text}

## Current User Message
{ctx.user_message}

What should be remembered, updated, or forgotten? Return JSON only."""

            response = llm_client.chat_completion([
                {"role": "system", "content": ARCHIVIST_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ])

            if not response or not response.get("content"):
                return self._heuristic_analyze(ctx, start_time)

            # Parse LLM response
            result = self._parse_llm_response(response["content"])
            if not result:
                return self._heuristic_analyze(ctx, start_time)

            # Execute memory operations
            return self._execute_memory_operations(ctx, result, start_time,
                                                    provider=response.get("provider", ""),
                                                    model=response.get("model", ""))

        except Exception as e:
            logger.error(f"LLM archivist failed: {e}", exc_info=True)
            return self._heuristic_analyze(ctx, start_time)

    def _summarize_existing_memories(self, memories: List[Dict]) -> str:
        """Build a compact summary of existing memories for dedup context."""
        if not memories:
            return "(No existing memories)"

        lines = []
        for m in memories[:30]:
            tier = m.get("memory_tier", "long_term")
            cat = m.get("category", "general")
            content = m["content"][:120]
            lines.append(f"[{tier}/{cat}] id={m['id']}: {content}")

        return "\n".join(lines)

    def _build_conversation_excerpt(self, ctx: RequestContext) -> str:
        """Build a compact conversation excerpt from history."""
        if not ctx.history:
            return "(No prior messages in this conversation)"

        # Take last 6 messages
        recent = ctx.history[-6:]
        lines = []
        for msg in recent:
            role = msg.get("role", "user")
            content = msg.get("content", "")[:300]
            lines.append(f"**{role}**: {content}")

        return "\n\n".join(lines)

    def _parse_llm_response(self, content: str) -> Optional[Dict]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        text = content.strip()

        # Strip markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass

            logger.warning(f"Could not parse archivist LLM response as JSON: {text[:200]}")
            return None

    def _execute_memory_operations(
        self, ctx: RequestContext, result: Dict, start_time: float,
        provider: str = "", model: str = "",
    ) -> AgentOutput:
        """Execute memory operations from LLM analysis."""
        stored_ids = []
        updated_ids = []
        forgotten_ids = []
        consolidated = 0

        # Store new memories
        for mem in result.get("memories_to_store", []):
            try:
                content = mem.get("content", "").strip()
                if not content:
                    continue

                memory_id = mem_svc.add_memory(
                    content=content,
                    category=mem.get("category", "general"),
                    user_id=ctx.user_id,
                    source="auto",
                    memory_tier=mem.get("tier", "long_term"),
                    confidence=mem.get("confidence", 0.5),
                )

                if memory_id:
                    stored_ids.append(memory_id)

                    # Link entities
                    for entity in mem.get("entities", []):
                        entity_id = mem_svc.add_entity(
                            entity.get("name", ""),
                            entity.get("type", "concept"),
                        )
                        if entity_id:
                            mem_svc.link_memory_to_entity(
                                memory_id, entity_id,
                                entity.get("relationship", "about"),
                            )

            except Exception as e:
                logger.error(f"Failed to store archivist memory: {e}")

        # Update existing memories
        for mem in result.get("memories_to_update", []):
            try:
                mid = mem.get("id") or mem.get("existing_id")
                if not mid:
                    continue

                mem_svc.update_memory(
                    memory_id=mid,
                    content=mem.get("new_content"),
                    confidence=mem.get("new_confidence"),
                    user_id=ctx.user_id,
                )
                updated_ids.append(mid)
            except Exception as e:
                logger.error(f"Failed to update memory: {e}")

        # Forget memories
        for mem in result.get("memories_to_forget", []):
            try:
                mid = mem.get("id") or mem.get("existing_id")
                if not mid:
                    continue

                mem_svc.delete_memory(mid, ctx.user_id)
                forgotten_ids.append(mid)
            except Exception as e:
                logger.error(f"Failed to forget memory: {e}")

        # Handle consolidations
        for cons in result.get("consolidations", []):
            try:
                source_ids = cons.get("source_ids", [])
                merged = cons.get("merged_content", "")
                if not source_ids or not merged:
                    continue

                # Create merged memory
                new_id = mem_svc.add_memory(
                    content=merged,
                    category="general",
                    user_id=ctx.user_id,
                    source="auto",
                    memory_tier=cons.get("tier", "long_term"),
                    confidence=cons.get("confidence", 0.8),
                )

                if new_id:
                    # Delete source memories
                    for sid in source_ids:
                        mem_svc.delete_memory(sid, ctx.user_id)
                    consolidated += 1
                    stored_ids.append(new_id)

            except Exception as e:
                logger.error(f"Failed to consolidate memories: {e}")

        processing_ms = int((time.time() - start_time) * 1000)

        return AgentOutput(
            agent_name=self.name,
            content={
                "memories_stored": len(stored_ids),
                "stored_ids": stored_ids,
                "memories_updated": len(updated_ids),
                "updated_ids": updated_ids,
                "memories_forgotten": len(forgotten_ids),
                "forgotten_ids": forgotten_ids,
                "consolidations": consolidated,
                "analysis": result.get("analysis", ""),
            },
            is_final=False,
            processing_ms=processing_ms,
            provider_used=provider,
            model_used=model,
        )

    def _heuristic_analyze(self, ctx: RequestContext, start_time: float) -> AgentOutput:
        """
        Fallback heuristic analysis when LLM is unavailable.
        Simplified from the old regex classifier — kept as safety net only.
        """
        memories_to_store = []
        message = ctx.user_message
        lower = message.lower()

        # Only detect the most obvious patterns
        if any(p in lower for p in ["my name is", "i am a ", "i work at", "i'm the creator"]):
            memories_to_store.append({
                "content": message,
                "category": "identity",
                "tier": "core",
                "confidence": 0.8,
            })
        elif any(p in lower for p in ["i prefer", "i like", "i always", "i never"]):
            memories_to_store.append({
                "content": message,
                "category": "preference",
                "tier": "long_term",
                "confidence": 0.7,
            })

        stored_ids = []
        if ctx.user_id and memories_to_store:
            for mem in memories_to_store:
                try:
                    memory_id = mem_svc.add_memory(
                        content=mem["content"],
                        category=mem["category"],
                        user_id=ctx.user_id,
                        source="auto",
                        memory_tier=mem["tier"],
                        confidence=mem["confidence"],
                    )
                    if memory_id:
                        stored_ids.append(memory_id)
                except Exception as e:
                    logger.error(f"Failed to auto-store memory: {e}")

        return AgentOutput(
            agent_name=self.name,
            content={
                "memories_stored": len(stored_ids),
                "stored_ids": stored_ids,
                "analysis": f"Heuristic fallback: found {len(memories_to_store)} potential memories",
            },
            is_final=False,
            processing_ms=int((time.time() - start_time) * 1000),
        )

    def _extract_memory_content(self, message: str) -> str:
        """Extract content from a remember command."""
        prefixes = [
            "remember that", "remember this:", "please remember",
            "don't forget that", "don't forget:",
        ]

        content = message
        for prefix in prefixes:
            if content.lower().startswith(prefix):
                content = content[len(prefix):].strip()
                break

        return content
