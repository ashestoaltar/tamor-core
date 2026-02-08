#!/usr/bin/env python3
"""
Founders Online harvester — founders.archives.gov

Downloads ~184,000 documents from the National Archives' Founders Online collection.
Professionally transcribed writings of seven Founding Fathers: Washington, Adams
(+ John Quincy), Franklin, Hamilton, Jay, Jefferson, Madison.

Two-phase approach:
  1. Download the metadata index (54MB JSON file, one HTTP request)
  2. Fetch full text for each document via the official API

Output: raw JSON per document in /mnt/library/harvest/raw/founders-online/{Project}/
conforming to the harvest metadata schema for process_raw.py pipeline.

Usage:
    # Phase 1: Discover (download + parse metadata index)
    python3 founders_online.py --discover

    # Phase 2: Download all
    python3 founders_online.py --download --all
    python3 founders_online.py --download --all --resume

    # Download one Founder
    python3 founders_online.py --download --project Washington
    python3 founders_online.py --download --project Adams --resume

    # Preview
    python3 founders_online.py --download --all --dry-run

    # Retry failures
    python3 founders_online.py --download --all --resume --retry-failed

Runs on: scraper machine or Tamor
Output: /mnt/library/harvest/raw/founders-online/{Project}/*.json
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HARVEST_BASE = "/mnt/library/harvest"
RAW_DIR = os.path.join(HARVEST_BASE, "raw", "founders-online")
CONFIG_DIR = os.path.join(HARVEST_BASE, "config")
MANIFEST_PATH = os.path.join(CONFIG_DIR, "founders-online-manifest.json")
LOG_PATH = os.path.join(CONFIG_DIR, "founders-online-download-log.json")

BASE_URL = "https://founders.archives.gov"
METADATA_URL = f"{BASE_URL}/Metadata/founders-online-metadata.json"
API_URL = f"{BASE_URL}/API/docdata"

# Respectful rate limiting — their docs say max 10 req/sec.
# Default 5/sec to be a good citizen. ~10 hours for full corpus.
REQUESTS_PER_SECOND = 5
REQUEST_DELAY = 1.0 / REQUESTS_PER_SECOND

MAX_RETRIES = 3
RETRY_BACKOFF = 5  # seconds, doubles each retry

HEADERS = {
    "User-Agent": "TamorHarvest/1.0 (personal research library)",
}

VALID_PROJECTS = {
    "Adams", "Franklin", "Hamilton", "Jay",
    "Jefferson", "Madison", "Washington",
}

SOURCE_NAME = "Founders Online"
THEOLOGICAL_STREAM = "founding-era"
COLLECTION_NAME = "Founders Online"

CHECKPOINT_INTERVAL = 100  # save progress every N documents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_url(url: str, retries: int = MAX_RETRIES) -> bytes:
    """Fetch URL with retry logic."""
    req = Request(url, headers=HEADERS)
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=60) as resp:
                return resp.read()
        except (HTTPError, URLError, TimeoutError) as e:
            wait = RETRY_BACKOFF * (2 ** attempt)
            if attempt < retries - 1:
                log.warning(f"Request failed ({e}), retrying in {wait}s... [{attempt+1}/{retries}]")
                time.sleep(wait)
            else:
                raise


def extract_doc_id(permalink: str) -> str:
    """Extract API document identifier from permalink.

    'https://founders.archives.gov/documents/Washington/05-04-02-0361'
    → 'Washington/05-04-02-0361'
    """
    marker = "/documents/"
    idx = permalink.find(marker)
    if idx >= 0:
        return permalink[idx + len(marker):]
    raise ValueError(f"Cannot extract doc ID from permalink: {permalink}")


def extract_project(doc_id: str) -> str:
    """'Washington/05-04-02-0361' → 'Washington'"""
    return doc_id.split("/")[0]


def load_download_log(path: str) -> dict:
    """Load or initialize download progress log."""
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {
        "started": datetime.now(timezone.utc).isoformat(),
        "completed_ids": [],
        "failed_ids": [],
        "total_documents": 0,
        "total_fetched": 0,
        "total_bytes": 0,
        "last_updated": None,
    }


def save_download_log(path: str, dl_log: dict):
    """Save download progress atomically."""
    dl_log["last_updated"] = datetime.now(timezone.utc).isoformat()
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(dl_log, f, indent=2)
    os.replace(tmp, path)


def format_authors(authors: list) -> str:
    """Join author list for metadata. 'Washington, George' → 'George Washington'."""
    result = []
    for a in authors:
        parts = [p.strip() for p in a.split(",", 1)]
        if len(parts) == 2:
            result.append(f"{parts[1]} {parts[0]}")
        else:
            result.append(a)
    return "; ".join(result) if result else ""


# ---------------------------------------------------------------------------
# Phase 1: Discover (metadata index)
# ---------------------------------------------------------------------------

def do_discover():
    """Download metadata index, parse, build manifest."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    meta_dir = os.path.join(CONFIG_DIR, "founders-online-metadata")
    os.makedirs(meta_dir, exist_ok=True)
    meta_file = os.path.join(meta_dir, "founders-online-metadata.json")

    # Download metadata index
    if os.path.exists(meta_file):
        size_mb = os.path.getsize(meta_file) / 1e6
        log.info(f"Metadata file exists ({size_mb:.1f} MB), loading...")
    else:
        log.info(f"Downloading metadata index from {METADATA_URL}...")
        data = fetch_url(METADATA_URL)
        with open(meta_file, "wb") as f:
            f.write(data)
        log.info(f"Downloaded {len(data) / 1e6:.1f} MB")

    log.info("Parsing metadata...")
    with open(meta_file) as f:
        documents = json.load(f)
    log.info(f"Total documents in index: {len(documents):,}")

    # Build manifest — filter editorial content (no date = editorial)
    manifest = []
    skipped_editorial = 0

    for doc in documents:
        if not doc.get("date-from"):
            skipped_editorial += 1
            continue

        try:
            doc_id = extract_doc_id(doc["permalink"])
        except (ValueError, KeyError) as e:
            log.warning(f"Skipping bad permalink: {e}")
            continue

        manifest.append({
            "doc_id": doc_id,
            "project": extract_project(doc_id),
            "title": doc.get("title", ""),
            "authors": doc.get("authors", []),
            "recipients": doc.get("recipients", []),
            "date_from": doc.get("date-from", ""),
            "date_to": doc.get("date-to", ""),
            "permalink": doc.get("permalink", ""),
        })

    log.info(f"Manifest: {len(manifest):,} primary documents")
    log.info(f"Skipped {skipped_editorial:,} editorial items (no date)")

    # Breakdown by project
    from collections import Counter
    counts = Counter(d["project"] for d in manifest)
    log.info("Documents by Founder:")
    for proj, count in sorted(counts.items()):
        log.info(f"  {proj}: {count:,}")

    # Save manifest
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    log.info(f"Manifest saved: {MANIFEST_PATH}")

    return manifest


