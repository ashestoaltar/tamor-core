# api/services/references/__init__.py
"""
Reference storage and retrieval services for Tamor.

This package provides:
- ReferenceStorage: Directory structure and configuration management
- SwordManager: SWORD Bible module download and management
- SwordClient: Bible passage lookup from local SWORD modules
- SefariaClient: Sefaria API access with aggressive local caching
"""

from .storage import ReferenceStorage
from .sword_manager import (
    SwordManager,
    SwordModuleError,
    ModuleNotFoundError,
    DownloadError,
    ExtractionError,
)
from .sword_client import (
    SwordClient,
    ReferenceParseError,
    parse_reference,
)
from .sefaria_client import (
    SefariaClient,
    SefariaError,
    SefariaNetworkError,
)

__all__ = [
    "ReferenceStorage",
    "SwordManager",
    "SwordModuleError",
    "ModuleNotFoundError",
    "DownloadError",
    "ExtractionError",
    "SwordClient",
    "ReferenceParseError",
    "parse_reference",
    "SefariaClient",
    "SefariaError",
    "SefariaNetworkError",
]
