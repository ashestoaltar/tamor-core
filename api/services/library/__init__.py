# api/services/library/__init__.py

"""
Library services package.

Provides centralized management for the global library system.
"""

from .chunk_service import LibraryChunkService
from .context_service import ContextChunk, LibraryContextService
from .index_queue_service import LibraryIndexQueueService
from .ingest_service import IngestProgress, LibraryIngestService
from .library_service import LibraryService
from .reference_service import LibraryReferenceService
from .scanner_service import LibraryScannerService, ScannedFile
from .search_service import LibrarySearchService, SearchResult
from .settings_service import LibrarySettingsService
from .storage_service import LibraryStorageService
from .text_service import LibraryTextService
from .transcription_service import TranscriptionQueueService, WHISPER_MODELS, TRANSCRIBABLE_TYPES

__all__ = [
    "LibraryStorageService",
    "LibraryService",
    "LibraryReferenceService",
    "LibraryTextService",
    "LibraryChunkService",
    "LibraryScannerService",
    "ScannedFile",
    "LibraryIngestService",
    "IngestProgress",
    "LibraryIndexQueueService",
    "LibrarySearchService",
    "SearchResult",
    "LibraryContextService",
    "ContextChunk",
    "LibrarySettingsService",
    "TranscriptionQueueService",
    "WHISPER_MODELS",
    "TRANSCRIBABLE_TYPES",
]
