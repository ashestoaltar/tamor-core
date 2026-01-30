"""
Cache Services

Phase 6.4: Plugin Framework Expansion

Services for caching external content with version tracking.
"""

from .reference_cache import ReferenceCache, get_reference_cache

__all__ = ["ReferenceCache", "get_reference_cache"]