# ---------------------------------------------------------------------------
# Phase 2: Download full text
# ---------------------------------------------------------------------------

def fetch_document(doc_id: str) -> dict | None:
    """Fetch a single document's full text from the API."""
    url = f"{API_URL}/{doc_id}"
    try:
        data = fetch_url(url)
        return json.loads(data)
    except HTTPError as e:
        if e.code == 404:
            log.warning(f"404: {doc_id}")
            return None
        raise
    except json.JSONDecodeError:
        log.warning(f"Invalid JSON: {doc_id}")
        return None


def build_raw_json(api_doc: dict, manifest_entry: dict) -> dict:
    """Convert API response to harvest raw JSON schema."""
    doc_id = manifest_entry["doc_id"]
    project = manifest_entry["project"]

    # Build filename: founders-online-{project}-{id_slug}.txt
    id_slug = doc_id.split("/", 1)[1] if "/" in doc_id else doc_id
    filename = f"founders-online-{project.lower()}-{id_slug}.txt"

    content = api_doc.get("content", "")
    title = api_doc.get("title", manifest_entry.get("title", ""))
    authors = api_doc.get("authors", manifest_entry.get("authors", []))
    recipients = api_doc.get("recipients", manifest_entry.get("recipients", []))
    date_from = api_doc.get("date-from", manifest_entry.get("date_from", ""))

    # Determine content_type from title heuristics
    title_lower = title.lower()
    if any(kw in title_lower for kw in ("diary", "journal")):
        content_type = "article"  # diary/journal entries
    elif any(kw in title_lower for kw in ("speech", "address", "inaugural")):
        content_type = "article"
    elif any(kw in title_lower for kw in ("order", "general orders")):
        content_type = "article"
    else:
        content_type = "article"  # letters are the bulk — all map to article

    author_str = format_authors(authors)
    recipient_str = format_authors(recipients)

    # Prepend header to content for better chunking context
    header_parts = [f"Title: {title}"]
    if author_str:
        header_parts.append(f"Author: {author_str}")
    if recipient_str:
        header_parts.append(f"Recipient: {recipient_str}")
    if date_from:
        header_parts.append(f"Date: {date_from}")
    header = "\n".join(header_parts)
    full_text = f"{header}\n\n{content}" if content else header

    word_count = len(full_text.split()) if full_text else 0

    return {
        "text": full_text,
        "filename": filename,
        "source_name": SOURCE_NAME,
        "teacher": author_str or project,
        "content_type": content_type,
        "url": manifest_entry.get("permalink", ""),
        "title": title,
        "date": date_from,
        "collection": COLLECTION_NAME,
        "series": f"{project} Papers",
        "topics": [],
        "copyright_note": "CC-BY-NC (UVA Press); underlying documents public domain",
        "metadata": {
            "theological_stream": THEOLOGICAL_STREAM,
            "language": "en",
            "original_format": "json-api",
            "word_count": word_count,
            "project": project,
            "authors": authors,
            "recipients": recipients,
            "date_from": date_from,
            "date_to": manifest_entry.get("date_to", ""),
            "doc_id": doc_id,
        },
    }


