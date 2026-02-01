#!/usr/bin/env python3
"""
Internet Archive Harvester for Tamor Corpus.

Downloads public domain materials and tracks provenance in SQLite.
Integrates with Tamor's library system via ia_import_service.

Usage:
    python ia_harvester.py "subject:(federalist papers) AND date:[1780 TO 1927]"
    python ia_harvester.py --sample-queries
    python ia_harvester.py --import-to-library  # Import downloaded items to Tamor
"""

import argparse
import hashlib
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

try:
    import internetarchive as ia
except ImportError:
    print("Install with: pip install internetarchive")
    sys.exit(1)


# === Configuration ===

# NAS mount path for downloads
DEFAULT_DOWNLOAD_DIR = Path("/mnt/library/internet_archive")

# Use Tamor's database for unified management
DEFAULT_DB = Path(__file__).parent.parent / "memory" / "tamor.db"

# Subjects useful for founding era and theological research
SAMPLE_QUERIES = [
    # Founding era US history
    "subject:(united states constitution) AND date:[1780 TO 1927]",
    "subject:(federalist papers) AND date:[1780 TO 1927]",
    "subject:(constitutional convention) AND date:[1780 TO 1927]",
    "subject:(american revolution) AND date:[1780 TO 1927]",
    "subject:(founding fathers) AND date:[1780 TO 1927]",
    "subject:(declaration of independence) AND date:[1780 TO 1927]",
    # Theological scholarship
    "subject:(biblical commentary) AND date:[1500 TO 1927]",
    "subject:(church history) AND date:[1500 TO 1927]",
    "subject:(theology) AND date:[1500 TO 1927]",
    "subject:(reformation) AND date:[1500 TO 1927]",
]


# === Database Setup ===

def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize SQLite database with provenance tracking table."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ia_items (
            id INTEGER PRIMARY KEY,
            identifier TEXT UNIQUE NOT NULL,
            title TEXT,
            creator TEXT,
            date TEXT,
            subject TEXT,
            description TEXT,
            collection TEXT,
            mediatype TEXT,
            source_url TEXT,
            download_date TEXT,
            local_path TEXT,
            file_format TEXT,
            file_size INTEGER,
            sha256 TEXT,
            public_domain INTEGER DEFAULT 1,
            imported_to_library INTEGER DEFAULT 0,
            library_file_id INTEGER,
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ia_identifier ON ia_items(identifier)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ia_imported ON ia_items(imported_to_library)
    """)
    conn.commit()
    return conn


# === Search Functions ===

def search_archive(query: str, max_results: int = 100) -> list:
    """
    Search Internet Archive and return item metadata.

    Args:
        query: IA advanced search query
        max_results: Maximum items to return

    Returns:
        List of item metadata dicts
    """
    print(f"Searching: {query}")
    results = []

    search = ia.search_items(query)

    for i, result in enumerate(search):
        if i >= max_results:
            break
        results.append(result)

    print(f"Found {len(results)} items")
    return results


def flatten_field(value) -> str:
    """Flatten a metadata field to a string, handling nested lists."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        # Flatten nested lists and join
        flat = []
        for item in value:
            if isinstance(item, list):
                flat.extend(str(i) for i in item)
            else:
                flat.append(str(item))
        return "; ".join(flat)
    return str(value)


def get_item_metadata(identifier: str) -> dict:
    """Fetch full metadata for an item."""
    item = ia.get_item(identifier)
    metadata = item.metadata

    # Flatten all potentially list fields
    subject = flatten_field(metadata.get("subject"))
    collection = flatten_field(metadata.get("collection"))
    creator = flatten_field(metadata.get("creator"))
    title = flatten_field(metadata.get("title"))
    date = flatten_field(metadata.get("date"))
    mediatype = flatten_field(metadata.get("mediatype"))

    # Truncate description
    description = flatten_field(metadata.get("description"))
    if len(description) > 2000:
        description = description[:2000] + "..."

    return {
        "identifier": identifier,
        "title": title,
        "creator": creator,
        "date": date,
        "subject": subject,
        "description": description,
        "collection": collection,
        "mediatype": mediatype,
        "source_url": f"https://archive.org/details/{identifier}",
    }


