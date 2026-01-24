# api/services/references/__init__.py
"""
Reference storage and retrieval services for Tamor.

This package provides:
- ReferenceStorage: Directory structure and configuration management
- SwordManager: SWORD Bible module download and management
- Sefaria API caching (future)
"""

from .storage import ReferenceStorage
from .sword_manager import (
    SwordManager,
    SwordModuleError,
    ModuleNotFoundError,
    DownloadError,
    ExtractionError,
)

__all__ = [
    "ReferenceStorage",
    "SwordManager",
    "SwordModuleError",
    "ModuleNotFoundError",
    "DownloadError",
    "ExtractionError",
]
