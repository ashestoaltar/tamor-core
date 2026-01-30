"""
Plugin Config Manager

Phase 6.4: Plugin Framework Expansion

Manages per-project plugin configurations stored in the database.
"""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class PluginConfigManager:
    """Manages plugin configurations for a project."""

    def __init__(self, project_id: int, db):
        self.project_id = project_id
        self.db = db

    def get_all_config(self) -> Dict[str, Any]:
        """Get all plugin configs for this project."""
        cur = self.db.cursor()
        cur.execute(
            "SELECT plugin_config FROM projects WHERE id = ?",
            (self.project_id,),
        )
        result = cur.fetchone()

        if result and result[0]:
            try:
                return json.loads(result[0])
            except json.JSONDecodeError:
                logger.warning(
                    f"Invalid plugin_config JSON for project {self.project_id}"
                )
                return {}
        return {}

    def get_plugin_config(self, plugin_id: str) -> Dict[str, Any]:
        """Get config for a specific plugin."""
        all_config = self.get_all_config()
        return all_config.get(plugin_id, {})

    def set_plugin_config(self, plugin_id: str, config: Dict[str, Any]) -> None:
        """Set config for a specific plugin."""
        all_config = self.get_all_config()
        all_config[plugin_id] = config

        cur = self.db.cursor()
        cur.execute(
            "UPDATE projects SET plugin_config = ? WHERE id = ?",
            (json.dumps(all_config), self.project_id),
        )
        self.db.commit()

    def update_plugin_config(self, plugin_id: str, updates: Dict[str, Any]) -> None:
        """Merge updates into existing plugin config."""
        current = self.get_plugin_config(plugin_id)
        current.update(updates)
        self.set_plugin_config(plugin_id, current)

    def delete_plugin_config(self, plugin_id: str) -> None:
        """Remove config for a specific plugin."""
        all_config = self.get_all_config()
        if plugin_id in all_config:
            del all_config[plugin_id]
            cur = self.db.cursor()
            cur.execute(
                "UPDATE projects SET plugin_config = ? WHERE id = ?",
                (json.dumps(all_config), self.project_id),
            )
            self.db.commit()

    def is_plugin_enabled(self, plugin_id: str) -> bool:
        """Check if a plugin is enabled for this project."""
        config = self.get_plugin_config(plugin_id)
        return config.get("enabled", False)


# Convenience functions
def get_project_plugin_config(project_id: int, plugin_id: str, db) -> Dict[str, Any]:
    """Get plugin config for a project."""
    manager = PluginConfigManager(project_id, db)
    return manager.get_plugin_config(plugin_id)


def set_project_plugin_config(
    project_id: int, plugin_id: str, config: Dict[str, Any], db
) -> None:
    """Set plugin config for a project."""
    manager = PluginConfigManager(project_id, db)
    manager.set_plugin_config(plugin_id, config)