def do_download(project_filter=None, resume=False, retry_failed=False,
                dry_run=False, rate=REQUESTS_PER_SECOND):
    """Download full text for all documents in manifest."""
    global REQUEST_DELAY
    REQUEST_DELAY = 1.0 / min(rate, 10.0)

    # Load manifest
    if not os.path.exists(MANIFEST_PATH):
        log.error(f"Manifest not found: {MANIFEST_PATH}")
        log.error("Run --discover first.")
        sys.exit(1)

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    log.info(f"Loaded manifest: {len(manifest):,} documents")

    # Filter by project
    if project_filter:
        manifest = [d for d in manifest if d["project"] == project_filter]
        log.info(f"Filtered to {project_filter}: {len(manifest):,} documents")

    # Load download log
    dl_log = load_download_log(LOG_PATH)

    if retry_failed:
        n_failed = len(dl_log.get("failed_ids", []))
        log.info(f"Clearing {n_failed} failed IDs for retry")
        dl_log["failed_ids"] = []
        save_download_log(LOG_PATH, dl_log)

    completed = set(dl_log.get("completed_ids", []))
    failed = set(dl_log.get("failed_ids", []))

    if not resume and completed:
        log.warning(
            f"Existing log has {len(completed):,} completed documents. "
            f"Use --resume to continue, or delete {LOG_PATH} to start fresh."
        )
        return

    # Filter to what still needs fetching
    to_fetch = [d for d in manifest if d["doc_id"] not in completed]
    log.info(f"To fetch: {len(to_fetch):,} ({len(completed):,} already done)")

    if dry_run:
        log.info("DRY RUN — would fetch:")
        for d in to_fetch[:20]:
            log.info(f"  {d['doc_id']}: {d['title'][:80]}")
        if len(to_fetch) > 20:
            log.info(f"  ... and {len(to_fetch) - 20:,} more")
        return

    if not to_fetch:
        log.info("Nothing to fetch — all done!")
        return

    # Ensure output dirs exist
    os.makedirs(RAW_DIR, exist_ok=True)
    for proj in VALID_PROJECTS:
        os.makedirs(os.path.join(RAW_DIR, proj), exist_ok=True)

    dl_log["total_documents"] = len(manifest)
    start_time = time.time()

    for i, entry in enumerate(to_fetch):
        doc_id = entry["doc_id"]

        try:
            api_doc = fetch_document(doc_id)
            if api_doc is None:
                failed.add(doc_id)
                dl_log["failed_ids"] = list(failed)
                continue

            raw = build_raw_json(api_doc, entry)

            # Write to /harvest/raw/founders-online/{Project}/{id}.json
            project = entry["project"]
            id_slug = doc_id.split("/", 1)[1] if "/" in doc_id else doc_id
            out_path = os.path.join(RAW_DIR, project, f"{id_slug}.json")
            content = json.dumps(raw, indent=2, ensure_ascii=False)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)

            nbytes = len(content.encode("utf-8"))
            completed.add(doc_id)
            dl_log["completed_ids"] = list(completed)
            dl_log["total_fetched"] = len(completed)
            dl_log["total_bytes"] = dl_log.get("total_bytes", 0) + nbytes

        except Exception as e:
            log.error(f"Error fetching {doc_id}: {e}")
            failed.add(doc_id)
            dl_log["failed_ids"] = list(failed)

        # Progress
        if (i + 1) % 100 == 0:
            elapsed = time.time() - start_time
            rate_actual = (i + 1) / elapsed if elapsed > 0 else 0
            remaining_sec = (len(to_fetch) - i - 1) / rate_actual if rate_actual > 0 else 0
            pct = len(completed) / len(manifest) * 100
            log.info(
                f"Progress: {len(completed):,}/{len(manifest):,} ({pct:.1f}%) | "
                f"{rate_actual:.1f} docs/sec | ETA: {remaining_sec/3600:.1f}h | "
                f"Failed: {len(failed)}"
            )

        # Checkpoint
        if (i + 1) % CHECKPOINT_INTERVAL == 0:
            save_download_log(LOG_PATH, dl_log)

        time.sleep(REQUEST_DELAY)

    # Final save
    save_download_log(LOG_PATH, dl_log)
    elapsed = time.time() - start_time
    size_gb = dl_log.get("total_bytes", 0) / 1e9

    log.info("=" * 60)
    log.info("HARVEST COMPLETE")
    log.info(f"  Total: {len(manifest):,}")
    log.info(f"  Fetched: {len(completed):,}")
    log.info(f"  Failed: {len(failed):,}")
    log.info(f"  Size: {size_gb:.2f} GB")
    log.info(f"  Time: {elapsed/3600:.1f} hours")
    log.info("=" * 60)

    if failed:
        log.warning(f"Re-run with --resume --retry-failed to retry {len(failed)} failures")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Founders Online harvester — founders.archives.gov"
    )
    parser.add_argument("--discover", action="store_true",
                        help="Download and parse metadata index")
    parser.add_argument("--download", action="store_true",
                        help="Download full text documents")
    parser.add_argument("--all", action="store_true",
                        help="Download all documents (required with --download)")
    parser.add_argument("--project", type=str, choices=sorted(VALID_PROJECTS),
                        help="Only harvest one Founder's documents")
    parser.add_argument("--resume", action="store_true",
                        help="Resume interrupted download")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Clear failed list and retry")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be fetched")
    parser.add_argument("--rate", type=float, default=REQUESTS_PER_SECOND,
                        help=f"Requests per second (default: {REQUESTS_PER_SECOND}, max: 10)")

    args = parser.parse_args()

    if not args.discover and not args.download:
        parser.print_help()
        sys.exit(1)

    if args.download and not args.all and not args.project:
        log.error("--download requires --all or --project <name>")
        sys.exit(1)

    if args.discover:
        do_discover()

    if args.download:
        do_download(
            project_filter=args.project,
            resume=args.resume,
            retry_failed=args.retry_failed,
            dry_run=args.dry_run,
            rate=args.rate,
        )


if __name__ == "__main__":
    main()
