# api/services/library/__init__.py

"""
Library services package.

Provides centralized management for the global library system.
"""

from .storage_service import LibraryStorageService

# LibraryService will be added in next step
# from .library_service import LibraryService

__all__ = ["LibraryStorageService"]
