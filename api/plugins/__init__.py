"""
Plugin Framework Base Classes

Phase 6.3: Plugin Framework (MVP)

Provides base classes for building importer plugins that let Tamor
read from/write to the outside world through strict contracts.

MVP Scope:
- Importers only (read-only or append-only)
- Project-scoped
- Deterministic execution (no LLM inside plugins)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ImportItem:
    """Represents a single item discovered by an importer plugin."""
    id: str
    name: str
    path: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportResult:
    """Result of importing a single item."""
    success: bool
    file_id: Optional[int] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ImporterPlugin(ABC):
    """
    Base class for importer plugins.

    Importers discover and import external content into Tamor projects.
    They must be deterministic (no LLM calls) and return artifacts
    that the system handles for storage.

    Constraints:
    - No UI logic in plugins
    - No LLM calls inside plugins
    - Plugins return artifacts, system handles storage
    """

    # Plugin identification
    id: str = ""
    name: str = ""
    type: str = "importer"
    description: str = ""

    # Configuration schema for this plugin
    # Format: {"field_name": {"type": "string", "required": True, "description": "..."}}
    config_schema: Dict[str, Any] = {}

    @abstractmethod
    def validate_config(self, config: Dict) -> bool:
        """
        Validate the provided configuration against the schema.

        Args:
            config: Configuration dictionary to validate

        Returns:
            True if config is valid, False otherwise
        """
        pass

    @abstractmethod
    def list_items(self, config: Dict) -> List[ImportItem]:
        """
        Discover available items to import based on the configuration.

        Args:
            config: Plugin configuration (e.g., path to scan)

        Returns:
            List of ImportItem objects representing discoverable items
        """
        pass

    @abstractmethod
    def import_item(self, item: ImportItem, project_id: int, user_id: int) -> ImportResult:
        """
        Import a single item into the specified project.

        Args:
            item: The ImportItem to import
            project_id: Target project ID
            user_id: User performing the import

        Returns:
            ImportResult with success status and file_id if successful
        """
        pass

    def get_info(self) -> Dict[str, Any]:
        """Return plugin information for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "config_schema": self.config_schema
        }