# === Download Functions ===

def download_item(
    identifier: str,
    download_dir: Path,
    formats: list = None,
    metadata: dict = None,
    clean_filenames: bool = True,
) -> list:
    """
    Download files for an item.

    Args:
        identifier: IA item identifier
        download_dir: Base directory for downloads
        formats: List of formats to download (e.g., ['PDF', 'EPUB'])
                 If None, downloads PDF only
        metadata: Item metadata (used for clean filenames)
        clean_filenames: If True, rename to "{Author} - {Title}.ext"

    Returns:
        List of downloaded file info dicts
    """
    if formats is None:
        formats = ["PDF"]

    item_dir = download_dir / identifier
    item_dir.mkdir(parents=True, exist_ok=True)

    downloaded = []

    try:
        item = ia.get_item(identifier)

        for file_info in item.files:
            file_format = file_info.get("format", "")

            # Check if this format is wanted
            if not any(fmt.upper() in file_format.upper() for fmt in formats):
                continue

            filename = file_info.get("name", "")
            if not filename:
                continue

            local_path = item_dir / filename

            # Determine final path (possibly renamed)
            if clean_filenames and metadata:
                ext = Path(filename).suffix.lstrip(".")
                clean_name = clean_filename(metadata, ext)
                final_path = item_dir / clean_name
            else:
                final_path = local_path

            # Skip if already downloaded (check both original and clean name)
            if final_path.exists():
                print(f"  Already exists: {final_path.name}")
                downloaded.append({
                    "path": final_path,
                    "format": file_format,
                    "size": final_path.stat().st_size
                })
                continue

            if local_path.exists() and local_path != final_path:
                # Original exists, just rename
                local_path.rename(final_path)
                print(f"  Renamed: {filename} -> {final_path.name}")
                downloaded.append({
                    "path": final_path,
                    "format": file_format,
                    "size": final_path.stat().st_size
                })
                continue

            print(f"  Downloading: {filename}")

            try:
                ia.download(
                    identifier,
                    files=[filename],
                    destdir=str(download_dir),
                    no_directory=False,
                    retries=3
                )

                if local_path.exists():
                    # Rename if clean filenames enabled
                    if clean_filenames and metadata and local_path != final_path:
                        local_path.rename(final_path)
                        print(f"  Renamed: {filename} -> {final_path.name}")

                    downloaded.append({
                        "path": final_path,
                        "format": file_format,
                        "size": final_path.stat().st_size
                    })
            except Exception as e:
                print(f"  Error downloading {filename}: {e}")

    except Exception as e:
        print(f"Error accessing item {identifier}: {e}")

    return downloaded


