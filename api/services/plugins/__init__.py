"""
Plugin Services

Phase 6.4: Plugin Framework Expansion

Services for managing plugin configurations.
"""

from .config_manager import (
    PluginConfigManager,
    get_project_plugin_config,
    set_project_plugin_config,
)

__all__ = [
    "PluginConfigManager",
    "get_project_plugin_config",
    "set_project_plugin_config",
]
