"""
Reference Cache

Phase 6.4: Plugin Framework Expansion

Caches external content (web pages, API responses, etc.) with version tracking.
Useful for Sefaria, web references, and other external sources.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReferenceCache:
    """Caches external references with versioning."""

    def __init__(self, db):
        self.db = db

    def _hash_content(self, content: str) -> str:
        """Generate content hash."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get(self, url: str) -> Optional[Dict[str, Any]]:
        """Get cached content for URL (latest version)."""
        cur = self.db.cursor()
        cur.execute(
            """SELECT * FROM reference_cache
               WHERE url = ?
               ORDER BY version DESC
               LIMIT 1""",
            (url,),
        )
        result = cur.fetchone()

        if result:
            return {
                "id": result[0],
                "url": result[1],
                "content_hash": result[2],
                "content": result[3],
                "content_type": result[4],
                "fetched_at": result[5],
                "expires_at": result[6],
                "version": result[7],
                "metadata": json.loads(result[8]) if result[8] else {},
            }
        return None

    def get_if_fresh(
        self, url: str, max_age_hours: int = 24
    ) -> Optional[Dict[str, Any]]:
        """Get cached content only if not expired."""
        cached = self.get(url)

        if not cached:
            return None

        fetched_str = cached["fetched_at"]
        if fetched_str:
            try:
                # Handle both ISO format and SQLite timestamp format
                if "T" in fetched_str:
                    fetched = datetime.fromisoformat(fetched_str.replace("Z", "+00:00"))
                else:
                    fetched = datetime.strptime(fetched_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                fetched = datetime.now()

            age = datetime.now() - fetched

            if age > timedelta(hours=max_age_hours):
                return None

        return cached

    def put(
        self,
        url: str,
        content: str,
        content_type: str = "text/html",
        metadata: Optional[Dict[str, Any]] = None,
        ttl_hours: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Cache content, creating new version if changed."""
        content_hash = self._hash_content(content)
        cur = self.db.cursor()

        # Check if we already have this exact content
        cur.execute(
            "SELECT id, url, content_hash, version, fetched_at FROM reference_cache WHERE url = ? AND content_hash = ?",
            (url, content_hash),
        )
        existing = cur.fetchone()

        if existing:
            # Content unchanged, just update fetched_at
            cur.execute(
                "UPDATE reference_cache SET fetched_at = ? WHERE id = ?",
                (datetime.now().isoformat(), existing[0]),
            )
            self.db.commit()
            return {
                "id": existing[0],
                "url": existing[1],
                "content_hash": existing[2],
                "version": existing[3],
                "fetched_at": datetime.now().isoformat(),
                "updated": True,
            }

        # Get current max version for this URL
        cur.execute(
            "SELECT MAX(version) FROM reference_cache WHERE url = ?",
            (url,),
        )
        max_version_row = cur.fetchone()
        new_version = (max_version_row[0] or 0) + 1

        # Calculate expiry
        expires_at = None
        if ttl_hours:
            expires_at = (datetime.now() + timedelta(hours=ttl_hours)).isoformat()

        # Insert new version
        cur.execute(
            """INSERT INTO reference_cache
               (url, content_hash, content, content_type, version, expires_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                url,
                content_hash,
                content,
                content_type,
                new_version,
                expires_at,
                json.dumps(metadata or {}),
            ),
        )
        self.db.commit()

        logger.info(f"Cached {url} (version {new_version}, {len(content)} bytes)")

        return {
            "id": cur.lastrowid,
            "url": url,
            "content_hash": content_hash,
            "version": new_version,
            "fetched_at": datetime.now().isoformat(),
            "created": True,
        }

    def get_versions(self, url: str) -> List[Dict[str, Any]]:
        """Get all cached versions for a URL."""
        cur = self.db.cursor()
        cur.execute(
            """SELECT id, url, content_hash, version, fetched_at,
                      LENGTH(content) as content_length
               FROM reference_cache
               WHERE url = ?
               ORDER BY version DESC""",
            (url,),
        )
        results = cur.fetchall()

        return [
            {
                "id": r[0],
                "url": r[1],
                "content_hash": r[2],
                "version": r[3],
                "fetched_at": r[4],
                "content_length": r[5],
            }
            for r in results
        ]

    def get_version(self, url: str, version: int) -> Optional[Dict[str, Any]]:
        """Get specific version of cached content."""
        cur = self.db.cursor()
        cur.execute(
            "SELECT * FROM reference_cache WHERE url = ? AND version = ?",
            (url, version),
        )
        result = cur.fetchone()

        if result:
            return {
                "id": result[0],
                "url": result[1],
                "content_hash": result[2],
                "content": result[3],
                "content_type": result[4],
                "fetched_at": result[5],
                "expires_at": result[6],
                "version": result[7],
                "metadata": json.loads(result[8]) if result[8] else {},
            }
        return None

    def delete_old_versions(self, url: str, keep_versions: int = 3) -> int:
        """Delete old versions, keeping the N most recent."""
        cur = self.db.cursor()

        # Get versions to keep
        cur.execute(
            """SELECT id FROM reference_cache
               WHERE url = ?
               ORDER BY version DESC
               LIMIT ?""",
            (url, keep_versions),
        )
        keep_rows = cur.fetchall()
        keep_ids = [r[0] for r in keep_rows]

        if not keep_ids:
            return 0

        # Delete others
        placeholders = ",".join("?" * len(keep_ids))
        cur.execute(
            f"""DELETE FROM reference_cache
                WHERE url = ? AND id NOT IN ({placeholders})""",
            (url, *keep_ids),
        )
        deleted = cur.rowcount
        self.db.commit()

        if deleted > 0:
            logger.info(f"Deleted {deleted} old versions for {url}")

        return deleted

    def cleanup_expired(self) -> int:
        """Remove all expired cache entries."""
        cur = self.db.cursor()
        cur.execute(
            "DELETE FROM reference_cache WHERE expires_at IS NOT NULL AND expires_at < ?",
            (datetime.now().isoformat(),),
        )
        deleted = cur.rowcount
        self.db.commit()

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} expired cache entries")

        return deleted

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        cur = self.db.cursor()

        cur.execute("SELECT COUNT(*) FROM reference_cache")
        total_entries = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT url) FROM reference_cache")
        unique_urls = cur.fetchone()[0]

        cur.execute("SELECT SUM(LENGTH(content)) FROM reference_cache")
        total_bytes = cur.fetchone()[0] or 0

        cur.execute(
            "SELECT COUNT(*) FROM reference_cache WHERE expires_at IS NOT NULL AND expires_at < ?",
            (datetime.now().isoformat(),),
        )
        expired = cur.fetchone()[0]

        return {
            "total_entries": total_entries,
            "unique_urls": unique_urls,
            "total_bytes": total_bytes,
            "expired_entries": expired,
        }


# Singleton helper
_cache_instances: Dict[int, ReferenceCache] = {}


def get_reference_cache(db) -> ReferenceCache:
    """Get or create reference cache for database connection."""
    # Use db object id as key since we can't hash the connection
    db_id = id(db)
    if db_id not in _cache_instances:
        _cache_instances[db_id] = ReferenceCache(db)
    return _cache_instances[db_id]
