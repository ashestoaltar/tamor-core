# api/services/references/reference_service.py
"""
Unified reference service combining SWORD and Sefaria sources.

Provides a single interface for looking up scripture passages from
multiple sources, comparing translations, and extracting references
from text.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from .sword_client import SwordClient
from .sefaria_client import SefariaClient, SefariaNetworkError
from .reference_parser import parse_reference, find_references, ParsedReference
from .storage import ReferenceStorage

logger = logging.getLogger(__name__)


@dataclass
class Reference:
    """
    A scripture reference with text from a specific source.

    Attributes:
        source: Source identifier ("sword" or "sefaria")
        ref_string: Normalized reference string (e.g., "Genesis 1:1-3")
        book: Book name
        chapter: Chapter number
        verse_start: Starting verse
        verse_end: Ending verse (None for single verse)
        text: The passage text (English)
        translation: Translation/version name (e.g., "KJV", "Sefaria English")
        hebrew: Hebrew text if available
        greek: Greek text if available
        cross_refs: List of cross-references
        is_cached: Whether this was served from cache
        commentary: Commentary dict if requested
        metadata: Additional source-specific metadata
    """
    source: str
    ref_string: str
    book: str
    chapter: int
    verse_start: int
    verse_end: Optional[int]
    text: str
    translation: str
    hebrew: Optional[str] = None
    greek: Optional[str] = None
    cross_refs: Optional[list] = None
    is_cached: bool = True
    commentary: Optional[dict] = None
    metadata: dict = field(default_factory=dict)

    @property
    def has_hebrew(self) -> bool:
        """Check if Hebrew text is available."""
        return bool(self.hebrew)

    @property
    def has_greek(self) -> bool:
        """Check if Greek text is available."""
        return bool(self.greek)

    @property
    def verse_range(self) -> str:
        """Return verse range string (e.g., '1-3' or '16')."""
        if self.verse_end and self.verse_end != self.verse_start:
            return f"{self.verse_start}-{self.verse_end}"
        return str(self.verse_start)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "source": self.source,
            "ref": self.ref_string,
            "book": self.book,
            "chapter": self.chapter,
            "verse_start": self.verse_start,
            "verse_end": self.verse_end,
            "text": self.text,
            "translation": self.translation,
            "hebrew": self.hebrew,
            "greek": self.greek,
            "cross_refs": self.cross_refs,
            "is_cached": self.is_cached,
            "commentary": self.commentary,
            "metadata": self.metadata,
        }


class ReferenceService:
    """
    Unified service for scripture reference lookup.

    Combines SWORD (local Bible modules) and Sefaria (Jewish texts API)
    into a single interface.

    Usage:
        service = ReferenceService()

        # Basic lookup
        refs = service.lookup("John 3:16")
        for ref in refs:
            print(f"{ref.translation}: {ref.text}")

        # Compare translations
        refs = service.compare("Romans 8:28", ["KJV", "WEB", "ASV"])

        # Get with commentary
        ref = service.get_with_commentary("Genesis 1:1")
        print(ref.commentary)

        # Find references in text
        found = service.detect_references("Read John 3:16 and Romans 8:28")
    """

    def __init__(self):
        self.sword = SwordClient()
        self.sefaria = SefariaClient()
        self.storage = ReferenceStorage()

    def lookup(
        self,
        ref: str,
        sources: list[str] = None,
        translations: list[str] = None,
        include_hebrew: bool = True,
    ) -> list[Reference]:
        """
        Look up a passage from one or more sources.

        Args:
            ref: Scripture reference (e.g., "Genesis 1:1-3", "John 3:16")
            sources: List of sources to query ("sword", "sefaria").
                    Defaults to both.
            translations: SWORD translations to use. Defaults to configured
                         default translation.
            include_hebrew: Include Hebrew text from Sefaria (default True)

        Returns:
            List of Reference objects from each source/translation

        Raises:
            ValueError: If reference cannot be parsed
        """
        parsed = parse_reference(ref)
        if not parsed:
            raise ValueError(f"Could not parse reference: {ref}")

        sources = sources or ["sword", "sefaria"]
        results = []

        # SWORD lookup
        if "sword" in sources:
            sword_translations = translations or [
                self.storage.get_config().get("default_translation", "KJV")
            ]
            for trans in sword_translations:
                if not self.sword.manager.is_installed(trans):
                    logger.debug(f"Translation {trans} not installed, skipping")
                    continue

                result = self.sword.get_passage(ref, trans)
                if result:
                    results.append(Reference(
                        source="sword",
                        ref_string=parsed.normalized,
                        book=parsed.book,
                        chapter=parsed.chapter,
                        verse_start=parsed.verse_start or 1,
                        verse_end=parsed.verse_end,
                        text=result["text"],
                        translation=trans,
                        is_cached=True,  # SWORD is always local
                        metadata={"module": trans},
                    ))

        # Sefaria lookup
        if "sefaria" in sources:
            try:
                result = self.sefaria.get_text(ref)
                if result:
                    results.append(Reference(
                        source="sefaria",
                        ref_string=parsed.normalized,
                        book=parsed.book,
                        chapter=parsed.chapter,
                        verse_start=parsed.verse_start or 1,
                        verse_end=parsed.verse_end,
                        text=result.get("text", ""),
                        translation="Sefaria English",
                        hebrew=result.get("he") if include_hebrew else None,
                        is_cached=result.get("_from_cache", False),
                        metadata={
                            "heRef": result.get("heRef", ""),
                            "categories": result.get("categories", []),
                        },
                    ))
            except SefariaNetworkError as e:
                logger.warning(f"Sefaria network error for {ref}: {e}")
            except Exception as e:
                logger.error(f"Sefaria error for {ref}: {e}")

        return results

    def lookup_one(
        self,
        ref: str,
        source: str = "sword",
        translation: str = None,
    ) -> Optional[Reference]:
        """
        Look up a single passage from one source.

        Convenience method for simple lookups.

        Args:
            ref: Scripture reference
            source: "sword" or "sefaria"
            translation: SWORD translation (ignored for sefaria)

        Returns:
            Reference object or None if not found
        """
        translations = [translation] if translation else None
        results = self.lookup(ref, sources=[source], translations=translations)
        return results[0] if results else None

    def compare(
        self,
        ref: str,
        translations: list[str],
        include_sefaria: bool = False,
    ) -> list[Reference]:
        """
        Compare multiple translations of the same passage.

        Args:
            ref: Scripture reference
            translations: List of SWORD translation codes (e.g., ["KJV", "WEB"])
            include_sefaria: Also include Sefaria English (default False)

        Returns:
            List of Reference objects, one per translation
        """
        sources = ["sword"]
        if include_sefaria:
            sources.append("sefaria")

        return self.lookup(ref, sources=sources, translations=translations)

    def search(
        self,
        query: str,
        sources: list[str] = None,
        max_results: int = 20,
    ) -> list[dict]:
        """
        Search for passages across sources.

        Currently only Sefaria supports search. SWORD search is limited.

        Args:
            query: Search terms
            sources: Sources to search (default: ["sefaria"])
            max_results: Maximum results to return

        Returns:
            List of search result dicts
        """
        sources = sources or ["sefaria"]
        results = []

        if "sefaria" in sources:
            try:
                sefaria_results = self.sefaria.search(query, size=max_results)
                for r in (sefaria_results or []):
                    r["source"] = "sefaria"
                    results.append(r)
            except SefariaNetworkError as e:
                logger.warning(f"Sefaria search error: {e}")

        if "sword" in sources:
            # SWORD search is basic - just note it's available
            sword_results = self.sword.search(query)
            for r in (sword_results or []):
                r["source"] = "sword"
                results.append(r)

        return results[:max_results]

    def get_with_commentary(
        self,
        ref: str,
        commentator: str = None,
    ) -> Optional[Reference]:
        """
        Get passage with linked commentary from Sefaria.

        Args:
            ref: Scripture reference
            commentator: Specific commentator (e.g., "Rashi", "Ibn Ezra")
                        If None, includes all available.

        Returns:
            Reference object with commentary field populated
        """
        parsed = parse_reference(ref)
        if not parsed:
            return None

        try:
            # Get main text
            result = self.sefaria.get_text(ref, with_commentary=True)
            if not result:
                return None

            # Get commentary if available
            commentary_data = None
            if commentator or result.get("commentary"):
                commentary_result = self.sefaria.get_commentary(ref, commentator)
                if commentary_result:
                    commentary_data = commentary_result.get("commentaries", [])

            return Reference(
                source="sefaria",
                ref_string=parsed.normalized,
                book=parsed.book,
                chapter=parsed.chapter,
                verse_start=parsed.verse_start or 1,
                verse_end=parsed.verse_end,
                text=result.get("text", ""),
                translation="Sefaria English",
                hebrew=result.get("he"),
                commentary={"commentaries": commentary_data} if commentary_data else None,
                is_cached=result.get("_from_cache", False),
            )

        except SefariaNetworkError as e:
            logger.warning(f"Sefaria network error: {e}")
            return None

    def get_cross_references(self, ref: str) -> list[dict]:
        """
        Get cross-references for a passage.

        Uses Sefaria links API.

        Args:
            ref: Scripture reference

        Returns:
            List of cross-reference dicts with ref, type, category
        """
        try:
            links = self.sefaria.get_links(ref)
            # Filter to just cross-references (not commentary)
            cross_refs = [
                link for link in links
                if link.get("type") not in ["commentary", "Commentary"]
            ]
            return cross_refs
        except SefariaNetworkError:
            return []

    def detect_references(self, text: str) -> list[ParsedReference]:
        """
        Find all scripture references in text.

        Args:
            text: Text to search for references

        Returns:
            List of ParsedReference objects found
        """
        return find_references(text)

    def lookup_detected(
        self,
        text: str,
        source: str = "sword",
        translation: str = None,
    ) -> list[Reference]:
        """
        Find references in text and look them all up.

        Args:
            text: Text containing references
            source: Source to use for lookup
            translation: Translation for SWORD

        Returns:
            List of Reference objects for each detected reference
        """
        detected = self.detect_references(text)
        results = []

        for parsed in detected:
            ref = self.lookup_one(
                parsed.normalized,
                source=source,
                translation=translation,
            )
            if ref:
                results.append(ref)

        return results

    def get_translations(self) -> list[dict]:
        """
        List all available translations.

        Returns:
            List of translation info dicts with code, name, source
        """
        translations = []

        # SWORD translations
        sword_trans = self.sword.list_translations()
        for t in sword_trans:
            translations.append({
                "code": t["code"],
                "name": t["name"],
                "language": t.get("language", "en"),
                "source": "sword",
                "installed": True,
            })

        # Available but not installed
        available = self.sword.manager.list_available()
        installed_codes = {t["code"] for t in sword_trans}
        for mod in available:
            if mod["code"] not in installed_codes:
                translations.append({
                    "code": mod["code"],
                    "name": mod["name"],
                    "language": mod.get("language", "en"),
                    "source": "sword",
                    "installed": False,
                })

        # Sefaria is always available (network permitting)
        translations.append({
            "code": "sefaria",
            "name": "Sefaria (English + Hebrew)",
            "language": "en,he",
            "source": "sefaria",
            "installed": True,  # Always "installed" as API
        })

        return translations

    def get_book_info(self, book: str, translation: str = None) -> Optional[dict]:
        """
        Get information about a book (chapters, verse counts).

        Args:
            book: Book name
            translation: SWORD translation to use

        Returns:
            Dict with name, num_chapters, chapter_lengths
        """
        return self.sword.get_book_info(book, translation)

    def cache_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with sefaria cache stats
        """
        return {
            "sefaria": self.sefaria.cache_stats(),
        }

    def clear_cache(self, older_than_days: int = None) -> dict:
        """
        Clear cached data.

        Args:
            older_than_days: Only clear items older than this

        Returns:
            Dict with number of items cleared per source
        """
        return {
            "sefaria": self.sefaria.clear_cache(older_than_days),
        }
