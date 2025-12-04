# core/intent.py
"""
Lightweight intent parser for command-like interactions.

This module is intentionally small and explicit.
It should only handle structured, tool-like commands and leave the
rest to the normal chat behavior.
"""

from __future__ import annotations

import re
from typing import Dict, Optional
from datetime import datetime

from services.playlists import (
    add_movie_to_christmas_by_title,
    remove_movie_from_christmas,
    list_christmas_playlist,
    add_tmdb_candidate_to_christmas,
)
from services.tmdb_service import tmdb_search_candidates
from services.pending_intents import (
    set_christmas_movie_pending,
    get_pending_for_conversation,
    clear_pending_for_conversation,
    PENDING_TYPE_CHRISTMAS_MOVIE,
)
from utils.db import get_db


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Add movie to Christmas playlist/list
_ADD_CHRISTMAS_MOVIE_PATTERNS = [
    # add <title> to the christmas playlist
    re.compile(
        r"^\s*add\s+(?P<title>.+?)\s+to\s+the\s+christmas\s+playlist\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*add\s+(?P<title>.+?)\s+to\s+my\s+christmas\s+playlist\s*[.!?']*$",
        re.IGNORECASE,
    ),
    # add <title> to the christmas list
    re.compile(
        r"^\s*add\s+(?P<title>.+?)\s+to\s+the\s+christmas\s+list\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*add\s+(?P<title>.+?)\s+to\s+my\s+christmas\s+list\s*[.!?']*$",
        re.IGNORECASE,
    ),
    # put <title> on the christmas playlist/list
    re.compile(
        r"^\s*put\s+(?P<title>.+?)\s+on\s+the\s+christmas\s+playlist\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*put\s+(?P<title>.+?)\s+on\s+my\s+christmas\s+playlist\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*put\s+(?P<title>.+?)\s+on\s+the\s+christmas\s+list\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*put\s+(?P<title>.+?)\s+on\s+my\s+christmas\s+list\s*[.!?']*$",
        re.IGNORECASE,
    ),
]

# Remove a movie from the Christmas playlist/list
_REMOVE_CHRISTMAS_MOVIE_PATTERNS = [
    re.compile(
        r"^\s*remove\s+(?P<title>.+?)\s+from\s+the\s+christmas\s+playlist\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*remove\s+(?P<title>.+?)\s+from\s+my\s+christmas\s+playlist\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*remove\s+(?P<title>.+?)\s+from\s+the\s+christmas\s+list\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*remove\s+(?P<title>.+?)\s+from\s+my\s+christmas\s+list\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*take\s+(?P<title>.+?)\s+off\s+the\s+christmas\s+playlist\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*take\s+(?P<title>.+?)\s+off\s+my\s+christmas\s+playlist\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*take\s+(?P<title>.+?)\s+off\s+the\s+christmas\s+list\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*take\s+(?P<title>.+?)\s+off\s+my\s+christmas\s+list\s*[.!?']*$",
        re.IGNORECASE,
    ),
]

# Show / list the Christmas playlist/list
_SHOW_CHRISTMAS_PLAYLIST_PATTERNS = [
    re.compile(
        r"^\s*show\s+(me\s+)?(my\s+)?christmas\s+playlist\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*show\s+(me\s+)?(my\s+)?christmas\s+list\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*what'?s\s+on\s+(my\s+)?christmas\s+playlist\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*what'?s\s+on\s+(my\s+)?christmas\s+list\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*list\s+(my\s+)?christmas\s+playlist\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*list\s+(my\s+)?christmas\s+list\s*[.!?']*$",
        re.IGNORECASE,
    ),
]

# Rename the current conversation
_RENAME_CONVERSATION_PATTERNS = [
    re.compile(
        r"^\s*rename\s+(this\s+)?conversation\s+to\s+(?P<title>.+?)\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*call\s+this\s+conversation\s+(?P<title>.+?)\s*[.!?']*$",
        re.IGNORECASE,
    ),
]

