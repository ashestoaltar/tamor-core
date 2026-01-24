# api/services/references/sword_client.py
"""
Client for reading Bible passages from local SWORD modules.

Uses pysword to read installed modules and provides a simple API
for passage lookup with human-readable references.
"""

import logging
from typing import Optional

from .storage import ReferenceStorage
from .sword_manager import SwordManager
from .reference_parser import (
    parse_reference as _parse_ref,
    normalize_book_name,
    BOOK_NAMES,
)

logger = logging.getLogger(__name__)


# Re-export for backwards compatibility
def parse_reference(ref: str) -> dict:
    """
    Parse a human-readable Bible reference.

    This is a compatibility wrapper around reference_parser.parse_reference
    that returns a dict instead of ParsedReference.
    """
    parsed = _parse_ref(ref)
    if parsed is None:
        return None
    return {
        "book": parsed.book,
        "chapter": parsed.chapter,
        "verse_start": parsed.verse_start,
        "verse_end": parsed.verse_end,
    }


# Keep BOOK_ALIASES as alias to BOOK_NAMES for backwards compatibility
BOOK_ALIASES = BOOK_NAMES


class SwordClient:
    """
    Client for reading Bible passages from local SWORD modules.

    Usage:
        client = SwordClient()

        # Get a passage
        result = client.get_passage("John 3:16")
        print(result["text"])

        # Get with specific translation
        result = client.get_passage("Genesis 1:1-3", translation="KJV")

        # Compare translations
        results = client.compare_translations("Romans 8:28", ["KJV", "WEB"])
    """

    def __init__(self):
        self.storage = ReferenceStorage()
        self.manager = SwordManager()
        self._modules = None
        self._bibles = {}  # Cache loaded bible objects

    def _load_modules(self):
        """Load SWORD modules from disk."""
        if self._modules is None:
            try:
                from pysword.modules import SwordModules
                sword_path = str(self.storage.sword_path)
                self._modules = SwordModules(sword_path)
                self._modules.parse_modules()
            except ImportError:
                logger.error("pysword not installed")
                raise RuntimeError("pysword not installed")
            except Exception as e:
                logger.error(f"Failed to load SWORD modules: {e}")
                raise
        return self._modules

    def _get_bible(self, translation: str):
        """Get a cached bible object for a translation."""
        translation = translation.upper()

        if translation not in self._bibles:
            modules = self._load_modules()
            try:
                self._bibles[translation] = modules.get_bible_from_module(translation)
            except Exception as e:
                logger.error(f"Failed to get bible for {translation}: {e}")
                raise ValueError(f"Cannot load translation: {translation}")

        return self._bibles[translation]

    def get_passage(self, ref: str, translation: str = None) -> Optional[dict]:
        """
        Get a passage from a local SWORD module.

        Args:
            ref: Human-readable reference like "Genesis 1:1-3" or "John 3:16"
            translation: Module code like "KJV", "WEB". Uses default if None.

        Returns:
            {
                "ref": "Genesis 1:1-3",
                "book": "Genesis",
                "chapter": 1,
                "verse_start": 1,
                "verse_end": 3,
                "text": "In the beginning...",
                "translation": "KJV",
                "source": "sword"
            }
            or None if translation not installed
        """
        if translation is None:
            translation = self.storage.get_config().get("default_translation", "KJV")

        translation = translation.upper()

        if not self.manager.is_installed(translation):
            logger.warning(f"Translation {translation} not installed")
            return None

        # Parse the reference
        try:
            parsed = parse_reference(ref)
        except ReferenceParseError as e:
            logger.error(f"Failed to parse reference: {e}")
            return None

        # Get the bible module
        try:
            bible = self._get_bible(translation)
        except (RuntimeError, ValueError) as e:
            logger.error(f"Failed to get bible: {e}")
            return None

        # Build verse list
        if parsed["verse_start"] is None:
            # Whole chapter - don't specify verses
            verses = None
        elif parsed["verse_end"] is None:
            # Single verse
            verses = [parsed["verse_start"]]
        else:
            # Verse range
            verses = list(range(parsed["verse_start"], parsed["verse_end"] + 1))

        # Get the text
        try:
            if verses:
                text = bible.get(
                    books=[parsed["book"]],
                    chapters=[parsed["chapter"]],
                    verses=verses
                )
            else:
                text = bible.get(
                    books=[parsed["book"]],
                    chapters=[parsed["chapter"]]
                )
        except Exception as e:
            logger.error(f"Failed to get passage: {e}")
            return None

        # Clean up text (remove extra whitespace)
        if text:
            text = text.strip()

        return {
            "ref": ref,
            "book": parsed["book"],
            "chapter": parsed["chapter"],
            "verse_start": parsed["verse_start"],
            "verse_end": parsed["verse_end"],
            "text": text,
            "translation": translation,
            "source": "sword",
        }

    def get_chapter(self, book: str, chapter: int, translation: str = None) -> Optional[dict]:
        """
        Get a full chapter.

        Args:
            book: Book name (e.g., "Genesis", "John")
            chapter: Chapter number
            translation: Module code. Uses default if None.

        Returns:
            Same format as get_passage
        """
        ref = f"{book} {chapter}"
        return self.get_passage(ref, translation)

    def get_verse(self, book: str, chapter: int, verse: int, translation: str = None) -> Optional[dict]:
        """
        Get a single verse.

        Args:
            book: Book name
            chapter: Chapter number
            verse: Verse number
            translation: Module code. Uses default if None.

        Returns:
            Same format as get_passage
        """
        ref = f"{book} {chapter}:{verse}"
        return self.get_passage(ref, translation)

    def compare_translations(self, ref: str, translations: list[str] = None) -> list[dict]:
        """
        Get the same passage from multiple translations.

        Args:
            ref: Bible reference
            translations: List of module codes. If None, uses all installed.

        Returns:
            List of passage dicts from each translation
        """
        if translations is None:
            translations = self.manager.list_installed()

        results = []
        for trans in translations:
            result = self.get_passage(ref, trans)
            if result:
                results.append(result)

        return results

    def list_translations(self) -> list[dict]:
        """
        List available (installed) translations.

        Returns:
            List of dicts with code, name, installed status
        """
        installed = self.manager.list_installed()
        available = self.manager.list_available()

        # Build result with full info for installed modules
        results = []
        for mod in available:
            if mod["code"] in installed:
                results.append({
                    "code": mod["code"],
                    "name": mod["name"],
                    "language": mod.get("language", "en"),
                    "description": mod.get("description", ""),
                    "source": "sword",
                    "installed": True,
                })

        return results

    def get_book_info(self, book: str, translation: str = None) -> Optional[dict]:
        """
        Get information about a book (chapter count, etc.).

        Args:
            book: Book name
            translation: Module code. Uses default if None.

        Returns:
            {
                "name": "Genesis",
                "num_chapters": 50,
                "chapter_lengths": [31, 25, ...],
            }
        """
        if translation is None:
            translation = self.storage.get_config().get("default_translation", "KJV")

        translation = translation.upper()

        if not self.manager.is_installed(translation):
            return None

        try:
            bible = self._get_bible(translation)
            structure = bible.get_structure()

            # Normalize book name
            book_key = book.lower().strip()
            if book_key in BOOK_ALIASES:
                book = BOOK_ALIASES[book_key]

            testament, book_struct = structure.find_book(book)

            return {
                "name": book_struct.name,
                "osis_name": book_struct.osis_name,
                "num_chapters": book_struct.num_chapters,
                "chapter_lengths": book_struct.chapter_lengths,
                "testament": testament,
            }
        except Exception as e:
            logger.error(f"Failed to get book info: {e}")
            return None

    def search(self, query: str, translation: str = None, max_results: int = 50) -> list[dict]:
        """
        Basic keyword search within a module.

        Note: SWORD/pysword doesn't have built-in search, so this is a
        simple linear scan which may be slow for large texts.

        Args:
            query: Search terms
            translation: Module code. Uses default if None.
            max_results: Maximum results to return

        Returns:
            List of matching passages
        """
        if translation is None:
            translation = self.storage.get_config().get("default_translation", "KJV")

        translation = translation.upper()

        if not self.manager.is_installed(translation):
            return []

        try:
            bible = self._get_bible(translation)
            structure = bible.get_structure()
        except Exception as e:
            logger.error(f"Failed to load bible for search: {e}")
            return []

        results = []
        query_lower = query.lower()

        # Search through all books
        for testament in ["ot", "nt"]:
            try:
                # Get books from this testament
                text = bible.get(books=[testament])
                if not text:
                    continue

                # This is a very basic search - we get all text and search
                # A proper implementation would iterate verse by verse
                if query_lower in text.lower():
                    # Found a match somewhere in this testament
                    # For now, just indicate it was found
                    results.append({
                        "testament": testament,
                        "query": query,
                        "found": True,
                        "translation": translation,
                        "source": "sword",
                        "note": "Full verse-level search not yet implemented",
                    })

            except Exception as e:
                logger.debug(f"Search error in {testament}: {e}")
                continue

            if len(results) >= max_results:
                break

        return results
