# api/services/library/settings_service.py

"""
Library settings service.

Manages user preferences for library behavior.
"""

import json
from typing import Any, Dict

from utils.db import get_db


# Default settings
DEFAULT_SETTINGS = {
    "context_injection_enabled": True,
    "context_max_chunks": 5,
    "context_max_chars": 4000,
    "context_min_score": 0.4,
    "context_scope": "all",  # 'library', 'project', 'all'
    "show_sources_in_response": True,
}


class LibrarySettingsService:
    """Service for managing library settings per user."""

    def __init__(self):
        pass

    def get_settings(self, user_id: int) -> Dict[str, Any]:
        """Get library settings for user."""
        conn = get_db()
        cur = conn.execute(
            "SELECT value FROM library_config WHERE key = ?",
            (f"user_settings_{user_id}",),
        )
        row = cur.fetchone()

        if row:
            try:
                settings = json.loads(row["value"])
                # Merge with defaults for any missing keys
                return {**DEFAULT_SETTINGS, **settings}
            except (json.JSONDecodeError, TypeError):
                pass

        return DEFAULT_SETTINGS.copy()

    def update_settings(self, user_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update library settings for user."""
        current = self.get_settings(user_id)

        # Only allow known settings
        for key in updates:
            if key in DEFAULT_SETTINGS:
                current[key] = updates[key]

        conn = get_db()
        conn.execute(
            """
            INSERT INTO library_config (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = CURRENT_TIMESTAMP
            """,
            (f"user_settings_{user_id}", json.dumps(current), json.dumps(current)),
        )
        conn.commit()

        return current

    def reset_settings(self, user_id: int) -> Dict[str, Any]:
        """Reset to default settings."""
        conn = get_db()
        conn.execute(
            "DELETE FROM library_config WHERE key = ?",
            (f"user_settings_{user_id}",),
        )
        conn.commit()
        return DEFAULT_SETTINGS.copy()

    def is_context_enabled(self, user_id: int) -> bool:
        """Quick check if context injection is enabled."""
        settings = self.get_settings(user_id)
        return settings.get("context_injection_enabled", True)