# Create a new project
_CREATE_PROJECT_PATTERNS = [
    re.compile(
        r"^\s*create\s+(a\s+)?project\s+(called|named)\s+(?P<name>.+?)\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*make\s+(a\s+)?project\s+(called|named)\s+(?P<name>.+?)\s*[.!?']*$",
        re.IGNORECASE,
    ),
]

# Delete the current conversation
_DELETE_CONVERSATION_PATTERNS = [
    re.compile(
        r"^\s*(delete|remove|trash)\s+(this\s+)?conversation\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*delete\s+(this\s+)?chat\s*[.!?']*$",
        re.IGNORECASE,
    ),
]

# Rename an existing project
_RENAME_PROJECT_PATTERNS = [
    re.compile(
        r"^\s*rename\s+project\s+(?P<old>.+?)\s+to\s+(?P<new>.+?)\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*rename\s+the\s+project\s+(?P<old>.+?)\s+to\s+(?P<new>.+?)\s*[.!?']*$",
        re.IGNORECASE,
    ),
]

# Delete a project
_DELETE_PROJECT_PATTERNS = [
    re.compile(
        r"^\s*(delete|remove)\s+project\s+(?P<name>.+?)\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(delete|remove)\s+the\s+project\s+(?P<name>.+?)\s*[.!?']*$",
        re.IGNORECASE,
    ),
]

# Project notes: add / show / clear
_ADD_PROJECT_NOTE_PATTERNS = [
    re.compile(
        r"^\s*(add|create|make)\s+(a\s+)?project\s+note\s*:\s*(?P<note>.+?)\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*note\s+for\s+this\s+project\s*:\s*(?P<note>.+?)\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*add\s+note\s*:\s*(?P<note>.+?)\s*$",
        re.IGNORECASE,
    ),
]

_SHOW_PROJECT_NOTES_PATTERNS = [
    re.compile(
        r"^\s*show\s+(the\s+)?notes\s+for\s+this\s+project\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*show\s+project\s+notes\s*[.!?']*$",
        re.IGNORECASE,
    ),
]

_CLEAR_PROJECT_NOTES_PATTERNS = [
    re.compile(
        r"^\s*(clear|delete|remove)\s+(all\s+)?project\s+notes\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(clear|delete|remove)\s+(all\s+)?notes\s+for\s+this\s+project\s*[.!?']*$",
        re.IGNORECASE,
    ),
]

