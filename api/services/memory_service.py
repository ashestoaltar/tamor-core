"""
Memory Service - Tiered Memory System (Phase 9.1)

Redesigned from flat pinned/unpinned to tiered architecture:
- Core: always loaded (identity, values, fundamental preferences) ~5-10 items
- Long-term: searchable, subject to decay (knowledge, preferences, project facts)
- Episodic: session summaries, fade over time
- Working: ephemeral, current session only (not persisted)

Key changes from Phase 6.1:
- Tier-based retrieval replaces pinned-first logic
- last_accessed tracking for memory aging
- Confidence scoring for retrieval ranking
- Entity relationships for connected retrieval
"""

import json
import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from core.config import MEMORY_DB
from core.memory_core import embed, search_memories as core_search_memories
from utils.db import get_db

logger = logging.getLogger(__name__)

# Valid memory tiers
VALID_TIERS = ("core", "long_term", "episodic")

# Default categories for auto-save (kept for backwards compatibility)
DEFAULT_AUTO_CATEGORIES = ["identity", "preference", "project", "theology", "engineering"]

# Context injection limits
MAX_CORE_MEMORIES = 10       # Max core memories to inject (all of them, typically 5-10)
MAX_CONTEXT_MEMORIES = 15    # Total max including core + long_term + episodic
MAX_LONG_TERM_MEMORIES = 8   # Max long-term memories per request
MAX_EPISODIC_MEMORIES = 3    # Max episodic memories per request

# Relevance thresholds (applied to decayed scores)
RELEVANCE_THRESHOLD_LONG_TERM = 0.20   # Low threshold — decay and confidence do the ranking
RELEVANCE_THRESHOLD_EPISODIC = 0.15

# Decay parameters
EPISODIC_HALF_LIFE_DAYS = 14   # Episodic memories lose half their relevance boost every 14 days
LONG_TERM_HALF_LIFE_DAYS = 180 # Long-term memories decay very slowly (6 months half-life)


def _get_memory_db():
    """Get connection to the memory database."""
    import sqlite3
    conn = sqlite3.connect(MEMORY_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _memory_row_to_dict(row) -> Dict[str, Any]:
    """Convert a database row to a memory dict."""
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "category": row["category"],
        "content": row["content"],
        "source": row["source"] or "auto",
        "memory_tier": row["memory_tier"] or "long_term",
        "confidence": row["confidence"] or 0.5,
        "access_count": row["access_count"] or 0,
        "last_accessed": row["last_accessed"],
        "summary": row["summary"],
        "created_at": row["timestamp"],
        "updated_at": row["updated_at"],
        # Backwards compatibility
        "is_pinned": row["memory_tier"] == "core",
    }


# -----------------------------------------------------------------------------
# Memory CRUD Operations
# -----------------------------------------------------------------------------

def add_memory(
    content: str,
    category: str = "general",
    user_id: Optional[int] = None,
    source: str = "manual",
    memory_tier: str = "long_term",
    confidence: float = 0.5,
    is_pinned: bool = False,
    conversation_id: Optional[int] = None,
    message_id: Optional[int] = None,
) -> Optional[int]:
    """
    Add a new memory.

    Args:
        content: The memory content
        category: Category for classification
        user_id: Owner user ID
        source: 'manual' or 'auto'
        memory_tier: 'core', 'long_term', or 'episodic'
        confidence: 0.0-1.0 confidence score
        is_pinned: Legacy — if True, sets tier to 'core'
        conversation_id: Associated conversation
        message_id: Associated message

    Returns:
        Memory ID if created, None if failed
    """
    if not content or not content.strip():
        return None

    # Legacy support: is_pinned=True → core tier
    if is_pinned:
        memory_tier = "core"

    # Validate tier
    if memory_tier not in VALID_TIERS:
        memory_tier = "long_term"

    # Enforce core tier limit
    if memory_tier == "core":
        core_count = _count_tier_memories(user_id, "core")
        if core_count >= MAX_CORE_MEMORIES:
            logger.warning(f"Core tier full ({core_count}), storing as long_term instead")
            memory_tier = "long_term"

    emb = embed(content)
    now = datetime.utcnow().isoformat()

    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO memories
            (user_id, conversation_id, message_id, category, content, embedding,
             source, is_pinned, memory_tier, confidence, last_accessed, access_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (user_id, conversation_id, message_id, category, content, emb,
             source, 1 if memory_tier == "core" else 0,
             memory_tier, confidence, now, now),
        )
        memory_id = cursor.lastrowid
        conn.commit()
        logger.info(f"Stored memory {memory_id} [{memory_tier}/{category}] confidence={confidence:.2f}")
        return memory_id
    except Exception as e:
        logger.error(f"Failed to add memory: {e}")
        return None
    finally:
        conn.close()


