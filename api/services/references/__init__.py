# api/services/references/__init__.py
"""
Reference storage and retrieval services for Tamor.

This package provides:
- ReferenceService: Unified interface for all reference lookups
- Reference: Dataclass for scripture passages with text
- ReferenceStorage: Directory structure and configuration management
- SwordManager: SWORD Bible module download and management
- SwordClient: Bible passage lookup from local SWORD modules
- SefariaClient: Sefaria API access with aggressive local caching
- ParsedReference: Structured scripture reference
- parse_reference: Parse human-readable references
- find_references: Extract references from text
"""

from .storage import ReferenceStorage
from .sword_manager import (
    SwordManager,
    SwordModuleError,
    ModuleNotFoundError,
    DownloadError,
    ExtractionError,
)
from .sword_client import SwordClient
from .sefaria_client import (
    SefariaClient,
    SefariaError,
    SefariaNetworkError,
)
from .reference_parser import (
    ParsedReference,
    ReferenceParseError,
    parse_reference,
    find_references,
    normalize_book_name,
    is_valid_reference,
    to_sefaria_format,
    to_osis_format,
    BOOK_NAMES,
    BOOK_TO_OSIS,
)
from .reference_service import (
    ReferenceService,
    Reference,
)

__all__ = [
    # Unified Service (primary interface)
    "ReferenceService",
    "Reference",
    # Storage
    "ReferenceStorage",
    # SWORD
    "SwordManager",
    "SwordModuleError",
    "ModuleNotFoundError",
    "DownloadError",
    "ExtractionError",
    "SwordClient",
    # Sefaria
    "SefariaClient",
    "SefariaError",
    "SefariaNetworkError",
    # Reference parsing
    "ParsedReference",
    "ReferenceParseError",
    "parse_reference",
    "find_references",
    "normalize_book_name",
    "is_valid_reference",
    "to_sefaria_format",
    "to_osis_format",
    "BOOK_NAMES",
    "BOOK_TO_OSIS",
]