# Move the current conversation to a project
_MOVE_CONVERSATION_PATTERNS = [
    re.compile(
        r"^\s*move\s+(this\s+)?conversation\s+to\s+(project\s+)?(?P<project>.+?)\s*[.!?']*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*put\s+(this\s+)?conversation\s+in(to)?\s+(project\s+)?(?P<project>.+?)\s*[.!?']*$",
        re.IGNORECASE,
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_title(raw: str) -> str:
    """Trim quotes and trailing punctuation around a title."""
    if raw is None:
        return ""
    cleaned = raw.strip().strip('"“”‘’\'')
    cleaned = cleaned.strip(" .!?")
    return cleaned


def _rename_conversation_in_db(user_id: int, conversation_id: int, new_title: str) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE conversations
        SET title = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        """,
        (new_title, conversation_id, user_id),
    )
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def _create_project_in_db(user_id: int, name: str) -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO projects (user_id, name, description)
        VALUES (?, ?, '')
        """,
        (user_id, name),
    )
    conn.commit()
    project_id = cur.lastrowid
    conn.close()
    return project_id


def _move_conversation_to_project_in_db(
    user_id: int, conversation_id: int, project_name: str
) -> Optional[str]:
    """
    Move the conversation to the most recently-created project with this name.
    Returns the final project name, or None if not found.
    """
    conn = get_db()
    cur = conn.cursor()

    # Find project by name for this user
    cur.execute(
        """
        SELECT id, name
        FROM projects
        WHERE user_id = ? AND name = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id, project_name),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    proj_id = row["id"]
    proj_name = row["name"]

    # Update conversation
    cur.execute(
        """
        UPDATE conversations
        SET project_id = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        """,
        (proj_id, conversation_id, user_id),
    )
    conn.commit()
    conn.close()
    return proj_name


def _delete_conversation_in_db(user_id: int, conversation_id: int) -> bool:
    """Hard-delete a conversation (and its messages) for this user."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        DELETE FROM conversations
        WHERE id = ? AND user_id = ?
        """,
        (conversation_id, user_id),
    )
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def _rename_project_in_db(user_id: int, old_name: str, new_name: str) -> bool:
    """
    Rename the most recently-created project with this name for the user.
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id
        FROM projects
        WHERE user_id = ? AND name = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id, old_name),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return False

    proj_id = row["id"]

    cur.execute(
        """
        UPDATE projects
        SET name = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        """,
        (new_name, proj_id, user_id),
    )
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def _delete_project_in_db(user_id: int, name: str) -> bool:
    """
    Delete a project by name for this user.

    Conversations under this project are NOT deleted;
    their project_id is set to NULL via the FK.
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id
        FROM projects
        WHERE user_id = ? AND name = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id, name),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return False

    proj_id = row["id"]

    cur.execute(
        "DELETE FROM projects WHERE id = ? AND user_id = ?",
        (proj_id, user_id),
    )
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def _get_project_id_for_conversation(
    user_id: int, conversation_id: int
) -> Optional[int]:
    """Return the project_id for a conversation, or None."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT project_id
        FROM conversations
        WHERE id = ? AND user_id = ?
        """,
        (conversation_id, user_id),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return row["project_id"]


def _get_project_notes(user_id: int, project_id: int) -> str:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT content
        FROM project_notes
        WHERE user_id = ? AND project_id = ?
        """,
        (user_id, project_id),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return ""
    return row["content"] or ""


def _append_project_note(user_id: int, project_id: int, note_text: str) -> str:
    """
    Append a note line to the project's notes.
    We store a single TEXT field and append with timestamps.
    """
    note_text = note_text.strip()
    if not note_text:
        return _get_project_notes(user_id, project_id)

    conn = get_db()
    cur = conn.cursor()

    # Fetch existing content (if any)
    cur.execute(
        """
        SELECT id, content
        FROM project_notes
        WHERE user_id = ? AND project_id = ?
        """,
        (user_id, project_id),
    )
    row = cur.fetchone()

    stamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    new_line = f"[{stamp}] {note_text}"

    if not row:
        content = new_line
        cur.execute(
            """
            INSERT INTO project_notes (user_id, project_id, content)
            VALUES (?, ?, ?)
            """,
            (user_id, project_id, content),
        )
    else:
        prev = row["content"] or ""
        content = (prev + "\n" + new_line).strip()
        cur.execute(
            """
            UPDATE project_notes
            SET content = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (content, row["id"]),
        )

    conn.commit()
    conn.close()
    return content


def _clear_project_notes(user_id: int, project_id: int) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        DELETE FROM project_notes
        WHERE user_id = ? AND project_id = ?
        """,
        (user_id, project_id),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Intent parsing
# ---------------------------------------------------------------------------

def parse_intent(message: str) -> Optional[Dict]:
    """
    Inspect the raw user message and, when appropriate, return
    a structured intent dict.
    Returns None if no intent is recognized.
    """
    text = message or ""
    stripped = text.strip()
    if not stripped:
        return None

    # --- Numeric/multi-numeric selection for pending intents --------------
    stripped = text.strip().lower()

    # Accept:
    # "1", "1 3", "1,3", "1, 3, 4", "1-3", "all"
    multi_num_pattern = r"^(\d+([,\s-]+\d+)*)$"

    if stripped == "all":
        return {
            "type": "pending_selection_multi",
            "selection": "all",
            "raw": text,
        }

    if re.fullmatch(multi_num_pattern, stripped):
        return {
            "type": "pending_selection_multi",
            "selection": stripped,
            "raw": text,
        }

    # --- Add-movie-to-Christmas intent ------------------------------------
    for pattern in _ADD_CHRISTMAS_MOVIE_PATTERNS:
        m = pattern.match(stripped)
        if m:
            title = _clean_title(m.group("title") or "")
            return {
                "type": "add_christmas_movie",
                "movie_title": title,
                "raw": text,
            }

    # --- Remove-movie-from-Christmas intent -------------------------------
    for pattern in _REMOVE_CHRISTMAS_MOVIE_PATTERNS:
        m = pattern.match(stripped)
        if m:
            title = _clean_title(m.group("title") or "")
            return {
                "type": "remove_christmas_movie",
                "movie_title": title,
                "raw": text,
            }

    # --- Show/list-Christmas-playlist intent ------------------------------
    for pattern in _SHOW_CHRISTMAS_PLAYLIST_PATTERNS:
        if pattern.match(stripped):
            return {
                "type": "show_christmas_playlist",
                "raw": text,
            }

    # --- Rename-conversation intent ---------------------------------------
    for pattern in _RENAME_CONVERSATION_PATTERNS:
        m = pattern.match(stripped)
        if m:
            title = _clean_title(m.group("title") or "")
            return {
                "type": "rename_conversation",
                "new_title": title,
                "raw": text,
            }

    # --- Create-project intent --------------------------------------------
    for pattern in _CREATE_PROJECT_PATTERNS:
        m = pattern.match(stripped)
        if m:
            name = _clean_title(m.group("name") or "")
            return {
                "type": "create_project",
                "project_name": name,
                "raw": text,
            }

    # --- Delete-conversation intent ---------------------------------------
    for pattern in _DELETE_CONVERSATION_PATTERNS:
        if pattern.match(stripped):
            return {
                "type": "delete_conversation",
                "raw": text,
            }

    # --- Rename-project intent --------------------------------------------
    for pattern in _RENAME_PROJECT_PATTERNS:
        m = pattern.match(stripped)
        if m:
            old_name = _clean_title(m.group("old") or "")
            new_name = _clean_title(m.group("new") or "")
            return {
                "type": "rename_project",
                "old_name": old_name,
                "new_name": new_name,
                "raw": text,
            }

    # --- Delete-project intent --------------------------------------------
    for pattern in _DELETE_PROJECT_PATTERNS:
        m = pattern.match(stripped)
        if m:
            name = _clean_title(m.group("name") or "")
            return {
                "type": "delete_project",
                "project_name": name,
                "raw": text,
            }

    # --- Add project note --------------------------------------------------
    for pattern in _ADD_PROJECT_NOTE_PATTERNS:
        m = pattern.match(stripped)
        if m:
            note = (m.group("note") or "").strip()
            return {
                "type": "add_project_note",
                "note_text": note,
                "raw": text,
            }

    # --- Show project notes ------------------------------------------------
    for pattern in _SHOW_PROJECT_NOTES_PATTERNS:
        if pattern.match(stripped):
            return {
                "type": "show_project_notes",
                "raw": text,
            }

    # --- Clear project notes -----------------------------------------------
    for pattern in _CLEAR_PROJECT_NOTES_PATTERNS:
        if pattern.match(stripped):
            return {
                "type": "clear_project_notes",
                "raw": text,
            }

    # --- Move-conversation-to-project intent ------------------------------
    for pattern in _MOVE_CONVERSATION_PATTERNS:
        m = pattern.match(stripped)
        if m:
            project_name = _clean_title(m.group("project") or "")
            return {
                "type": "move_conversation_to_project",
                "project_name": project_name,
                "raw": text,
            }

    # (Future: additional intents)
    return None


# ---------------------------------------------------------------------------
# Intent execution
# ---------------------------------------------------------------------------

def execute_intent(
    intent: Dict,
    user_id: Optional[int] = None,
    conversation_id: Optional[int] = None,
) -> Dict:
    """
    Execute a parsed intent and return a result dict:

    {
      "handled": bool,
      "reply_text": str,
      "memory_matches": list,  # optional, usually []
      "meta": dict,            # optional extra info
    }
    """
    if not intent or "type" not in intent:
        return {"handled": False}

    itype = intent["type"]

    # --- Multi-selection pending intent (TMDb disambiguation) -------------
    if itype == "pending_selection_multi":
        sel = intent.get("selection")
        if conversation_id is None:
            return {"handled": False}

        pending = get_pending_for_conversation(conversation_id)
        if not pending or pending.get("type") != PENDING_TYPE_CHRISTMAS_MOVIE:
            return {"handled": False}

        candidates = pending.get("candidates") or []
        n = len(candidates)

        if not candidates:
            clear_pending_for_conversation(conversation_id)
            return {
                "handled": True,
                "reply_text": "There were candidates stored, but I don't have them anymore.",
                "memory_matches": [],
            }

        # Parse "all"
        if sel == "all":
            indices = list(range(1, n + 1))
        else:
            # Parse selections: “1 3”, “1,3”, "1-3"
            parts = re.split(r"[,\s]+", sel)
            indices = []
            for part in parts:
                if "-" in part:
                    start, end = part.split("-")
                    try:
                        start, end = int(start), int(end)
                        for k in range(start, end + 1):
                            indices.append(k)
                    except Exception:
                        pass
                else:
                    try:
                        indices.append(int(part))
                    except Exception:
                        pass

        # Deduplicate & validate
        indices = sorted(set([i for i in indices if 1 <= i <= n]))

        if not indices:
            return {
                "handled": True,
                "reply_text": f"Choose numbers between 1 and {n}.",
                "memory_matches": [],
            }

        # Add all selected
        messages = []
        for idx in indices:
            choice = candidates[idx - 1]
            msg = add_tmdb_candidate_to_christmas(choice)
            messages.append(f"{idx}. {msg}")

        clear_pending_for_conversation(conversation_id)

        return {
            "handled": True,
            "reply_text": "\n".join(messages),
            "memory_matches": [],
            "meta": {
                "intent": "pending_selection_multi",
                "selected_indices": indices,
            },
        }

    # --- Add movie to Christmas playlist -----------------------------------
    if itype == "add_christmas_movie":
        title = _clean_title(intent.get("movie_title") or "")

        if not title:
            return {
                "handled": True,
                "reply_text": (
                    "Tell me the movie title, like: "
                    "“Add The Polar Express to the Christmas playlist.”"
                ),
                "memory_matches": [],
                "meta": {"intent": itype, "needs_title": True},
            }

        # First try a TMDb multi-match search so we can disambiguate.
        candidates = tmdb_search_candidates(title, max_results=5)
        # Keep only those with an IMDb id; the others aren't useful for our playlist.
        candidates_with_ids = [c for c in candidates if c.get("imdb_id")]

        # If TMDb returned nothing useful, fall back to the old single-lookup behavior.
        if not candidates_with_ids:
            raw_reply = add_movie_to_christmas_by_title(title) or ""
            lower = raw_reply.lower()

            # Collapse long 'here’s your playlist' messages into a short one
            if (
                "here is your christmas playlist" in lower
                or "here is the updated list" in lower
                or "christmas movie playlist" in lower
                or lower.startswith("certainly! i will add")
            ):
                simple_reply = f'I’ve added “{title}” to the Christmas playlist.'
            else:
                # For errors like “I couldn’t find …”, keep the original wording.
                simple_reply = raw_reply

            return {
                "handled": True,
                "reply_text": simple_reply,
                "memory_matches": [],
                "meta": {"intent": itype, "movie_title": title},
            }

        # If there is exactly one solid candidate, add it immediately.
        if len(candidates_with_ids) == 1:
            choice = candidates_with_ids[0]
            reply = add_tmdb_candidate_to_christmas(choice)
            return {
                "handled": True,
                "reply_text": reply,
                "memory_matches": [],
                "meta": {
                    "intent": itype,
                    "movie_title": title,
                    "tmdb_id": choice.get("tmdb_id"),
                    "imdb_id": choice.get("imdb_id"),
                },
            }

        # Otherwise, store a pending disambiguation and list the options.
        set_christmas_movie_pending(
            conversation_id=conversation_id or 0,
            original_title=title,
            candidates=candidates_with_ids,
        )

        lines = [f'I found multiple matches for “{title}”:', ""]
        for idx, c in enumerate(candidates_with_ids, start=1):
            year = f" ({c['year']})" if c.get("year") else ""
            lines.append(f"{idx}. {c['title']}{year}")
        lines.append("")
        lines.append("Reply with 1, 2, 3, etc. to choose the right one.")

        return {
            "handled": True,
            "reply_text": "\n".join(lines),
            "memory_matches": [],
            "meta": {
                "intent": itype,
                "movie_title": title,
                "candidate_count": len(candidates_with_ids),
            },
        }

    # --- Remove movie from Christmas playlist ------------------------------
    elif itype == "remove_christmas_movie":
        title = _clean_title(intent.get("movie_title") or "")

        if not title:
            return {
                "handled": True,
                "reply_text": (
                    "Tell me the movie title, like: "
                    "“Remove The Polar Express from the Christmas playlist.”"
                ),
                "memory_matches": [],
                "meta": {"intent": itype, "needs_title": True},
            }

        reply = remove_movie_from_christmas(title)
        return {
            "handled": True,
            "reply_text": reply,
            "memory_matches": [],
            "meta": {"intent": itype, "movie_title": title},
        }

    # --- Show Christmas playlist -------------------------------------------
    elif itype == "show_christmas_playlist":
        movies = list_christmas_playlist() or []
        if not movies:
            reply = "Your Christmas playlist is currently empty."
        else:
            lines = []
            for i, m in enumerate(movies, start=1):
                name = m.get("name") or "Untitled"
                lines.append(f"{i}. {name}")
            reply = "Here’s your Christmas playlist:\n" + "\n".join(lines)

        return {
            "handled": True,
            "reply_text": reply,
            "memory_matches": [],
            "meta": {
                "intent": itype,
                "count": len(movies),
            },
        }

    # --- Rename conversation -----------------------------------------------
    elif itype == "rename_conversation":
        if user_id is None or conversation_id is None:
            return {
                "handled": True,
                "reply_text": (
                    "I can only rename a conversation when you're inside one."
                ),
                "memory_matches": [],
                "meta": {"intent": itype, "missing_context": True},
            }

        new_title = _clean_title(intent.get("new_title") or "")
        if not new_title:
            return {
                "handled": True,
                "reply_text": (
                    "Tell me what to call this conversation, like: "
                    "“Rename this conversation to Christmas Planning.”"
                ),
                "memory_matches": [],
                "meta": {"intent": itype, "needs_title": True},
            }

        changed = _rename_conversation_in_db(user_id, conversation_id, new_title)
        if not changed:
            reply = "I couldn't rename this conversation. It may not belong to you."
        else:
            reply = f'I’ve renamed this conversation to “{new_title}”.'

        return {
            "handled": True,
            "reply_text": reply,
            "memory_matches": [],
            "meta": {
                "intent": itype,
                "conversation_id": conversation_id,
                "new_title": new_title,
            },
        }

    # --- Create project ----------------------------------------------------
    elif itype == "create_project":
        if user_id is None:
            return {
                "handled": True,
                "reply_text": "You need to be signed in to create a project.",
                "memory_matches": [],
                "meta": {"intent": itype, "missing_context": True},
            }

        name = _clean_title(intent.get("project_name") or "")
        if not name:
            return {
                "handled": True,
                "reply_text": (
                    "Tell me the project name, like: "
                    "“Create a project called 2025 Trade Show Prep.”"
                ),
                "memory_matches": [],
                "meta": {"intent": itype, "needs_name": True},
            }

        project_id = _create_project_in_db(user_id, name)

        reply = f'Created a project called “{name}”.'
        return {
            "handled": True,
            "reply_text": reply,
            "memory_matches": [],
            "meta": {"intent": itype, "project_id": project_id, "name": name},
        }

    # --- Delete current conversation --------------------------------------
    elif itype == "delete_conversation":
        if user_id is None or conversation_id is None:
            return {
                "handled": True,
                "reply_text": "I can only delete a conversation when you're inside one.",
                "memory_matches": [],
                "meta": {"intent": itype, "missing_context": True},
            }

        ok = _delete_conversation_in_db(user_id, conversation_id)
        if not ok:
            return {
                "handled": True,
                "reply_text": "I couldn't delete this conversation (it may not exist or belong to you).",
                "memory_matches": [],
                "meta": {"intent": itype, "deleted": False},
            }

        return {
            "handled": True,
            "reply_text": "Okay, I’ve deleted this conversation.",
            "memory_matches": [],
            "meta": {"intent": itype, "deleted": True},
        }

    # --- Rename project ----------------------------------------------------
    elif itype == "rename_project":
        if user_id is None:
            return {
                "handled": True,
                "reply_text": "You need to be logged in to rename a project.",
                "memory_matches": [],
                "meta": {"intent": itype, "missing_user": True},
            }

        old_name = _clean_title(intent.get("old_name") or "")
        new_name = _clean_title(intent.get("new_name") or "")

        if not old_name or not new_name:
            return {
                "handled": True,
                "reply_text": "Please say something like: “Rename project X to Y.”",
                "memory_matches": [],
                "meta": {"intent": itype, "needs_names": True},
            }

        ok = _rename_project_in_db(user_id, old_name, new_name)
        if not ok:
            return {
                "handled": True,
                "reply_text": f"I couldn't find a project called “{old_name}” to rename.",
                "memory_matches": [],
                "meta": {"intent": itype, "renamed": False},
            }

        return {
            "handled": True,
            "reply_text": f"Renamed project “{old_name}” to “{new_name}”.",
            "memory_matches": [],
            "meta": {"intent": itype, "renamed": True},
        }

    # --- Delete project ----------------------------------------------------
    elif itype == "delete_project":
        if user_id is None:
            return {
                "handled": True,
                "reply_text": "You need to be logged in to delete a project.",
                "memory_matches": [],
                "meta": {"intent": itype, "missing_user": True},
            }

        name = _clean_title(intent.get("project_name") or "")
        if not name:
            return {
                "handled": True,
                "reply_text": "Tell me which project to delete, e.g., “Delete project X.”",
                "memory_matches": [],
                "meta": {"intent": itype, "needs_name": True},
            }

        ok = _delete_project_in_db(user_id, name)
        if not ok:
            return {
                "handled": True,
                "reply_text": f"I couldn't find a project called “{name}” to delete.",
                "memory_matches": [],
                "meta": {"intent": itype, "deleted": False},
            }

        return {
            "handled": True,
            "reply_text": f"Deleted project “{name}”. Conversations were kept under Unassigned.",
            "memory_matches": [],
            "meta": {"intent": itype, "deleted": True},
        }

    # --- Add project note --------------------------------------------------
    elif itype == "add_project_note":
        if user_id is None or conversation_id is None:
            return {
                "handled": True,
                "reply_text": "I can only attach notes when you're inside a conversation.",
                "memory_matches": [],
                "meta": {"intent": itype, "missing_context": True},
            }

        note_text = (intent.get("note_text") or "").strip()
        if not note_text:
            return {
                "handled": True,
                "reply_text": "Tell me the note text after “Add project note: ...”.",
                "memory_matches": [],
                "meta": {"intent": itype, "needs_text": True},
            }

        project_id = _get_project_id_for_conversation(user_id, conversation_id)
        if not project_id:
            return {
                "handled": True,
                "reply_text": (
                    "This conversation isn't in a project yet. "
                    "Create or move it into a project first, then I can attach notes."
                ),
                "memory_matches": [],
                "meta": {"intent": itype, "missing_project": True},
            }

        content = _append_project_note(user_id, project_id, note_text)
        return {
            "handled": True,
            "reply_text": "Got it — I’ve added that to this project’s notes.",
            "memory_matches": [],
            "meta": {
                "intent": itype,
                "project_id": project_id,
                "note_length": len(content),
            },
        }

    # --- Show project notes -------------------------------------------------
    elif itype == "show_project_notes":
        if user_id is None or conversation_id is None:
            return {
                "handled": True,
                "reply_text": "I can only show project notes when you're inside a conversation.",
                "memory_matches": [],
                "meta": {"intent": itype, "missing_context": True},
            }

        project_id = _get_project_id_for_conversation(user_id, conversation_id)
        if not project_id:
            return {
                "handled": True,
                "reply_text": "This conversation isn't in a project yet, so there are no project notes.",
                "memory_matches": [],
                "meta": {"intent": itype, "missing_project": True},
            }

        content = _get_project_notes(user_id, project_id)
        if not content.strip():
            return {
                "handled": True,
                "reply_text": "There are no notes for this project yet.",
                "memory_matches": [],
                "meta": {"intent": itype, "project_id": project_id},
            }

        return {
            "handled": True,
            "reply_text": "Here are the notes for this project:\n\n" + content,
            "memory_matches": [],
            "meta": {"intent": itype, "project_id": project_id},
        }

    # --- Clear project notes ------------------------------------------------
    elif itype == "clear_project_notes":
        if user_id is None or conversation_id is None:
            return {
                "handled": True,
                "reply_text": "I can only clear project notes when you're inside a conversation.",
                "memory_matches": [],
                "meta": {"intent": itype, "missing_context": True},
            }

        project_id = _get_project_id_for_conversation(user_id, conversation_id)
        if not project_id:
            return {
                "handled": True,
                "reply_text": "This conversation isn't in a project yet, so there are no project notes.",
                "memory_matches": [],
                "meta": {"intent": itype, "missing_project": True},
            }

        _clear_project_notes(user_id, project_id)
        return {
            "handled": True,
            "reply_text": "Cleared all notes for this project.",
            "memory_matches": [],
            "meta": {"intent": itype, "project_id": project_id},
        }

    # --- Move conversation to project --------------------------------------
    elif itype == "move_conversation_to_project":
        if user_id is None or conversation_id is None:
            return {
                "handled": True,
                "reply_text": (
                    "I can only move a conversation when you're inside one."
                ),
                "memory_matches": [],
                "meta": {"intent": itype, "missing_context": True},
            }

        project_name = _clean_title(intent.get("project_name") or "")
        if not project_name:
            return {
                "handled": True,
                "reply_text": (
                    "Tell me which project to use, like: "
                    "“Move this conversation to Christmas Movie List.”"
                ),
                "memory_matches": [],
                "meta": {"intent": itype, "needs_name": True},
            }

        final_name = _move_conversation_to_project_in_db(
            user_id, conversation_id, project_name
        )

        if final_name is None:
            reply = (
                f'I couldn’t find a project called “{project_name}”. '
                "You can create one by saying, "
                "“Create a project called Christmas Movie List.”"
            )
        else:
            reply = f'I’ve moved this conversation to the project “{final_name}”.'

        return {
            "handled": True,
            "reply_text": reply,
            "memory_matches": [],
            "meta": {
                "intent": itype,
                "conversation_id": conversation_id,
                "project_name": project_name,
                "resolved_project_name": final_name,
            },
        }

    # --- Unknown intent type (defensive) -----------------------------------
    return {"handled": False}

