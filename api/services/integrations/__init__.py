"""
Integration Services

Phase 6.4: Plugin Framework Expansion

Services for integrating with external tools and libraries.
"""

from .zotero import ZoteroReader, ZoteroItem, get_zotero_reader

__all__ = ["ZoteroReader", "ZoteroItem", "get_zotero_reader"]
