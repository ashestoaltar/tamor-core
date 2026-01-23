"""
Memory Service - Governed Memory System (Phase 6.1)

Provides memory management with governance controls:
- Add, update, delete memories
- Pin/unpin memories with limits
- Semantic search
- Memory injection into chat context
- User settings for auto-save governance
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from core.config import MEMORY_DB
from core.memory_core import embed, search_memories as core_search_memories
from utils.db import get_db

logger = logging.getLogger(__name__)

# Default categories for auto-save
DEFAULT_AUTO_CATEGORIES = ["identity", "preference", "project", "theology", "engineering"]

# Maximum memories to inject into chat context
MAX_CONTEXT_MEMORIES = 5

# Relevance threshold for including memories in context
RELEVANCE_THRESHOLD = 0.65


def _get_memory_db():
    """Get connection to the memory database."""
    import sqlite3
    conn = sqlite3.connect(MEMORY_DB)
    conn.row_factory = sqlite3.Row
    return conn


# -----------------------------------------------------------------------------
# Memory CRUD Operations
# -----------------------------------------------------------------------------

def add_memory(
    content: str,
    category: str = "general",
    user_id: Optional[int] = None,
    source: str = "manual",
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
        is_pinned: Whether to pin immediately
        conversation_id: Associated conversation
        message_id: Associated message

    Returns:
        Memory ID if created, None if failed
    """
    if not content or not content.strip():
        return None

    # Check pin limit if pinning
    if is_pinned:
        settings = get_settings(user_id)
        max_pinned = settings.get("max_pinned_memories", 10)
        current_pinned = count_pinned_memories(user_id)
        if current_pinned >= max_pinned:
            is_pinned = False  # Don't pin if at limit

    emb = embed(content)
    now = datetime.utcnow().isoformat()

    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO memories
            (user_id, conversation_id, message_id, category, content, embedding,
             source, is_pinned, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, conversation_id, message_id, category, content, emb,
             source, 1 if is_pinned else 0, now),
        )
        memory_id = cursor.lastrowid
        conn.commit()
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
    is_pinned: Optional[bool] = None,
    user_id: Optional[int] = None,
) -> bool:
    """
    Update an existing memory.

    Args:
        memory_id: ID of memory to update
        content: New content (re-embeds if changed)
        category: New category
        is_pinned: New pinned status
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

        if is_pinned is not None:
            # Check pin limit before pinning
            if is_pinned:
                settings = get_settings(user_id)
                max_pinned = settings.get("max_pinned_memories", 10)
                current_pinned = count_pinned_memories(user_id)

                # Check if this memory is already pinned
                cursor.execute("SELECT is_pinned FROM memories WHERE id = ?", (memory_id,))
                row = cursor.fetchone()
                already_pinned = row and row[0] == 1

                if not already_pinned and current_pinned >= max_pinned:
                    # At limit, can't pin more
                    pass
                else:
                    updates.append("is_pinned = ?")
                    params.append(1)
            else:
                updates.append("is_pinned = ?")
                params.append(0)

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
    """
    Delete a memory.

    Args:
        memory_id: ID of memory to delete
        user_id: User ID for ownership check

    Returns:
        True if deleted, False otherwise
    """
    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
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
                   timestamp, updated_at, consent_at
            FROM memories WHERE id = ?
            """,
            (memory_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "category": row["category"],
            "content": row["content"],
            "source": row["source"] or "auto",
            "is_pinned": bool(row["is_pinned"]),
            "created_at": row["timestamp"],
            "updated_at": row["updated_at"],
            "consent_at": row["consent_at"],
        }
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# Pin/Unpin Operations
# -----------------------------------------------------------------------------

