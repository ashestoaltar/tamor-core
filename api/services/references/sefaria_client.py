# api/services/references/sefaria_client.py
"""
Sefaria API client with aggressive local file caching.

Provides access to Jewish texts (Torah, Talmud, Midrash, etc.) with
offline-first behavior. All API responses are cached to disk and
served from cache when available.
"""

import os
import json
import hashlib
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

from .storage import ReferenceStorage

logger = logging.getLogger(__name__)


class SefariaError(Exception):
    """Base exception for Sefaria client errors."""
    pass


class SefariaNetworkError(SefariaError):
    """Raised when network request fails and no cache available."""
    pass


class SefariaClient:
    """
    Client for the Sefaria API with aggressive local caching.

    All API responses are cached to disk. On cache hit, no network
    request is made. On network failure, expired cache is served
    with a warning flag.

    Usage:
        client = SefariaClient()

        # Get a text (cached)
        result = client.get_text("Genesis 1:1-3")
        print(result["text"])

        # Check if from cache
        if result.get("_from_cache"):
            print("Served from cache")

        # Get Hebrew text
        print(result["he"])
    """

    def __init__(self):
        self.storage = ReferenceStorage()
        self.base_url = os.getenv("SEFARIA_BASE_URL", "https://www.sefaria.org/api")
        self.cache_ttl_days = int(os.getenv("SEFARIA_CACHE_TTL_DAYS", "30"))
        self._request_timeout = 15  # seconds

    def _cache_path(self, cache_type: str, key: str) -> Path:
        """
        Generate cache file path for a request.

        Args:
            cache_type: Category (texts, search, commentary)
            key: Unique key for this request

        Returns:
            Path to cache file
        """
        # Hash the key to create safe filename
        key_hash = hashlib.md5(key.encode()).hexdigest()[:16]
        # Create readable prefix from key
        safe_key = "".join(c if c.isalnum() else "_" for c in key)[:50]
        filename = f"{safe_key}_{key_hash}.json"

        cache_dir = self.storage.sefaria_cache_path / cache_type
        cache_dir.mkdir(parents=True, exist_ok=True)

        return cache_dir / filename

    def _get_cached(self, cache_type: str, key: str) -> Optional[dict]:
        """
        Get from cache if exists and not expired.

        Args:
            cache_type: Category (texts, search, commentary)
            key: Cache key

        Returns:
            Cached data or None if not found/expired
        """
        cache_file = self._cache_path(cache_type, key)
        if not cache_file.exists():
            return None

        try:
            with open(cache_file) as f:
                cached = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read cache file {cache_file}: {e}")
            return None

        # Check expiration
        try:
            cached_at = datetime.fromisoformat(cached["_cached_at"])
            if datetime.now() - cached_at > timedelta(days=self.cache_ttl_days):
                logger.debug(f"Cache expired for {key}")
                return None
        except (KeyError, ValueError):
            return None

        return cached.get("data")

    def _get_cached_expired(self, cache_type: str, key: str) -> Optional[dict]:
        """
        Get from cache even if expired (for offline fallback).

        Args:
            cache_type: Category
            key: Cache key

        Returns:
            Cached data regardless of expiration, or None
        """
        cache_file = self._cache_path(cache_type, key)
        if not cache_file.exists():
            return None

        try:
            with open(cache_file) as f:
                cached = json.load(f)
            return cached.get("data")
        except (json.JSONDecodeError, IOError):
            return None

    def _set_cache(self, cache_type: str, key: str, data: dict):
        """
        Store data in cache.

        Args:
            cache_type: Category
            key: Cache key
            data: Data to cache
        """
        cache_file = self._cache_path(cache_type, key)

        try:
            with open(cache_file, "w") as f:
                json.dump({
                    "_cached_at": datetime.now().isoformat(),
                    "_key": key,
                    "data": data,
                }, f, indent=2, ensure_ascii=False)
            logger.debug(f"Cached {key} to {cache_file}")
        except IOError as e:
            logger.warning(f"Failed to write cache file {cache_file}: {e}")

    def _to_sefaria_format(self, ref: str) -> str:
        """
        Convert human reference to Sefaria API format.

        "Genesis 1:1-3" -> "Genesis.1.1-3"
        "Bereshit 1:1" -> "Bereshit.1.1"
        """
        # Replace spaces with dots, colons with dots
        ref = ref.strip()

        # Handle chapter:verse format
        # "Genesis 1:1-3" -> "Genesis.1.1-3"
        ref = re.sub(r'\s+', '.', ref)
        ref = ref.replace(':', '.')

        return ref

    def _from_sefaria_format(self, ref: str) -> str:
        """
        Convert Sefaria format back to human-readable.

        "Genesis.1.1-3" -> "Genesis 1:1-3"
        """
        # This is approximate - Sefaria refs can be complex
        parts = ref.split('.')
        if len(parts) >= 2:
            book = parts[0]
            rest = '.'.join(parts[1:])
            # Convert first dot after book to space, remaining to colon
            if len(parts) == 2:
                return f"{book} {parts[1]}"
            elif len(parts) >= 3:
                return f"{book} {parts[1]}:{'.'.join(parts[2:])}"
        return ref

    def get_text(self, ref: str, with_commentary: bool = False) -> Optional[dict]:
        """
        Get a text passage from Sefaria.

        Args:
            ref: Reference like "Genesis 1:1-3" or Sefaria format "Genesis.1.1-3"
            with_commentary: Include linked commentary (larger response)

        Returns:
            {
                "ref": "Genesis 1:1-3",
                "text": "In the beginning...",
                "he": "בְּרֵאשִׁית...",
                "book": "Genesis",
                "sections": [1, 1],
                "toSections": [1, 3],
                "source": "sefaria",
                "_from_cache": True/False,
                "_cache_expired": True/False (if serving expired cache)
            }
            or None if not found
        """
        # Normalize to Sefaria format
        sefaria_ref = self._to_sefaria_format(ref)
        cache_key = f"text_{sefaria_ref}_comm{with_commentary}"

        # Check cache first
        cached = self._get_cached("texts", cache_key)
        if cached:
            cached["_from_cache"] = True
            cached["_cache_expired"] = False
            logger.debug(f"Cache hit for {ref}")
            return cached

        # Fetch from API
        url = f"{self.base_url}/texts/{sefaria_ref}"
        params = {"context": "0"}  # Don't include surrounding context
        if with_commentary:
            params["commentary"] = "1"

        try:
            logger.debug(f"Fetching {url}")
            response = requests.get(url, params=params, timeout=self._request_timeout)

            if response.status_code == 404:
                logger.info(f"Text not found: {ref}")
                return None

            response.raise_for_status()
            data = response.json()

        except requests.RequestException as e:
            logger.warning(f"Network error fetching {ref}: {e}")

            # Try expired cache as fallback
            expired_cache = self._get_cached_expired("texts", cache_key)
            if expired_cache:
                expired_cache["_from_cache"] = True
                expired_cache["_cache_expired"] = True
                logger.info(f"Serving expired cache for {ref}")
                return expired_cache

            raise SefariaNetworkError(f"Network error and no cache available: {e}")

        # Process response
        result = {
            "ref": data.get("ref", ref),
            "heRef": data.get("heRef", ""),
            "text": self._normalize_text(data.get("text", "")),
            "he": self._normalize_text(data.get("he", "")),
            "book": data.get("book", ""),
            "categories": data.get("categories", []),
            "sections": data.get("sections", []),
            "toSections": data.get("toSections", []),
            "sectionNames": data.get("sectionNames", []),
            "source": "sefaria",
            "_from_cache": False,
            "_cache_expired": False,
        }

        # Include commentary if requested
        if with_commentary and "commentary" in data:
            result["commentary"] = data["commentary"]

        # Cache it
        self._set_cache("texts", cache_key, result)

        return result

    def _normalize_text(self, text) -> str:
        """
        Normalize text which may be a string or nested list.

        Sefaria returns text as either a string or list of strings/lists.
        """
        if isinstance(text, str):
            return text
        elif isinstance(text, list):
            # Flatten and join
            return "\n".join(self._flatten_text(text))
        return ""

    def _flatten_text(self, obj) -> list:
        """Recursively flatten nested lists of strings."""
        if isinstance(obj, str):
            return [obj] if obj.strip() else []
        elif isinstance(obj, list):
            result = []
            for item in obj:
                result.extend(self._flatten_text(item))
            return result
        return []

    def get_commentary(self, ref: str, commentator: str = None) -> Optional[dict]:
        """
        Get commentary on a passage.

        Args:
            ref: Reference to get commentary for
            commentator: Specific commentator (e.g., "Rashi", "Ibn Ezra")
                        If None, gets all available commentary.

        Returns:
            {
                "ref": "...",
                "commentaries": [
                    {"commentator": "Rashi", "text": "...", "he": "..."},
                    ...
                ],
                "_from_cache": True/False
            }
        """
        sefaria_ref = self._to_sefaria_format(ref)
        cache_key = f"commentary_{sefaria_ref}_{commentator or 'all'}"

        # Check cache
        cached = self._get_cached("commentary", cache_key)
        if cached:
            cached["_from_cache"] = True
            cached["_cache_expired"] = False
            return cached

        # Fetch links for this ref
        url = f"{self.base_url}/links/{sefaria_ref}"
        params = {}
        if commentator:
            params["with_text"] = "1"

        try:
            response = requests.get(url, params=params, timeout=self._request_timeout)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            links = response.json()

        except requests.RequestException as e:
            logger.warning(f"Network error fetching commentary for {ref}: {e}")

            expired_cache = self._get_cached_expired("commentary", cache_key)
            if expired_cache:
                expired_cache["_from_cache"] = True
                expired_cache["_cache_expired"] = True
                return expired_cache

            raise SefariaNetworkError(f"Network error and no cache: {e}")

        # Filter to commentary links
        commentaries = []
        for link in links:
            link_type = link.get("type", "")
            if "commentary" in link_type.lower() or link.get("category") == "Commentary":
                # Filter by commentator if specified
                if commentator and commentator.lower() not in link.get("collectiveTitle", "").lower():
                    continue

                commentaries.append({
                    "ref": link.get("ref", ""),
                    "commentator": link.get("collectiveTitle", ""),
                    "text": self._normalize_text(link.get("text", "")),
                    "he": self._normalize_text(link.get("he", "")),
                    "sourceRef": link.get("sourceRef", ""),
                })

        result = {
            "ref": ref,
            "commentaries": commentaries,
            "source": "sefaria",
            "_from_cache": False,
            "_cache_expired": False,
        }

        self._set_cache("commentary", cache_key, result)
        return result

    def get_links(self, ref: str) -> list:
        """
        Get cross-references and related texts for a passage.

        Args:
            ref: Reference to get links for

        Returns:
            List of link objects with ref, type, category
        """
        sefaria_ref = self._to_sefaria_format(ref)
        cache_key = f"links_{sefaria_ref}"

        cached = self._get_cached("texts", cache_key)
        if cached:
            return cached

        url = f"{self.base_url}/links/{sefaria_ref}"

        try:
            response = requests.get(url, timeout=self._request_timeout)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            links = response.json()

        except requests.RequestException as e:
            logger.warning(f"Network error fetching links for {ref}: {e}")

            expired_cache = self._get_cached_expired("texts", cache_key)
            if expired_cache:
                return expired_cache

            raise SefariaNetworkError(f"Network error and no cache: {e}")

        # Process links
        result = []
        for link in links:
            result.append({
                "ref": link.get("ref", ""),
                "type": link.get("type", ""),
                "category": link.get("category", ""),
                "collectiveTitle": link.get("collectiveTitle", ""),
            })

        self._set_cache("texts", cache_key, result)
        return result

    def search(self, query: str, filters: dict = None, size: int = 20) -> list:
        """
        Search across Sefaria texts.

        Note: Sefaria's search API may have rate limits or require
        specific access. Consider using get_text() with known references
        for more reliable results.

        Args:
            query: Search terms
            filters: Optional filters like {"categories": ["Torah"]}
            size: Maximum results to return

        Returns:
            List of search results with ref, text preview, score
        """
        filters = filters or {}
        cache_key = f"search_{query}_{json.dumps(filters, sort_keys=True)}_{size}"

        cached = self._get_cached("search", cache_key)
        if cached:
            return cached

        # Use the name API for finding texts by name/query
        # The search-wrapper endpoint may have access restrictions
        url = f"{self.base_url}/name/{query}"
        params = {"limit": size}

        try:
            response = requests.get(url, params=params, timeout=self._request_timeout)
            if response.status_code in (403, 429):
                logger.warning(f"Search API rate limited or forbidden")
                return []
            response.raise_for_status()
            data = response.json()

        except requests.RequestException as e:
            logger.warning(f"Network error searching: {e}")

            expired_cache = self._get_cached_expired("search", cache_key)
            if expired_cache:
                return expired_cache

            # Don't raise for search - just return empty
            return []

        # Process results from name API
        results = []
        completions = data.get("completions", [])
        for completion in completions[:size]:
            results.append({
                "ref": completion,
                "heRef": "",
                "text": "",
                "categories": "",
                "score": 0,
                "type": "name_match",
            })

        self._set_cache("search", cache_key, results)
        return results

    def get_index(self, title: str) -> Optional[dict]:
        """
        Get the index (table of contents) for a text.

        Args:
            title: Book title (e.g., "Genesis", "Talmud Berakhot")

        Returns:
            Index structure with chapters, sections, etc.
        """
        cache_key = f"index_{title}"

        cached = self._get_cached("texts", cache_key)
        if cached:
            return cached

        url = f"{self.base_url}/index/{title}"

        try:
            response = requests.get(url, timeout=self._request_timeout)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()

        except requests.RequestException as e:
            logger.warning(f"Network error fetching index for {title}: {e}")

            expired_cache = self._get_cached_expired("texts", cache_key)
            if expired_cache:
                return expired_cache

            return None

        self._set_cache("texts", cache_key, data)
        return data

    def clear_cache(self, older_than_days: int = None):
        """
        Clear cached files.

        Args:
            older_than_days: If specified, only clear files older than this.
                            If None, clears all cached files.
        """
        cache_base = self.storage.sefaria_cache_path
        now = datetime.now()
        cleared = 0

        for cache_type in ["texts", "search", "commentary"]:
            cache_dir = cache_base / cache_type
            if not cache_dir.exists():
                continue

            for cache_file in cache_dir.glob("*.json"):
                should_delete = True

                if older_than_days is not None:
                    try:
                        with open(cache_file) as f:
                            cached = json.load(f)
                        cached_at = datetime.fromisoformat(cached["_cached_at"])
                        age_days = (now - cached_at).days
                        should_delete = age_days > older_than_days
                    except (json.JSONDecodeError, KeyError, IOError):
                        should_delete = True  # Delete corrupt files

                if should_delete:
                    cache_file.unlink()
                    cleared += 1

        logger.info(f"Cleared {cleared} cache files")
        return cleared

    def cache_stats(self) -> dict:
        """
        Return cache statistics.

        Returns:
            {
                "total_files": 123,
                "total_size_bytes": 456789,
                "total_size_mb": 0.44,
                "by_type": {
                    "texts": {"files": 100, "size_bytes": 300000},
                    "search": {"files": 20, "size_bytes": 150000},
                    "commentary": {"files": 3, "size_bytes": 6789},
                }
            }
        """
        cache_base = self.storage.sefaria_cache_path
        stats = {
            "total_files": 0,
            "total_size_bytes": 0,
            "by_type": {},
        }

        for cache_type in ["texts", "search", "commentary"]:
            cache_dir = cache_base / cache_type
            type_stats = {"files": 0, "size_bytes": 0}

            if cache_dir.exists():
                for cache_file in cache_dir.glob("*.json"):
                    type_stats["files"] += 1
                    type_stats["size_bytes"] += cache_file.stat().st_size

            stats["by_type"][cache_type] = type_stats
            stats["total_files"] += type_stats["files"]
            stats["total_size_bytes"] += type_stats["size_bytes"]

        stats["total_size_mb"] = round(stats["total_size_bytes"] / (1024 * 1024), 2)

        return stats

    def prefetch_book(self, book: str, chapters: list[int] = None) -> int:
        """
        Prefetch and cache chapters from a book.

        Useful for offline preparation.

        Args:
            book: Book name (e.g., "Genesis")
            chapters: Specific chapters to fetch. If None, fetches all.

        Returns:
            Number of chapters cached
        """
        # Get index to find chapter count
        index = self.get_index(book)
        if not index:
            logger.warning(f"Could not get index for {book}")
            return 0

        # Determine chapters to fetch
        if chapters is None:
            # Try to determine chapter count from index
            schema = index.get("schema", {})
            if "lengths" in schema:
                chapters = list(range(1, schema["lengths"][0] + 1))
            else:
                # Default to first 50 chapters
                chapters = list(range(1, 51))

        cached_count = 0
        for chapter in chapters:
            ref = f"{book} {chapter}"
            try:
                result = self.get_text(ref)
                if result:
                    cached_count += 1
                    logger.debug(f"Prefetched {ref}")
            except SefariaNetworkError:
                logger.warning(f"Failed to prefetch {ref}")
                break

        logger.info(f"Prefetched {cached_count} chapters of {book}")
        return cached_count
