"""
Plugin Framework Base Classes

Phase 6.3: Plugin Framework

Provides base classes for building plugins that let Tamor
read from/write to the outside world through strict contracts.

Plugin Types:
- Importers: Import external content into projects
- Exporters: Export project data to various formats
- References: Reference external content without importing

Constraints:
- No UI logic in plugins
- No LLM calls inside plugins
- Plugins return artifacts, system handles storage
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Importer Plugin Types
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Exporter Plugin Types
# ---------------------------------------------------------------------------


@dataclass
class ExportResult:
    """Result of exporting project data."""
    success: bool
    export_path: Optional[str] = None    # Path to generated file (for download)
    filename: Optional[str] = None       # Suggested download filename
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExporterPlugin(ABC):
    """
    Base class for exporter plugins.

    Exporters generate downloadable files from project data
    in various formats (ZIP, JSON, etc.).
    """

    # Plugin identification
    id: str = ""
    name: str = ""
    type: str = "exporter"
    description: str = ""

    # Configuration schema for this plugin
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
    def export_project(self, project_id: int, user_id: int, config: Dict) -> ExportResult:
        """
        Export project data to a downloadable format.

        Args:
            project_id: Source project ID
            user_id: User performing the export
            config: Export configuration options

        Returns:
            ExportResult with path to generated file
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


# ---------------------------------------------------------------------------
# Reference Plugin Types
# ---------------------------------------------------------------------------


@dataclass
class ReferenceItem:
    """Represents a single item from a reference source."""
    id: str
    title: str
    path: str                           # File path or URL
    content_preview: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReferenceResult:
    """Result of listing reference items."""
    success: bool
    items: List[ReferenceItem] = field(default_factory=list)
    total: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FetchResult:
    """Result of fetching a single reference item's content."""
    success: bool
    content: Optional[str] = None       # Full text content
    title: Optional[str] = None
    url: Optional[str] = None
    fetched_at: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ReferencePlugin(ABC):
    """
    Base class for reference plugins.

    References allow browsing and fetching external content
    without importing it into the project. Content is fetched
    on-demand and can optionally be imported afterward.

    Key behaviors:
    - Read-only access to external sources
    - On-demand content fetching
    - Clear provenance tracking
    """

    # Plugin identification
    id: str = ""
    name: str = ""
    type: str = "reference"
    description: str = ""

    # Configuration schema for this plugin
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
    def list_items(self, config: Dict) -> ReferenceResult:
        """
        List available items from the reference source.

        Args:
            config: Plugin configuration (e.g., directory path, search query)

        Returns:
            ReferenceResult with list of available items
        """
        pass

    @abstractmethod
    def fetch_item(self, item_id: str, config: Dict) -> FetchResult:
        """
        Fetch full content of a specific item.

        Args:
            item_id: Identifier of the item to fetch
            config: Plugin configuration

        Returns:
            FetchResult with full content
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