def compute_sha256(filepath: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def clean_filename(metadata: dict, extension: str) -> str:
    """
    Build a clean filename from metadata.

    Format: "{Author} - {Title}.{ext}" or "{Title}.{ext}" if no author.
    Falls back to identifier if no title.

    Args:
        metadata: Item metadata dict with title, creator, identifier
        extension: File extension (e.g., "pdf")

    Returns:
        Cleaned filename string
    """
    title = metadata.get("title", "").strip()
    creator = metadata.get("creator", "").strip()
    identifier = metadata.get("identifier", "unknown")

    # Fall back to identifier if no title
    if not title:
        return f"{identifier}.{extension}"

    # Clean up title
    # Remove subtitle after colon if title is very long
    if len(title) > 80 and ":" in title:
        title = title.split(":")[0].strip()

    # Truncate if still too long
    if len(title) > 100:
        title = title[:100].rsplit(" ", 1)[0] + "..."

    # Clean up creator
    if creator:
        # Handle multiple authors - take first or shorten
        if ";" in creator:
            creators = [c.strip() for c in creator.split(";")]
            if len(creators) > 2:
                creator = f"{creators[0]} et al."
            else:
                creator = " & ".join(creators)

        # Truncate long author names
        if len(creator) > 50:
            creator = creator[:50].rsplit(" ", 1)[0]

    # Remove characters invalid for filenames
    def sanitize(s):
        # Replace problematic characters
        s = re.sub(r'[<>:"/\\|?*]', "", s)
        # Replace multiple spaces with single
        s = re.sub(r"\s+", " ", s)
        # Remove leading/trailing dots and spaces
        s = s.strip(". ")
        return s

    title = sanitize(title)
    creator = sanitize(creator)

    # Build filename
    if creator:
        filename = f"{creator} - {title}.{extension}"
    else:
        filename = f"{title}.{extension}"

    return filename


# === Database Operations ===

def item_exists(conn: sqlite3.Connection, identifier: str) -> bool:
    """Check if item already in database."""
    cursor = conn.execute(
        "SELECT 1 FROM ia_items WHERE identifier = ?",
        (identifier,)
    )
    return cursor.fetchone() is not None


def save_item(conn: sqlite3.Connection, metadata: dict, download_info: dict = None):
    """Save item metadata and download info to database."""
    local_path = None
    file_format = None
    file_size = None
    sha256_hash = None

    if download_info and download_info.get("path"):
        local_path = str(download_info["path"])
        file_format = download_info.get("format")
        file_size = download_info.get("size")
        sha256_hash = compute_sha256(download_info["path"])

    conn.execute("""
        INSERT OR REPLACE INTO ia_items
        (identifier, title, creator, date, subject, description, collection,
         mediatype, source_url, download_date, local_path, file_format,
         file_size, sha256, public_domain)
        VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        metadata["identifier"],
        metadata.get("title"),
        metadata.get("creator"),
        metadata.get("date"),
        metadata.get("subject"),
        metadata.get("description"),
        metadata.get("collection"),
        metadata.get("mediatype"),
        metadata.get("source_url"),
        datetime.now().isoformat(),
        local_path,
        file_format,
        file_size,
        sha256_hash,
    ))
    conn.commit()


# === Main Harvesting Function ===

def harvest(
    query: str,
    db_path: Path = DEFAULT_DB,
    download_dir: Path = DEFAULT_DOWNLOAD_DIR,
    max_results: int = 50,
    formats: list = None,
    download: bool = True,
    skip_existing: bool = True,
    clean_filenames: bool = True,
):
    """
    Main harvest function: search, download, and record provenance.

    Args:
        query: IA search query
        db_path: Path to SQLite database
        download_dir: Directory for downloaded files
        max_results: Maximum items to process
        formats: File formats to download
        download: Whether to download files (False = metadata only)
        skip_existing: Skip items already in database
        clean_filenames: Rename files to "{Author} - {Title}.ext"
    """
    conn = init_db(db_path)
    download_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print("Harvesting from Internet Archive")
    print(f"Query: {query}")
    print(f"Database: {db_path}")
    print(f"Download dir: {download_dir}")
    print(f"{'='*60}\n")

    # Search
    results = search_archive(query, max_results)

    processed = 0
    skipped = 0
    errors = 0

    for result in results:
        identifier = result.get("identifier")
        if not identifier:
            continue

        print(f"\nProcessing: {identifier}")

        # Skip if exists
        if skip_existing and item_exists(conn, identifier):
            print("  Skipping (already in database)")
            skipped += 1
            continue

        try:
            # Get full metadata
            metadata = get_item_metadata(identifier)
            title = metadata.get('title', 'Unknown')
            if len(title) > 60:
                title = title[:60] + "..."
            print(f"  Title: {title}")

            # Download if requested
            if download:
                downloaded = download_item(
                    identifier,
                    download_dir,
                    formats,
                    metadata=metadata,
                    clean_filenames=clean_filenames,
                )

                if downloaded:
                    # Save with first downloaded file info
                    save_item(conn, metadata, downloaded[0])
                    processed += 1
                else:
                    # Save metadata only
                    save_item(conn, metadata)
                    print("  No files downloaded (metadata only)")
            else:
                save_item(conn, metadata)
                processed += 1

        except Exception as e:
            print(f"  Error: {e}")
            errors += 1

    conn.close()

    print(f"\n{'='*60}")
    print("Harvest complete")
    print(f"Processed: {processed}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")
    print(f"{'='*60}\n")


def list_pending_imports(db_path: Path = DEFAULT_DB) -> list:
    """List items downloaded but not yet imported to library."""
    conn = init_db(db_path)
    cur = conn.execute("""
        SELECT identifier, title, local_path, file_size
        FROM ia_items
        WHERE local_path IS NOT NULL
          AND imported_to_library = 0
        ORDER BY download_date DESC
    """)
    items = [dict(row) for row in cur.fetchall()]
    conn.close()
    return items


def get_stats(db_path: Path = DEFAULT_DB) -> dict:
    """Get harvester statistics."""
    conn = init_db(db_path)

    cur = conn.execute("SELECT COUNT(*) FROM ia_items")
    total = cur.fetchone()[0]

    cur = conn.execute("SELECT COUNT(*) FROM ia_items WHERE local_path IS NOT NULL")
    downloaded = cur.fetchone()[0]

    cur = conn.execute("SELECT COUNT(*) FROM ia_items WHERE imported_to_library = 1")
    imported = cur.fetchone()[0]

    cur = conn.execute("SELECT SUM(file_size) FROM ia_items WHERE local_path IS NOT NULL")
    total_bytes = cur.fetchone()[0] or 0

    conn.close()

    return {
        "total_items": total,
        "downloaded": downloaded,
        "imported_to_library": imported,
        "pending_import": downloaded - imported,
        "total_size_mb": round(total_bytes / (1024 * 1024), 2),
    }


# === CLI ===

def main():
    parser = argparse.ArgumentParser(
        description="Harvest public domain materials from Internet Archive"
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Search query (IA advanced search syntax)"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"SQLite database path (default: {DEFAULT_DB})"
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=DEFAULT_DOWNLOAD_DIR,
        help=f"Download directory (default: {DEFAULT_DOWNLOAD_DIR})"
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=50,
        help="Maximum items to process (default: 50)"
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["PDF"],
        help="File formats to download (default: PDF)"
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Collect metadata without downloading files"
    )
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Re-process items already in database"
    )
    parser.add_argument(
        "--no-clean-filenames",
        action="store_true",
        help="Keep original IA filenames (default: rename to 'Author - Title.ext')"
    )
    parser.add_argument(
        "--sample-queries",
        action="store_true",
        help="Show sample queries for research"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show harvester statistics"
    )
    parser.add_argument(
        "--pending",
        action="store_true",
        help="List items pending library import"
    )

    args = parser.parse_args()

    if args.sample_queries:
        print("Sample queries for research:\n")
        print("Founding Era US History:")
        for q in SAMPLE_QUERIES[:6]:
            print(f"  {q}\n")
        print("Theological Scholarship:")
        for q in SAMPLE_QUERIES[6:]:
            print(f"  {q}\n")
        return

    if args.stats:
        stats = get_stats(args.db)
        print("\nIA Harvester Statistics:")
        print(f"  Total items tracked: {stats['total_items']}")
        print(f"  Downloaded: {stats['downloaded']}")
        print(f"  Imported to library: {stats['imported_to_library']}")
        print(f"  Pending import: {stats['pending_import']}")
        print(f"  Total size: {stats['total_size_mb']} MB\n")
        return

    if args.pending:
        items = list_pending_imports(args.db)
        if not items:
            print("No items pending import.")
            return
        print(f"\n{len(items)} items pending library import:\n")
        for item in items[:20]:
            size_mb = (item['file_size'] or 0) / (1024 * 1024)
            print(f"  {item['identifier']}")
            print(f"    {item['title'][:60] if item['title'] else 'No title'}...")
            print(f"    {size_mb:.1f} MB\n")
        if len(items) > 20:
            print(f"  ... and {len(items) - 20} more")
        return

    if not args.query:
        parser.print_help()
        print("\n\nExample usage:")
        print('  python ia_harvester.py "subject:(federalist papers) AND date:[1780 TO 1927]"')
        print('  python ia_harvester.py --sample-queries')
        print('  python ia_harvester.py --stats')
        print('  python ia_harvester.py --pending')
        return

    harvest(
        query=args.query,
        db_path=args.db,
        download_dir=args.download_dir,
        max_results=args.max_results,
        formats=args.formats,
        download=not args.metadata_only,
        skip_existing=not args.include_existing,
        clean_filenames=not args.no_clean_filenames,
    )


if __name__ == "__main__":
    main()
