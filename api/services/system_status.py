"""
System Status Service

Phase 8.4: Reports system state for UI indicators.
"""

import os
from dataclasses import dataclass, asdict
from typing import Optional
from pathlib import Path


@dataclass
class SystemStatus:
    """Current system status."""
    # Network
    online: bool = True  # Assume online unless proven otherwise

    # Library
    library_mounted: bool = False
    library_path: Optional[str] = None
    library_file_count: int = 0

    # LLM
    llm_available: bool = True
    llm_provider: str = "unknown"

    # Voice
    voice_available: bool = True  # Frontend determines this

    # References
    sword_available: bool = False
    sword_module_count: int = 0
    sefaria_cached: bool = False

    # Embeddings
    embeddings_available: bool = True


def get_system_status() -> SystemStatus:
    """Get current system status."""
    status = SystemStatus()

    # Check library mount
    try:
        from services.library.storage_service import LibraryStorageService
        storage = LibraryStorageService()
        mount_path = storage.get_mount_path()
        status.library_path = str(mount_path)
        status.library_mounted = mount_path.exists() and mount_path.is_dir()

        if status.library_mounted:
            from services.library.library_service import LibraryService
            lib = LibraryService()
            stats = lib.get_stats()
            status.library_file_count = stats.get('file_count', 0)
    except Exception:
        pass

    # Check LLM
    try:
        from services.llm_service import get_llm_provider
        status.llm_provider = get_llm_provider()
        status.llm_available = True
    except Exception:
        status.llm_available = False

    # Check SWORD
    try:
        from services.references.sword_client import SwordClient
        client = SwordClient()
        modules = client.list_modules()
        status.sword_available = len(modules) > 0
        status.sword_module_count = len(modules)
    except Exception:
        pass

    # Check Sefaria cache
    try:
        from services.references.sefaria_client import SefariaClient
        client = SefariaClient()
        cache_stats = client.get_cache_stats()
        status.sefaria_cached = cache_stats.get('total_items', 0) > 0
    except Exception:
        pass

    # Check embeddings
    try:
        from services.embedding_service import get_embedding_model
        get_embedding_model()
        status.embeddings_available = True
    except Exception:
        status.embeddings_available = False

    return status


def get_status_dict() -> dict:
    """Get status as dictionary for JSON response."""
    return asdict(get_system_status())
