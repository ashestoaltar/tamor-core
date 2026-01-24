# api/services/references/__init__.py
"""
Reference storage and retrieval services for Tamor.

This package provides:
- ReferenceStorage: Directory structure and configuration management
- SWORD module support (future)
- Sefaria API caching (future)
"""

from .storage import ReferenceStorage

__all__ = ["ReferenceStorage"]
