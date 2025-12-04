# services/pending_intents.py
"""Helpers for storing and resolving 'pending intents' per conversation.

Right now this is only used for TMDb / Christmas playlist disambiguation, but
the schema is generic enough to support other pending flows later.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, List

from utils.db import get_db


PENDING_TYPE_CHRISTMAS_MOVIE = "disambiguate_christmas_movie"


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "conversation_id": row["conversation_id"],
        "type": row["type"],
        "original_title": row["original_title"],
        "candidates": json.loads(row["candidates"] or "[]"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_pending_for_conversation(conversation_id: int) -> Optional[Dict[str, Any]]:
    """Return the pending intent for this conversation, if any."""
    if not conversation_id:
        return None

    conn = get_db()
    try:
        cur = conn.execute(
            """
            SELECT id, conversation_id, type, original_title, candidates,
                   created_at, updated_at
            FROM pending_intents
            WHERE conversation_id = ?
            """,
            (conversation_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return _row_to_dict(row)
    except Exception as e:
        print("[pending_intents] get_pending_for_conversation failed", e)
        return None
    finally:
        conn.close()


def clear_pending_for_conversation(conversation_id: int) -> None:
    """Delete any pending intent for this conversation."""
    if not conversation_id:
        return
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM pending_intents WHERE conversation_id = ?",
            (conversation_id,),
        )
        conn.commit()
    except Exception as e:
        print("[pending_intents] clear_pending_for_conversation failed", e)
    finally:
        conn.close()


def set_christmas_movie_pending(
    conversation_id: int,
    original_title: str,
    candidates: List[Dict[str, Any]],
) -> None:
    """Insert or replace the pending entry for this conversation.

    We enforce 'one pending per conversation' with a UNIQUE constraint at the DB
    level, but this helper also does a manual delete/insert for clarity.
    """
    if not conversation_id:
        return

    payload_json = json.dumps(candidates, ensure_ascii=False)

    conn = get_db()
    try:
        # Simple strategy: delete any existing pending intent for this convo,
        # then insert a fresh one.
        conn.execute(
            "DELETE FROM pending_intents WHERE conversation_id = ?",
            (conversation_id,),
        )
        conn.execute(
            """
            INSERT INTO pending_intents
                (conversation_id, type, original_title, candidates)
            VALUES (?, ?, ?, ?)
            """,
            (conversation_id, PENDING_TYPE_CHRISTMAS_MOVIE, original_title, payload_json),
        )
        conn.commit()
    except Exception as e:
        print("[pending_intents] set_christmas_movie_pending failed", e)
    finally:
        conn.close()
