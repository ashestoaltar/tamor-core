"""
Plugin Registry

Phase 6.3: Plugin Framework

Provides central registry for discovering and managing plugins.
Auto-discovers plugins from the plugins/importers/, exporters/, and references/ directories.
"""

import importlib
import logging
import os
import pkgutil
from typing import Dict, List, Optional

from plugins import ImporterPlugin, ExporterPlugin, ReferencePlugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    Central registry for all plugins.

    Handles plugin registration, discovery, and retrieval.
    Supports auto-discovery from the importers/, exporters/, and references/ subdirectories.
    """

    def __init__(self):
        self._importers: Dict[str, ImporterPlugin] = {}
        self._exporters: Dict[str, ExporterPlugin] = {}
        self._references: Dict[str, ReferencePlugin] = {}

    # ---------------------------------------------------------------------------
    # Importer Methods
    # ---------------------------------------------------------------------------

    def register(self, plugin: ImporterPlugin) -> None:
        """
        Register an importer plugin instance.

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
        Get an importer plugin by its ID.

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

    # ---------------------------------------------------------------------------
    # Exporter Methods
    # ---------------------------------------------------------------------------

    def register_exporter(self, plugin: ExporterPlugin) -> None:
        """
        Register an exporter plugin instance.

        Args:
            plugin: An ExporterPlugin instance to register
        """
        if not plugin.id:
            logger.error("Cannot register exporter plugin without an id")
            return

        if plugin.id in self._exporters:
            logger.warning(f"Exporter {plugin.id} already registered, replacing")

        self._exporters[plugin.id] = plugin
        logger.info(f"Registered exporter plugin: {plugin.id}")

    def get_exporter(self, plugin_id: str) -> Optional[ExporterPlugin]:
        """
        Get an exporter plugin by its ID.

        Args:
            plugin_id: The unique plugin identifier

        Returns:
            The plugin instance or None if not found
        """
        return self._exporters.get(plugin_id)

    def list_exporters(self) -> List[Dict]:
        """
        List all registered exporter plugins.

        Returns:
            List of plugin info dictionaries
        """
        return [plugin.get_info() for plugin in self._exporters.values()]

    # ---------------------------------------------------------------------------
    # Reference Methods
    # ---------------------------------------------------------------------------

    def register_reference(self, plugin: ReferencePlugin) -> None:
        """
        Register a reference plugin instance.

        Args:
            plugin: A ReferencePlugin instance to register
        """
        if not plugin.id:
            logger.error("Cannot register reference plugin without an id")
            return

        if plugin.id in self._references:
            logger.warning(f"Reference {plugin.id} already registered, replacing")

        self._references[plugin.id] = plugin
        logger.info(f"Registered reference plugin: {plugin.id}")

    def get_reference(self, plugin_id: str) -> Optional[ReferencePlugin]:
        """
        Get a reference plugin by its ID.

        Args:
            plugin_id: The unique plugin identifier

        Returns:
            The plugin instance or None if not found
        """
        return self._references.get(plugin_id)

    def list_references(self) -> List[Dict]:
        """
        List all registered reference plugins.

        Returns:
            List of plugin info dictionaries
        """
        return [plugin.get_info() for plugin in self._references.values()]

    # ---------------------------------------------------------------------------
    # Plugin Loading
    # ---------------------------------------------------------------------------

    def load_plugins(self) -> None:
        """
        Auto-discover and register plugins from all plugin directories.

        Scans importers/, exporters/, and references/ directories for Python modules
        and looks for classes that inherit from the appropriate base class.
        """
        plugins_dir = os.path.dirname(__file__)

        # Load importers
        self._load_plugin_type(
            os.path.join(plugins_dir, "importers"),
            "plugins.importers",
            ImporterPlugin,
            self.register,
        )

        # Load exporters
        self._load_plugin_type(
            os.path.join(plugins_dir, "exporters"),
            "plugins.exporters",
            ExporterPlugin,
            self.register_exporter,
        )

        # Load references
        self._load_plugin_type(
            os.path.join(plugins_dir, "references"),
            "plugins.references",
            ReferencePlugin,
            self.register_reference,
        )

        logger.info(
            f"Loaded plugins: {len(self._importers)} importers, "
            f"{len(self._exporters)} exporters, {len(self._references)} references"
        )

    def _load_plugin_type(
        self,
        directory: str,
        module_prefix: str,
        base_class: type,
        register_func,
    ) -> None:
        """
        Load plugins of a specific type from a directory.

        Args:
            directory: Path to the plugin directory
            module_prefix: Module prefix for imports (e.g., "plugins.importers")
            base_class: The base class to look for (e.g., ImporterPlugin)
            register_func: Function to call to register discovered plugins
        """
        if not os.path.exists(directory):
            logger.debug(f"Plugin directory not found: {directory}")
            return

        # Iterate through all Python modules in the directory
        for finder, module_name, is_pkg in pkgutil.iter_modules([directory]):
            if module_name.startswith("_"):
                continue  # Skip __init__ and private modules

            try:
                # Import the module
                module = importlib.import_module(f"{module_prefix}.{module_name}")

                # Look for plugin subclasses
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)

                    # Check if it's a class and subclass of the base class
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, base_class)
                        and attr is not base_class
                    ):
                        try:
                            # Instantiate and register
                            plugin_instance = attr()
                            register_func(plugin_instance)
                        except Exception as e:
                            logger.error(
                                f"Failed to instantiate plugin {attr_name}: {e}"
                            )

            except Exception as e:
                logger.error(f"Failed to load plugin module {module_name}: {e}")


# Global registry instance
REGISTRY = PluginRegistry()


def get_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    return REGISTRY


def load_all_plugins() -> None:
    """Load all plugins into the global registry."""
    REGISTRY.load_plugins()