def pin_memory(memory_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Pin a memory.

    Returns:
        Dict with 'success' and optional 'error' message
    """
    settings = get_settings(user_id)
    max_pinned = settings.get("max_pinned_memories", 10)
    current_pinned = count_pinned_memories(user_id)

    # Check if already pinned
    memory = get_memory(memory_id)
    if not memory:
        return {"success": False, "error": "Memory not found"}

    if memory.get("is_pinned"):
        return {"success": True}  # Already pinned

    if current_pinned >= max_pinned:
        return {
            "success": False,
            "error": f"Pin limit reached ({max_pinned}). Unpin another memory first."
        }

    success = update_memory(memory_id, is_pinned=True, user_id=user_id)
    return {"success": success}


def unpin_memory(memory_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Unpin a memory."""
    success = update_memory(memory_id, is_pinned=False, user_id=user_id)
    return {"success": success}


def count_pinned_memories(user_id: Optional[int] = None) -> int:
    """Count currently pinned memories for a user."""
    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        if user_id is not None:
            cursor.execute(
                "SELECT COUNT(*) FROM memories WHERE is_pinned = 1 AND (user_id = ? OR user_id IS NULL)",
                (user_id,)
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM memories WHERE is_pinned = 1")

        return cursor.fetchone()[0]
    finally:
        conn.close()


def get_pinned_memories(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get all pinned memories for a user."""
    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        if user_id is not None:
            cursor.execute(
                """
                SELECT id, user_id, category, content, source, is_pinned,
                       timestamp, updated_at
                FROM memories
                WHERE is_pinned = 1 AND (user_id = ? OR user_id IS NULL)
                ORDER BY timestamp DESC
                """,
                (user_id,)
            )
        else:
            cursor.execute(
                """
                SELECT id, user_id, category, content, source, is_pinned,
                       timestamp, updated_at
                FROM memories
                WHERE is_pinned = 1
                ORDER BY timestamp DESC
                """
            )

        rows = cursor.fetchall()
        return [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "category": r["category"],
                "content": r["content"],
                "source": r["source"] or "auto",
                "is_pinned": True,
                "created_at": r["timestamp"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# List and Search
# -----------------------------------------------------------------------------

def list_memories(
    user_id: Optional[int] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    pinned_only: bool = False,
    query: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """
    List memories with filters.

    Args:
        user_id: Filter by user
        category: Filter by category ('all' or None means no filter)
        source: Filter by source ('auto', 'manual', or None for all)
        pinned_only: Only return pinned memories
        query: Text search filter
        limit: Maximum results

    Returns:
        List of memory dicts
    """
    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        sql = """
            SELECT id, user_id, category, content, source, is_pinned,
                   timestamp, updated_at
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

        if pinned_only:
            filters.append("is_pinned = 1")

        if query:
            filters.append("content LIKE ?")
            params.append(f"%{query}%")

        if filters:
            sql += " WHERE " + " AND ".join(filters)

        sql += " ORDER BY is_pinned DESC, timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        return [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "category": r["category"],
                "content": r["content"],
                "source": r["source"] or "auto",
                "is_pinned": bool(r["is_pinned"]),
                "created_at": r["timestamp"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def search_memories(
    query: str,
    user_id: Optional[int] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Semantic search for memories.

    Returns memories with relevance scores.
    """
    # Use core search function which handles embedding
    results = core_search_memories(query, limit=limit * 2)  # Get more, filter by user

    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        output = []
        for score, mid, content in results:
            # Get full memory info
            cursor.execute(
                """
                SELECT id, user_id, category, content, source, is_pinned,
                       timestamp, updated_at
                FROM memories WHERE id = ?
                """,
                (mid,)
            )
            row = cursor.fetchone()
            if not row:
                continue

            # Filter by user if specified
            if user_id is not None:
                if row["user_id"] is not None and row["user_id"] != user_id:
                    continue

            output.append({
                "id": row["id"],
                "user_id": row["user_id"],
                "category": row["category"],
                "content": row["content"],
                "source": row["source"] or "auto",
                "is_pinned": bool(row["is_pinned"]),
                "created_at": row["timestamp"],
                "updated_at": row["updated_at"],
                "score": score,
            })

            if len(output) >= limit:
                break

        return output
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# Chat Context Integration
# -----------------------------------------------------------------------------

def get_memories_for_context(
    user_message: str,
    user_id: Optional[int] = None,
    max_memories: int = MAX_CONTEXT_MEMORIES,
) -> List[Dict[str, Any]]:
    """
    Get memories to inject into chat context.

    Strategy:
    1. Always include pinned memories (up to limit)
    2. Fill remaining with semantically relevant memories

    Args:
        user_message: Current user message for semantic matching
        user_id: User ID for filtering
        max_memories: Maximum memories to return

    Returns:
        List of memory dicts to inject into context
    """
    memories = []

    # 1. Get pinned memories first
    pinned = get_pinned_memories(user_id)
    memories.extend(pinned[:max_memories])

    remaining_slots = max_memories - len(memories)

    if remaining_slots > 0 and user_message:
        # 2. Search for relevant memories
        search_results = search_memories(user_message, user_id, limit=remaining_slots + 5)

        # Get IDs already included
        included_ids = {m["id"] for m in memories}

        for result in search_results:
            if result["id"] in included_ids:
                continue

            # Only include if above relevance threshold
            if result.get("score", 0) >= RELEVANCE_THRESHOLD:
                memories.append(result)
                if len(memories) >= max_memories:
                    break

    return memories


def format_memories_for_prompt(memories: List[Dict[str, Any]]) -> str:
    """
    Format memories for injection into system prompt.

    Args:
        memories: List of memory dicts

    Returns:
        Formatted string for system prompt, or empty string if no memories
    """
    if not memories:
        return ""

    lines = ["## User Memories\n"]
    lines.append("The following are relevant memories about the user:\n")

    for mem in memories:
        category = mem.get("category", "general")
        content = mem.get("content", "")
        is_pinned = mem.get("is_pinned", False)

        prefix = "[Pinned] " if is_pinned else ""
        lines.append(f"- {prefix}[{category}] {content}")

    lines.append("\nUse these memories to personalize your responses when relevant.")

    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Settings Management
# -----------------------------------------------------------------------------

def get_settings(user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Get memory settings for a user.

    Returns default settings if none exist.
    """
    defaults = {
        "auto_save_enabled": True,
        "auto_save_categories": DEFAULT_AUTO_CATEGORIES,
        "max_pinned_memories": 10,
    }

    if user_id is None:
        return defaults

    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT auto_save_enabled, auto_save_categories, max_pinned_memories
            FROM memory_settings
            WHERE user_id = ?
            """,
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
            "max_pinned_memories": row["max_pinned_memories"] or 10,
        }
    finally:
        conn.close()


def update_settings(
    user_id: int,
    auto_save_enabled: Optional[bool] = None,
    auto_save_categories: Optional[List[str]] = None,
    max_pinned_memories: Optional[int] = None,
) -> bool:
    """
    Update memory settings for a user.

    Creates settings record if it doesn't exist.
    """
    conn = _get_memory_db()
    cursor = conn.cursor()

    try:
        # Check if settings exist
        cursor.execute(
            "SELECT id FROM memory_settings WHERE user_id = ?",
            (user_id,)
        )
        exists = cursor.fetchone() is not None

        now = datetime.utcnow().isoformat()

        if exists:
            # Update existing
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
            # Insert new
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
                    max_pinned_memories or 10,
                    now,
                    now,
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
    """
    Check if a category is allowed for auto-save based on user settings.

    Args:
        category: The memory category
        user_id: User ID for settings lookup

    Returns:
        True if auto-save is allowed for this category
    """
    settings = get_settings(user_id)

    if not settings.get("auto_save_enabled", True):
        return False

    allowed_categories = settings.get("auto_save_categories", DEFAULT_AUTO_CATEGORIES)
    return category in allowed_categories


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
# Helper for getting service instance
# -----------------------------------------------------------------------------

_memory_service_instance = None

def get_memory_service():
    """Get memory service singleton (module itself acts as service)."""
    # This module acts as the service - return module reference
    import services.memory_service as svc
    return svc