def update_memory(
    memory_id: int,
    content: Optional[str] = None,
    category: Optional[str] = None,
    memory_tier: Optional[str] = None,
    confidence: Optional[float] = None,
    summary: Optional[str] = None,
    is_pinned: Optional[bool] = None,
    user_id: Optional[int] = None,
) -> bool:
    """
    Update an existing memory.

    Args:
        memory_id: ID of memory to update
        content: New content (re-embeds if changed)
        category: New category
        memory_tier: New tier ('core', 'long_term', 'episodic')
        confidence: New confidence score
        summary: Compressed summary (for consolidation)
        is_pinned: Legacy — maps to tier change
        user_id: User ID for ownership check

    Returns:
        True if updated, False otherwise
    """
    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        # Verify ownership if user_id provided
        if user_id is not None:
            cursor.execute(
                "SELECT id FROM memories WHERE id = ? AND (user_id = ? OR user_id IS NULL)",
                (memory_id, user_id)
            )
            if not cursor.fetchone():
                return False

        updates = []
        params = []

        if content is not None:
            updates.append("content = ?")
            params.append(content)
            # Re-embed on content change
            emb = embed(content)
            updates.append("embedding = ?")
            params.append(emb)

        if category is not None:
            updates.append("category = ?")
            params.append(category)

        if memory_tier is not None and memory_tier in VALID_TIERS:
            updates.append("memory_tier = ?")
            params.append(memory_tier)
            # Keep is_pinned in sync for backwards compatibility
            updates.append("is_pinned = ?")
            params.append(1 if memory_tier == "core" else 0)

        if confidence is not None:
            updates.append("confidence = ?")
            params.append(max(0.0, min(1.0, confidence)))

        if summary is not None:
            updates.append("summary = ?")
            params.append(summary)

        # Legacy is_pinned support
        if is_pinned is not None and memory_tier is None:
            new_tier = "core" if is_pinned else "long_term"
            updates.append("memory_tier = ?")
            params.append(new_tier)
            updates.append("is_pinned = ?")
            params.append(1 if is_pinned else 0)

        if not updates:
            return True  # Nothing to update

        updates.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        params.append(memory_id)

        cursor.execute(
            f"UPDATE memories SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update memory {memory_id}: {e}")
        return False
    finally:
        conn.close()


def delete_memory(memory_id: int, user_id: Optional[int] = None) -> bool:
    """Delete a memory and its entity links."""
    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        # Delete entity links first
        cursor.execute("DELETE FROM memory_entity_links WHERE memory_id = ?", (memory_id,))

        if user_id is not None:
            cursor.execute(
                "DELETE FROM memories WHERE id = ? AND (user_id = ? OR user_id IS NULL)",
                (memory_id, user_id)
            )
        else:
            cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))

        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to delete memory {memory_id}: {e}")
        return False
    finally:
        conn.close()


def get_memory(memory_id: int) -> Optional[Dict[str, Any]]:
    """Get a single memory by ID."""
    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT id, user_id, category, content, source, is_pinned,
                   memory_tier, confidence, access_count, last_accessed,
                   summary, timestamp, updated_at, consent_at
            FROM memories WHERE id = ?
            """,
            (memory_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        return _memory_row_to_dict(row)
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# Tier Operations (replaces Pin/Unpin)
# -----------------------------------------------------------------------------

def promote_to_core(memory_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Promote a memory to core tier."""
    core_count = _count_tier_memories(user_id, "core")
    if core_count >= MAX_CORE_MEMORIES:
        return {
            "success": False,
            "error": f"Core tier full ({core_count}/{MAX_CORE_MEMORIES}). Demote another memory first."
        }

    success = update_memory(memory_id, memory_tier="core", confidence=0.9, user_id=user_id)
    return {"success": success}


