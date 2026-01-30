"""
Zotero Integration

Phase 6.4: Plugin Framework Expansion

Reads from local Zotero SQLite database and imports references.
Supports reading collections, items, and PDF attachments.
"""

import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ZoteroItem:
    """A Zotero library item."""

    key: str
    item_type: str
    title: str
    creators: List[Dict[str, str]] = field(default_factory=list)
    date: Optional[str] = None
    abstract: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    attachments: List[Dict[str, str]] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)


class ZoteroReader:
    """
    Reads from local Zotero SQLite database.

    Default Zotero data location:
    - Linux: ~/.zotero/zotero/
    - macOS: ~/Library/Application Support/Zotero/
    - Windows: C:/Users/<user>/Zotero/

    The actual database is in a profile folder like: abc123.default/zotero.sqlite
    """

    def __init__(self, zotero_data_path: Optional[str] = None):
        self.data_path = zotero_data_path or self._find_zotero_path()
        self.db_path = self._find_database()
        self.storage_path = os.path.join(os.path.dirname(self.db_path), "storage")

    def _find_zotero_path(self) -> str:
        """Find Zotero data directory."""
        home = Path.home()

        # Try common locations
        candidates = [
            home / ".zotero" / "zotero",  # Linux
            home / "Zotero",  # Common custom location
            home / "Library" / "Application Support" / "Zotero",  # macOS
            home / "snap" / "zotero-snap" / "common" / "Zotero",  # Snap package
        ]

        for path in candidates:
            if path.exists():
                return str(path)

        raise FileNotFoundError(
            "Could not find Zotero data directory. "
            "Please specify the path manually or install Zotero."
        )

    def _find_database(self) -> str:
        """Find zotero.sqlite in data path."""
        data_path = Path(self.data_path)

        # Look for profile directories
        for profile_dir in data_path.iterdir():
            if profile_dir.is_dir():
                db_path = profile_dir / "zotero.sqlite"
                if db_path.exists():
                    return str(db_path)

        # Direct path
        direct_db = data_path / "zotero.sqlite"
        if direct_db.exists():
            return str(direct_db)

        raise FileNotFoundError(f"Could not find zotero.sqlite in {self.data_path}")

    def _connect(self) -> sqlite3.Connection:
        """Connect to Zotero database (read-only)."""
        # Connect in read-only mode to avoid locking issues
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def get_collections(self) -> List[Dict[str, Any]]:
        """Get all collections."""
        conn = self._connect()
        try:
            results = conn.execute(
                """
                SELECT collectionID, collectionName, parentCollectionID
                FROM collections
                ORDER BY collectionName
                """
            ).fetchall()

            return [dict(r) for r in results]
        finally:
            conn.close()

    def get_items(
        self,
        collection_id: Optional[int] = None,
        item_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[ZoteroItem]:
        """Get items, optionally filtered by collection or type."""
        conn = self._connect()
        try:
            # Base query for items
            query = """
                SELECT i.itemID, i.key, it.typeName,
                       MAX(CASE WHEN f.fieldName = 'title' THEN iv.value END) as title,
                       MAX(CASE WHEN f.fieldName = 'date' THEN iv.value END) as date,
                       MAX(CASE WHEN f.fieldName = 'abstractNote' THEN iv.value END) as abstract,
                       MAX(CASE WHEN f.fieldName = 'url' THEN iv.value END) as url,
                       MAX(CASE WHEN f.fieldName = 'DOI' THEN iv.value END) as doi
                FROM items i
                JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
                LEFT JOIN itemData id ON i.itemID = id.itemID
                LEFT JOIN itemDataValues iv ON id.valueID = iv.valueID
                LEFT JOIN fields f ON id.fieldID = f.fieldID
            """

            conditions = ["it.typeName != 'attachment'", "it.typeName != 'note'"]
            params: List[Any] = []

            if collection_id:
                query += " JOIN collectionItems ci ON i.itemID = ci.itemID"
                conditions.append("ci.collectionID = ?")
                params.append(collection_id)

            if item_type:
                conditions.append("it.typeName = ?")
                params.append(item_type)

            query += " WHERE " + " AND ".join(conditions)
            query += " GROUP BY i.itemID"
            query += f" LIMIT {limit}"

            results = conn.execute(query, params).fetchall()

            items = []
            for row in results:
                # Get creators
                creators = self._get_item_creators(conn, row["itemID"])

                # Get tags
                tags = self._get_item_tags(conn, row["itemID"])

                # Get attachments
                attachments = self._get_item_attachments(conn, row["itemID"])

                items.append(
                    ZoteroItem(
                        key=row["key"],
                        item_type=row["typeName"],
                        title=row["title"] or "Untitled",
                        creators=creators,
                        date=row["date"],
                        abstract=row["abstract"],
                        url=row["url"],
                        doi=row["doi"],
                        tags=tags,
                        attachments=attachments,
                        raw_data=dict(row),
                    )
                )

            return items
        finally:
            conn.close()

    def _get_item_creators(self, conn, item_id: int) -> List[Dict[str, str]]:
        """Get creators for an item."""
        results = conn.execute(
            """
            SELECT c.firstName, c.lastName, ct.creatorType
            FROM itemCreators ic
            JOIN creators c ON ic.creatorID = c.creatorID
            JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
            WHERE ic.itemID = ?
            ORDER BY ic.orderIndex
            """,
            (item_id,),
        ).fetchall()

        return [
            {
                "firstName": r["firstName"] or "",
                "lastName": r["lastName"] or "",
                "type": r["creatorType"],
            }
            for r in results
        ]

    def _get_item_tags(self, conn, item_id: int) -> List[str]:
        """Get tags for an item."""
        results = conn.execute(
            """
            SELECT t.name
            FROM itemTags it
            JOIN tags t ON it.tagID = t.tagID
            WHERE it.itemID = ?
            """,
            (item_id,),
        ).fetchall()

        return [r["name"] for r in results]

    def _get_item_attachments(self, conn, item_id: int) -> List[Dict[str, str]]:
        """Get attachments for an item."""
        results = conn.execute(
            """
            SELECT i.key, ia.contentType, ia.path
            FROM itemAttachments ia
            JOIN items i ON ia.itemID = i.itemID
            WHERE ia.parentItemID = ?
            """,
            (item_id,),
        ).fetchall()

        attachments = []
        for r in results:
            att: Dict[str, Any] = {
                "key": r["key"],
                "content_type": r["contentType"],
                "path": r["path"],
            }

            # Resolve full path if it's a stored file
            if r["path"] and r["path"].startswith("storage:"):
                filename = r["path"].replace("storage:", "")
                full_path = os.path.join(self.storage_path, r["key"], filename)
                if os.path.exists(full_path):
                    att["full_path"] = full_path

            attachments.append(att)

        return attachments

    def get_item_by_key(self, key: str) -> Optional[ZoteroItem]:
        """Get a single item by its key."""
        items = self.get_items(limit=10000)  # Search all items
        for item in items:
            if item.key == key:
                return item
        return None

    def get_pdf_path(self, item: ZoteroItem) -> Optional[str]:
        """Get path to PDF attachment if available."""
        for att in item.attachments:
            if att.get("content_type") == "application/pdf":
                return att.get("full_path")
        return None

    def format_citation(self, item: ZoteroItem, style: str = "apa") -> str:
        """Format a basic citation for an item."""
        # Simple APA-ish format
        authors = []
        for c in item.creators:
            if c["type"] == "author":
                if c["lastName"]:
                    name = c["lastName"]
                    if c["firstName"]:
                        name += f", {c['firstName'][0]}."
                    authors.append(name)

        author_str = ", ".join(authors) if authors else "Unknown"
        year = f"({item.date[:4]})" if item.date else "(n.d.)"
        title = item.title

        citation = f"{author_str} {year}. {title}."

        if item.doi:
            citation += f" https://doi.org/{item.doi}"
        elif item.url:
            citation += f" {item.url}"

        return citation

    def search_items(self, query: str, limit: int = 50) -> List[ZoteroItem]:
        """Search items by title or abstract."""
        all_items = self.get_items(limit=10000)
        query_lower = query.lower()

        matches = []
        for item in all_items:
            title_match = query_lower in (item.title or "").lower()
            abstract_match = query_lower in (item.abstract or "").lower()
            tag_match = any(query_lower in tag.lower() for tag in item.tags)

            if title_match or abstract_match or tag_match:
                matches.append(item)
                if len(matches) >= limit:
                    break

        return matches


def get_zotero_reader(data_path: Optional[str] = None) -> ZoteroReader:
    """Create a Zotero reader instance."""
    return ZoteroReader(data_path)


def check_zotero_available(data_path: Optional[str] = None) -> Dict[str, Any]:
    """Check if Zotero is available without raising exceptions."""
    try:
        reader = get_zotero_reader(data_path)
        return {
            "available": True,
            "db_path": reader.db_path,
            "storage_path": reader.storage_path,
        }
    except FileNotFoundError as e:
        return {
            "available": False,
            "error": str(e),
        }
