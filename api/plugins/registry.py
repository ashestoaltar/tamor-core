"""
Plugin Registry

Phase 6.3: Plugin Framework (MVP)

Provides central registry for discovering and managing plugins.
Auto-discovers plugins from the plugins/importers/ directory.
"""

import importlib
import logging
import os
import pkgutil
from typing import Dict, List, Optional

from plugins import ImporterPlugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    Central registry for all plugins.

    Handles plugin registration, discovery, and retrieval.
    Supports auto-discovery from the importers/ subdirectory.
    """

    def __init__(self):
        self._importers: Dict[str, ImporterPlugin] = {}

    def register(self, plugin: ImporterPlugin) -> None:
        """
        Register a plugin instance.

        Args:
            plugin: An ImporterPlugin instance to register
        """
        if not plugin.id:
            logger.error("Cannot register plugin without an id")
            return

        if plugin.id in self._importers:
            logger.warning(f"Plugin {plugin.id} already registered, replacing")

        self._importers[plugin.id] = plugin
        logger.info(f"Registered importer plugin: {plugin.id}")

    def get(self, plugin_id: str) -> Optional[ImporterPlugin]:
        """
        Get a plugin by its ID.

        Args:
            plugin_id: The unique plugin identifier

        Returns:
            The plugin instance or None if not found
        """
        return self._importers.get(plugin_id)

    def list_importers(self) -> List[Dict]:
        """
        List all registered importer plugins.

        Returns:
            List of plugin info dictionaries
        """
        return [plugin.get_info() for plugin in self._importers.values()]

    def load_plugins(self) -> None:
        """
        Auto-discover and register plugins from plugins/importers/.

        Scans the importers directory for Python modules and looks for
        classes that inherit from ImporterPlugin. Each discovered class
        is instantiated and registered.
        """
        # Get the path to the importers directory
        plugins_dir = os.path.dirname(__file__)
        importers_dir = os.path.join(plugins_dir, "importers")

        if not os.path.exists(importers_dir):
            logger.warning(f"Importers directory not found: {importers_dir}")
            return

        # Iterate through all Python modules in importers/
        for finder, module_name, is_pkg in pkgutil.iter_modules([importers_dir]):
            if module_name.startswith("_"):
                continue  # Skip __init__ and private modules

            try:
                # Import the module
                module = importlib.import_module(f"plugins.importers.{module_name}")

                # Look for ImporterPlugin subclasses
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)

                    # Check if it's a class and subclass of ImporterPlugin
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, ImporterPlugin)
                        and attr is not ImporterPlugin
                    ):
                        try:
                            # Instantiate and register
                            plugin_instance = attr()
                            self.register(plugin_instance)
                        except Exception as e:
                            logger.error(
                                f"Failed to instantiate plugin {attr_name}: {e}"
                            )

            except Exception as e:
                logger.error(f"Failed to load plugin module {module_name}: {e}")

        logger.info(f"Loaded {len(self._importers)} importer plugins")


# Global registry instance
REGISTRY = PluginRegistry()


def get_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    return REGISTRY


def load_all_plugins() -> None:
    """Load all plugins into the global registry."""
    REGISTRY.load_plugins()