def demote_from_core(memory_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Demote a memory from core to long_term."""
    success = update_memory(memory_id, memory_tier="long_term", user_id=user_id)
    return {"success": success}


def set_memory_tier(memory_id: int, tier: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Set a memory's tier explicitly."""
    if tier not in VALID_TIERS:
        return {"success": False, "error": f"Invalid tier: {tier}. Must be one of {VALID_TIERS}"}

    if tier == "core":
        return promote_to_core(memory_id, user_id)

    success = update_memory(memory_id, memory_tier=tier, user_id=user_id)
    return {"success": success}


# Legacy pin/unpin support (maps to tier operations)
def pin_memory(memory_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Legacy: Pin a memory (promotes to core tier)."""
    return promote_to_core(memory_id, user_id)


def unpin_memory(memory_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Legacy: Unpin a memory (demotes from core tier)."""
    return demote_from_core(memory_id, user_id)


def count_pinned_memories(user_id: Optional[int] = None) -> int:
    """Legacy: Count pinned (core tier) memories."""
    return _count_tier_memories(user_id, "core")


def get_pinned_memories(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Legacy: Get pinned (core tier) memories."""
    return get_tier_memories(user_id, "core")


def _count_tier_memories(user_id: Optional[int], tier: str) -> int:
    """Count memories in a specific tier."""
    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        if user_id is not None:
            cursor.execute(
                "SELECT COUNT(*) FROM memories WHERE memory_tier = ? AND (user_id = ? OR user_id IS NULL)",
                (tier, user_id)
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM memories WHERE memory_tier = ?", (tier,))

        return cursor.fetchone()[0]
    finally:
        conn.close()


def get_tier_memories(user_id: Optional[int], tier: str) -> List[Dict[str, Any]]:
    """Get all memories in a specific tier."""
    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        if user_id is not None:
            cursor.execute(
                """
                SELECT id, user_id, category, content, source, is_pinned,
                       memory_tier, confidence, access_count, last_accessed,
                       summary, timestamp, updated_at
                FROM memories
                WHERE memory_tier = ? AND (user_id = ? OR user_id IS NULL)
                ORDER BY confidence DESC, timestamp DESC
                """,
                (tier, user_id)
            )
        else:
            cursor.execute(
                """
                SELECT id, user_id, category, content, source, is_pinned,
                       memory_tier, confidence, access_count, last_accessed,
                       summary, timestamp, updated_at
                FROM memories
                WHERE memory_tier = ?
                ORDER BY confidence DESC, timestamp DESC
                """,
                (tier,)
            )

        return [_memory_row_to_dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# List and Search
# -----------------------------------------------------------------------------

def list_memories(
    user_id: Optional[int] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    tier: Optional[str] = None,
    pinned_only: bool = False,
    query: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """
    List memories with filters.

    Args:
        user_id: Filter by user
        category: Filter by category
        source: Filter by source ('auto', 'manual')
        tier: Filter by tier ('core', 'long_term', 'episodic')
        pinned_only: Legacy — filter to core tier
        query: Text search filter
        limit: Maximum results
    """
    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        sql = """
            SELECT id, user_id, category, content, source, is_pinned,
                   memory_tier, confidence, access_count, last_accessed,
                   summary, timestamp, updated_at
            FROM memories
        """
        params = []
        filters = []

        if user_id is not None:
            filters.append("(user_id = ? OR user_id IS NULL)")
            params.append(user_id)

        if category and category.lower() != "all":
            filters.append("category = ?")
            params.append(category)

        if source and source.lower() != "all":
            filters.append("source = ?")
            params.append(source)

        if tier and tier in VALID_TIERS:
            filters.append("memory_tier = ?")
            params.append(tier)

        if pinned_only:
            filters.append("memory_tier = 'core'")

        if query:
            filters.append("content LIKE ?")
            params.append(f"%{query}%")

        if filters:
            sql += " WHERE " + " AND ".join(filters)

        sql += " ORDER BY CASE memory_tier WHEN 'core' THEN 0 WHEN 'long_term' THEN 1 WHEN 'episodic' THEN 2 END, confidence DESC, timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)
        return [_memory_row_to_dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def search_memories(
    query: str,
    user_id: Optional[int] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Semantic search for memories.

    Returns memories with relevance scores, weighted by recency and confidence.
    """
    # Use core search function which handles embedding
    results = core_search_memories(query, limit=limit * 3)  # Over-fetch, then rank

    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        output = []
        for score, mid, content in results:
            cursor.execute(
                """
                SELECT id, user_id, category, content, source, is_pinned,
                       memory_tier, confidence, access_count, last_accessed,
                       summary, timestamp, updated_at
                FROM memories WHERE id = ?
                """,
                (mid,)
            )
            row = cursor.fetchone()
            if not row:
                continue

            # Filter by user
            if user_id is not None:
                if row["user_id"] is not None and row["user_id"] != user_id:
                    continue

            mem = _memory_row_to_dict(row)
            # Apply recency decay to score
            mem["raw_score"] = score
            mem["score"] = _apply_decay(score, row["memory_tier"], row["last_accessed"], row["confidence"])
            output.append(mem)

        # Re-sort by decayed score
        output.sort(key=lambda m: m["score"], reverse=True)
        return output[:limit]
    finally:
        conn.close()


def _apply_decay(
    raw_score: float,
    tier: str,
    last_accessed: Optional[str],
    confidence: Optional[float],
) -> float:
    """
    Apply recency decay and confidence weighting to a relevance score.

    Core memories: no decay (always full weight)
    Long-term: slow decay based on LONG_TERM_HALF_LIFE_DAYS
    Episodic: faster decay based on EPISODIC_HALF_LIFE_DAYS
    """
    if tier == "core":
        return raw_score  # Core memories are always fully relevant

    # Calculate age in days
    age_days = 0.0
    if last_accessed:
        try:
            last = datetime.fromisoformat(last_accessed)
            age_days = (datetime.utcnow() - last).total_seconds() / 86400
        except (ValueError, TypeError):
            age_days = 30.0  # Default to 30 days if unparseable

    # Exponential decay
    half_life = EPISODIC_HALF_LIFE_DAYS if tier == "episodic" else LONG_TERM_HALF_LIFE_DAYS
    recency_factor = math.pow(0.5, age_days / half_life)

    # Confidence boost (0.5 default → 1.0x, 0.9 high → 1.4x, 0.3 low → 0.6x)
    confidence_factor = 0.4 + (confidence or 0.5) * 1.2

    return raw_score * recency_factor * confidence_factor


# -----------------------------------------------------------------------------
# Chat Context Integration — THE CORE CHANGE
# -----------------------------------------------------------------------------

def get_memories_for_context(
    user_message: str,
    user_id: Optional[int] = None,
    max_memories: int = MAX_CONTEXT_MEMORIES,
) -> List[Dict[str, Any]]:
    """
    Get memories to inject into chat context using tiered retrieval.

    Strategy:
    1. ALWAYS load all core memories (identity, values — always relevant)
    2. Search for relevant long-term memories (weighted by recency + confidence)
    3. Search for relevant episodic memories (recent session context)
    4. Track access for decay system

    Args:
        user_message: Current user message for semantic matching
        user_id: User ID for filtering
        max_memories: Maximum total memories to return

    Returns:
        List of memory dicts to inject into context
    """
    memories = []
    included_ids = set()

    # --- Tier 1: Core memories (always loaded) ---
    core = get_tier_memories(user_id, "core")
    for mem in core[:MAX_CORE_MEMORIES]:
        mem["_injection_reason"] = "core"
        memories.append(mem)
        included_ids.add(mem["id"])

    remaining = max_memories - len(memories)
    if remaining <= 0 or not user_message:
        _record_access(included_ids)
        return memories

    # --- Tier 2: Long-term memories (relevance + decay weighted) ---
    long_term_results = search_memories(user_message, user_id, limit=MAX_LONG_TERM_MEMORIES + 5)
    lt_added = 0
    for mem in long_term_results:
        if mem["id"] in included_ids:
            continue
        if mem.get("memory_tier") != "long_term":
            continue
        if mem.get("score", 0) < RELEVANCE_THRESHOLD_LONG_TERM:
            continue

        mem["_injection_reason"] = "relevant"
        memories.append(mem)
        included_ids.add(mem["id"])
        lt_added += 1

        if lt_added >= MAX_LONG_TERM_MEMORIES or len(memories) >= max_memories:
            break

    remaining = max_memories - len(memories)
    if remaining <= 0:
        _record_access(included_ids)
        return memories

    # --- Tier 3: Episodic memories (recent session context) ---
    episodic_results = search_memories(user_message, user_id, limit=MAX_EPISODIC_MEMORIES + 3)
    ep_added = 0
    for mem in episodic_results:
        if mem["id"] in included_ids:
            continue
        if mem.get("memory_tier") != "episodic":
            continue
        if mem.get("score", 0) < RELEVANCE_THRESHOLD_EPISODIC:
            continue

        mem["_injection_reason"] = "episodic"
        memories.append(mem)
        included_ids.add(mem["id"])
        ep_added += 1

        if ep_added >= MAX_EPISODIC_MEMORIES or len(memories) >= max_memories:
            break

    # Record access for all retrieved memories
    _record_access(included_ids)

    return memories


def _record_access(memory_ids: set):
    """Update last_accessed and access_count for retrieved memories."""
    if not memory_ids:
        return

    conn = _get_memory_db()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()

    try:
        for mid in memory_ids:
            cursor.execute(
                "UPDATE memories SET last_accessed = ?, access_count = access_count + 1 WHERE id = ?",
                (now, mid)
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to record memory access: {e}")
    finally:
        conn.close()


def format_memories_for_prompt(memories: List[Dict[str, Any]]) -> str:
    """
    Format memories for injection into system prompt.

    Organizes by tier for clarity.
    """
    if not memories:
        return ""

    core_mems = [m for m in memories if m.get("memory_tier") == "core" or m.get("_injection_reason") == "core"]
    other_mems = [m for m in memories if m not in core_mems]

    lines = ["## What You Know About the User\n"]

    if core_mems:
        lines.append("**Always remember:**")
        for mem in core_mems:
            lines.append(f"- {mem['content']}")
        lines.append("")

    if other_mems:
        lines.append("**Relevant context:**")
        for mem in other_mems:
            category = mem.get("category", "general")
            lines.append(f"- [{category}] {mem['content']}")

    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Memory Stats
# -----------------------------------------------------------------------------

def get_memory_stats(user_id: Optional[int] = None) -> Dict[str, Any]:
    """Get memory statistics by tier."""
    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        user_filter = "AND (user_id = ? OR user_id IS NULL)" if user_id else ""
        params = (user_id,) if user_id else ()

        stats = {}
        for tier in VALID_TIERS:
            cursor.execute(
                f"SELECT COUNT(*), ROUND(AVG(confidence), 2), ROUND(AVG(access_count), 1) "
                f"FROM memories WHERE memory_tier = ? {user_filter}",
                (tier, *params)
            )
            row = cursor.fetchone()
            stats[tier] = {
                "count": row[0],
                "avg_confidence": row[1] or 0,
                "avg_access_count": row[2] or 0,
            }

        cursor.execute(f"SELECT COUNT(*) FROM memories WHERE 1=1 {user_filter}", params)
        stats["total"] = cursor.fetchone()[0]

        cursor.execute(f"SELECT COUNT(DISTINCT entity_id) FROM memory_entity_links")
        stats["entities"] = cursor.fetchone()[0]

        return stats
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# Entity Management
# -----------------------------------------------------------------------------

def add_entity(name: str, entity_type: str) -> Optional[int]:
    """Add or get an entity. Returns entity ID."""
    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT OR IGNORE INTO memory_entities (name, entity_type) VALUES (?, ?)",
            (name, entity_type)
        )
        conn.commit()

        cursor.execute(
            "SELECT id FROM memory_entities WHERE name = ? AND entity_type = ?",
            (name, entity_type)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"Failed to add entity: {e}")
        return None
    finally:
        conn.close()


def link_memory_to_entity(
    memory_id: int, entity_id: int, relationship: str = "about"
) -> bool:
    """Link a memory to an entity."""
    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT OR IGNORE INTO memory_entity_links (memory_id, entity_id, relationship) VALUES (?, ?, ?)",
            (memory_id, entity_id, relationship)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to link memory {memory_id} to entity {entity_id}: {e}")
        return False
    finally:
        conn.close()


def get_connected_memories(entity_name: str, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get all memories connected to an entity by name."""
    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        user_filter = "AND (m.user_id = ? OR m.user_id IS NULL)" if user_id else ""
        params = [f"%{entity_name}%"]
        if user_id:
            params.append(user_id)

        cursor.execute(
            f"""
            SELECT DISTINCT m.id, m.user_id, m.category, m.content, m.source, m.is_pinned,
                   m.memory_tier, m.confidence, m.access_count, m.last_accessed,
                   m.summary, m.timestamp, m.updated_at,
                   e.name as entity_name, l.relationship
            FROM memories m
            JOIN memory_entity_links l ON m.id = l.memory_id
            JOIN memory_entities e ON l.entity_id = e.id
            WHERE e.name LIKE ? {user_filter}
            ORDER BY m.memory_tier, m.confidence DESC
            """,
            params
        )

        results = []
        for row in cursor.fetchall():
            mem = _memory_row_to_dict(row)
            mem["entity_name"] = row["entity_name"]
            mem["relationship"] = row["relationship"]
            results.append(mem)

        return results
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# Settings Management (kept for backwards compatibility)
# -----------------------------------------------------------------------------

def get_settings(user_id: Optional[int] = None) -> Dict[str, Any]:
    """Get memory settings for a user."""
    defaults = {
        "auto_save_enabled": True,
        "auto_save_categories": DEFAULT_AUTO_CATEGORIES,
        "max_pinned_memories": MAX_CORE_MEMORIES,
        "max_core_memories": MAX_CORE_MEMORIES,
    }

    if user_id is None:
        return defaults

    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT auto_save_enabled, auto_save_categories, max_pinned_memories FROM memory_settings WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()

        if not row:
            return defaults

        categories = DEFAULT_AUTO_CATEGORIES
        if row["auto_save_categories"]:
            try:
                categories = json.loads(row["auto_save_categories"])
            except json.JSONDecodeError:
                pass

        return {
            "auto_save_enabled": bool(row["auto_save_enabled"]),
            "auto_save_categories": categories,
            "max_pinned_memories": row["max_pinned_memories"] or MAX_CORE_MEMORIES,
            "max_core_memories": row["max_pinned_memories"] or MAX_CORE_MEMORIES,
        }
    finally:
        conn.close()


def update_settings(
    user_id: int,
    auto_save_enabled: Optional[bool] = None,
    auto_save_categories: Optional[List[str]] = None,
    max_pinned_memories: Optional[int] = None,
) -> bool:
    """Update memory settings for a user."""
    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM memory_settings WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone() is not None
        now = datetime.utcnow().isoformat()

        if exists:
            updates = []
            params = []

            if auto_save_enabled is not None:
                updates.append("auto_save_enabled = ?")
                params.append(1 if auto_save_enabled else 0)

            if auto_save_categories is not None:
                updates.append("auto_save_categories = ?")
                params.append(json.dumps(auto_save_categories))

            if max_pinned_memories is not None:
                updates.append("max_pinned_memories = ?")
                params.append(max_pinned_memories)

            if updates:
                updates.append("updated_at = ?")
                params.append(now)
                params.append(user_id)
                cursor.execute(
                    f"UPDATE memory_settings SET {', '.join(updates)} WHERE user_id = ?",
                    params
                )
        else:
            cursor.execute(
                """
                INSERT INTO memory_settings
                (user_id, auto_save_enabled, auto_save_categories, max_pinned_memories, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    1 if (auto_save_enabled is None or auto_save_enabled) else 0,
                    json.dumps(auto_save_categories or DEFAULT_AUTO_CATEGORIES),
                    max_pinned_memories or MAX_CORE_MEMORIES,
                    now, now,
                )
            )

        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to update settings for user {user_id}: {e}")
        return False
    finally:
        conn.close()


def should_auto_save(category: str, user_id: Optional[int] = None) -> bool:
    """Check if a category is allowed for auto-save."""
    settings = get_settings(user_id)
    if not settings.get("auto_save_enabled", True):
        return False
    return category in settings.get("auto_save_categories", DEFAULT_AUTO_CATEGORIES)


# -----------------------------------------------------------------------------
# Categories
# -----------------------------------------------------------------------------

def get_categories() -> List[str]:
    """Get list of all memory categories in use."""
    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT DISTINCT category FROM memories WHERE category IS NOT NULL ORDER BY category"
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# Helper
# -----------------------------------------------------------------------------

def get_memory_service():
    """Get memory service singleton (module itself acts as service)."""
    import services.memory_service as svc
    return svc
