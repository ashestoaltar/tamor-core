"""
Anchor Service

Phase 8.2: Attempts to attach supporting evidence to claims.

Strategy: "Anchor, don't hedge"
- If we can find supporting text quickly, attach it
- If not, flag for minimal rewrite
- Never auto-insert generic hedges
"""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from .config_loader import get_anchor_settings


@dataclass
class Anchor:
    """A piece of supporting evidence."""
    source: str           # e.g., "library", "reference", "context"
    source_id: str        # File ID, reference ID, etc.
    source_name: str      # Human-readable name
    content: str          # The actual text
    relevance: float      # 0.0 to 1.0
    page: Optional[int] = None
    verse: Optional[str] = None


@dataclass
class AnchorResult:
    """Result of anchor search."""
    found: bool
    anchors: List[Anchor] = field(default_factory=list)
    search_time_ms: int = 0
    sources_checked: List[str] = field(default_factory=list)
    budget_exceeded: bool = False


class AnchorService:
    """
    Searches for supporting evidence within time budget.

    Source priority:
    1. Session context (already retrieved)
    2. Library cache (indexed chunks)
    3. Reference cache (SWORD/Sefaria)
    """

    def __init__(self):
        self._settings = get_anchor_settings()
        self._session_context: Dict[str, Any] = {}

    def set_session_context(self, context: Dict[str, Any]):
        """Set context from current session (already retrieved sources)."""
        self._session_context = context

    def find_anchors(
        self,
        claim: str,
        deep_search: bool = False,
        max_anchors: int = 3
    ) -> AnchorResult:
        """
        Search for supporting evidence for a claim.

        Args:
            claim: The text claim to support
            deep_search: Use extended time budget
            max_anchors: Maximum anchors to return

        Returns:
            AnchorResult with any found anchors
        """
        budget_ms = (
            self._settings.get('deep_budget_ms', 800) if deep_search
            else self._settings.get('fast_budget_ms', 250)
        )

        start_time = time.time()
        anchors = []
        sources_checked = []

        # Check each source in priority order
        source_order = self._settings.get('sources', [
            'session_context', 'library_cache', 'reference_cache'
        ])

        for source in source_order:
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms >= budget_ms:
                break

            sources_checked.append(source)
            remaining_ms = budget_ms - elapsed_ms

            if source == 'session_context':
                found = self._search_session_context(claim, remaining_ms)
            elif source == 'library_cache':
                found = self._search_library_cache(claim, remaining_ms)
            elif source == 'reference_cache':
                found = self._search_reference_cache(claim, remaining_ms)
            else:
                found = []

            anchors.extend(found)

            if len(anchors) >= max_anchors:
                break

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Sort by relevance and limit
        anchors.sort(key=lambda a: a.relevance, reverse=True)
        anchors = anchors[:max_anchors]

        return AnchorResult(
            found=len(anchors) > 0,
            anchors=anchors,
            search_time_ms=elapsed_ms,
            sources_checked=sources_checked,
            budget_exceeded=elapsed_ms >= budget_ms and len(anchors) == 0
        )

    def _search_session_context(
        self,
        claim: str,
        budget_ms: float
    ) -> List[Anchor]:
        """Search already-retrieved session context."""
        anchors = []

        # Check library context
        library_context = self._session_context.get('library_chunks', [])
        for chunk in library_context:
            if self._is_relevant(claim, chunk.get('content', '')):
                anchors.append(Anchor(
                    source='session_context',
                    source_id=str(chunk.get('library_file_id', '')),
                    source_name=chunk.get('filename', 'Unknown'),
                    content=chunk.get('content', '')[:500],
                    relevance=chunk.get('score', 0.5),
                    page=chunk.get('page')
                ))

        # Check reference context
        reference_context = self._session_context.get('references', [])
        for ref in reference_context:
            if self._is_relevant(claim, ref.get('text', '')):
                anchors.append(Anchor(
                    source='session_context',
                    source_id=ref.get('reference', ''),
                    source_name=ref.get('reference', 'Scripture'),
                    content=ref.get('text', '')[:500],
                    relevance=0.8,
                    verse=ref.get('reference')
                ))

        return anchors

    def _search_library_cache(
        self,
        claim: str,
        budget_ms: float
    ) -> List[Anchor]:
        """Search library chunk cache (fast, pre-embedded)."""
        anchors = []

        try:
            # Import here to avoid circular dependency
            from services.library.search_service import LibrarySearchService

            search_service = LibrarySearchService()

            # Quick search with low threshold
            results = search_service.search(
                query=claim,
                scope='library',
                limit=3,
                min_score=0.3
            )

            for result in results.get('results', []):
                anchors.append(Anchor(
                    source='library_cache',
                    source_id=str(result.get('library_file_id', '')),
                    source_name=result.get('filename', 'Unknown'),
                    content=result.get('content', '')[:500],
                    relevance=result.get('score', 0.5),
                    page=result.get('page')
                ))
        except Exception:
            # Fail silently - anchor search is best-effort
            pass

        return anchors

    def _search_reference_cache(
        self,
        claim: str,
        budget_ms: float
    ) -> List[Anchor]:
        """Search SWORD/Sefaria cache."""
        anchors = []

        try:
            # Extract potential scripture references from claim
            from services.references.reference_parser import ReferenceParser

            parser = ReferenceParser()
            refs = parser.find_references(claim)

            if refs:
                from services.references.reference_service import ReferenceService
                ref_service = ReferenceService()

                for ref in refs[:2]:  # Limit to 2
                    result = ref_service.lookup(ref['reference'])
                    if result and result.get('text'):
                        anchors.append(Anchor(
                            source='reference_cache',
                            source_id=ref['reference'],
                            source_name=ref['reference'],
                            content=result['text'][:500],
                            relevance=0.9,
                            verse=ref['reference']
                        ))
        except Exception:
            # Fail silently
            pass

        return anchors

    def _is_relevant(self, claim: str, content: str) -> bool:
        """Quick relevance check (keyword overlap)."""
        if not claim or not content:
            return False

        # Simple word overlap check
        claim_words = set(claim.lower().split())
        content_words = set(content.lower().split())

        # Remove common words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                      'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                      'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                      'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
                      'it', 'we', 'they', 'what', 'which', 'who', 'whom', 'whose',
                      'where', 'when', 'why', 'how', 'and', 'or', 'but', 'if',
                      'then', 'so', 'than', 'too', 'very', 'just', 'only', 'own',
                      'same', 'as', 'of', 'at', 'by', 'for', 'with', 'about',
                      'to', 'from', 'in', 'on', 'not', 'no'}

        claim_words -= stop_words
        content_words -= stop_words

        if not claim_words:
            return False

        overlap = len(claim_words & content_words)
        return overlap >= 2 or (overlap >= 1 and len(claim_words) <= 3)


# Singleton
_anchor_service = None


def get_anchor_service() -> AnchorService:
    """Get or create singleton anchor service."""
    global _anchor_service
    if _anchor_service is None:
        _anchor_service = AnchorService()
    return _anchor_service


def find_anchors(
    claim: str,
    deep_search: bool = False,
    max_anchors: int = 3
) -> AnchorResult:
    """Convenience function for anchor search."""
    return get_anchor_service().find_anchors(claim, deep_search, max_anchors)


def set_session_context(context: Dict[str, Any]):
    """Set session context for anchor searches."""
    get_anchor_service().set_session_context(context)
