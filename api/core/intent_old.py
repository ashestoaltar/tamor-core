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

from services.playlists import add_movie_to_christmas_by_title


# Precompiled patterns for "add movie to Christmas playlist/list" style commands.
# We keep these fairly permissive but still structured, so normal sentences
# (e.g., theological discussion about Christmas) won't accidentally trigger.
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


def _clean_title(raw: str) -> str:
    """Trim quotes and trailing punctuation around a title."""
    if raw is None:
        return ""
    cleaned = raw.strip().strip('"“”‘’\'')
    cleaned = cleaned.strip(" .!?")
    return cleaned


def parse_intent(message: str) -> Optional[Dict]:
    """
    Inspect the raw user message and, when appropriate, return
    a structured intent dict.

    For now this is deliberately narrow:
    - add_christmas_movie: add a movie to the Christmas playlist/list

    Returns None if no intent is recognized.
    """
    text = message or ""
    stripped = text.strip()
    if not stripped:
        return None

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

    # (Future: additional intents like remove_movie, list_playlist, etc.)

    return None


def execute_intent(intent: Dict) -> Dict:
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

        reply = add_movie_to_christmas_by_title(title)
        return {
            "handled": True,
            "reply_text": reply,
            "memory_matches": [],
            "meta": {"intent": itype, "movie_title": title},
        }

    # --- Unknown intent type (defensive) -----------------------------------
    return {"handled": False}
