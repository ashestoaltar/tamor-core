#!/usr/bin/env python3
"""
Torah Class scraper — torahclass.com

Scrapes Tom Bradford's verse-by-verse Bible studies.
Text manuscripts (PDF transcripts) are the primary target.

Usage:
    # Phase 1: Discover all lessons
    python3 torah_class.py --discover

    # Phase 2: Download transcripts and write raw JSON
    python3 torah_class.py --download --book genesis --limit 5
    python3 torah_class.py --download --book genesis  # all Genesis
    python3 torah_class.py --download --all            # everything

Runs on: scraper machine or Tamor (for testing)
Output: /mnt/library/harvest/raw/torah-class/*.json
"""

import argparse
import io
import json
import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

try:
    from pypdf import PdfReader
except ImportError:
    print("ERROR: pypdf not installed. Run: pip install pypdf")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HARVEST_BASE = "/mnt/library/harvest"
RAW_DIR = os.path.join(HARVEST_BASE, "raw", "torah-class")
CONFIG_DIR = os.path.join(HARVEST_BASE, "config")
MANIFEST_PATH = os.path.join(CONFIG_DIR, "torah-class-manifest.json")
LOG_PATH = os.path.join(CONFIG_DIR, "torah-class-download-log.json")

# NAS storage for original PDFs (consistent with billcloud/, wildbranch ministries/, etc.)
NAS_LIBRARY_BASE = "/mnt/library"
NAS_TORAHCLASS_DIR = os.path.join(NAS_LIBRARY_BASE, "religious", "torahclass")

SITEMAPS = [
    "https://www.torahclass.com/tc-lessons-sitemap.xml",
    "https://www.torahclass.com/tc-lessons-sitemap2.xml",
]

CDN_TRANSCRIPT_GUESS = "https://cdn.torahclass.com/tclsmedia/transcript/EN/text-{book}-l{num:02d}-{slug}.pdf"

HEADERS = {
    "User-Agent": "TamorHarvest/1.0 (personal research library)",
}

REQUEST_DELAY = 1.5  # seconds between requests

SOURCE_NAME = "Torah Class"
TEACHER_DEFAULT = "Tom Bradford"
THEOLOGICAL_STREAM = "messianic-torah-observant"
COLLECTION_NAME = "Torah Class"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Text cleanup (duplicated from api/services/file_parsing.py for portability)
# ---------------------------------------------------------------------------

def clean_extracted_text(text):
    """Clean up text extracted from PDFs."""
    if not text:
        return text

    lines = text.split("\n")
    cleaned = []

    # Remove page number lines
    page_re = re.compile(
        r"^\s*\d+\s*/\s*\d+\s*$|"
        r"^\s*Page\s+\d+\s*$|"
        r"^\s*-\s*\d+\s*-\s*$|"
        r"^\s*\[\s*\d+\s*\]\s*$",
        re.IGNORECASE,
    )

    for line in lines:
        s = line.strip()
        if not s:
            cleaned.append("")
            continue
        if page_re.match(s):
            continue
        if len(s) <= 4 and s.isdigit():
            continue
        cleaned.append(line)

    # Merge broken lines
    merged = []
    i = 0
    enders = '.!?:;"\'"\u201d\u2019'

    while i < len(cleaned):
        line = cleaned[i].strip()
        if not line:
            merged.append("")
            i += 1
            continue

        while i + 1 < len(cleaned):
            nxt = cleaned[i + 1].strip()
            if not nxt:
                break
            if line and line[-1] in enders:
                break
            if nxt and nxt[0].isupper():
                if not (line.endswith(",") or line.endswith("-") or
                        line.endswith("and") or line.endswith("or") or
                        line.endswith("the") or line.endswith("a")):
                    break
            line = line + " " + nxt
            i += 1

        merged.append(line)
        i += 1

    # Collapse multiple blank lines
    final = []
    prev_blank = False
    for line in merged:
        blank = not line.strip()
        if blank:
            if not prev_blank:
                final.append("")
            prev_blank = True
        else:
            final.append(line)
            prev_blank = False

    return "\n".join(final).strip()


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def fetch_sitemap_urls(sitemap_url):
    """Fetch and parse a sitemap XML, returning all URLs."""
    log.info(f"Fetching sitemap: {sitemap_url}")
    resp = requests.get(sitemap_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    # Parse XML (remove namespace for easier parsing)
    content = re.sub(r'\sxmlns="[^"]+"', '', resp.text, count=1)
    root = ET.fromstring(content)

    urls = []
    for url_elem in root.findall(".//url/loc"):
        urls.append(url_elem.text.strip())

    return urls


def is_english_lesson(url):
    """Check if URL is an English lesson (not translated)."""
    # English lessons: /lessons/old-testament/ or /lessons/new-testament/
    # Translated: /lessons/es/ or /lessons/ru/ etc.
    if "/lessons/es/" in url or "/lessons/ru/" in url:
        return False
    if "/lessons/hi/" in url or "/lessons/ar/" in url:
        return False
    # Must be a specific lesson, not just the index page
    if url.rstrip("/").endswith("/lessons"):
        return False
    if re.search(r"/lessons/(old|new)-testament/[^/]+/lesson-", url):
        return True
    return False


def parse_lesson_url(url):
    """
    Extract book, lesson number, and slug from a lesson URL.

    URL pattern: /lessons/old-testament/genesis/lesson-1-intro-10/
    Returns: (testament, book, lesson_num, slug) or None
    """
    m = re.search(
        r"/lessons/(old|new)-testament/([^/]+)/lesson-(\d+)-([^/]+)/?$",
        url,
    )
    if not m:
        return None
    testament = m.group(1)
    book = m.group(2)
    lesson_num = int(m.group(3))
    slug = m.group(4)
    return testament, book, lesson_num, slug


def build_transcript_url_guess(book, lesson_num, slug):
    """Build a guessed CDN transcript PDF URL (may not match actual filename)."""
    return CDN_TRANSCRIPT_GUESS.format(book=book, num=lesson_num, slug=slug)


def extract_transcript_url(lesson_page_url):
    """
    Fetch a lesson page and extract the real transcript URL from ALL_VIDEO_DATA.

    Returns transcript URL string, or None if not found.
    """
    try:
        resp = requests.get(lesson_page_url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        m = re.search(r'transcriptUrl":"(https?:[^"]+)"', resp.text)
        if m:
            return m.group(1).replace("\\/", "/")
    except Exception as e:
        log.warning(f"  Could not fetch lesson page: {e}")
    return None


def fetch_lesson_metadata(url):
    """
    Fetch a lesson page and extract metadata from ALL_VIDEO_DATA.

    Returns dict with title, duration, categoryName, etc.
    """
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    metadata = {}

    # Extract ALL_VIDEO_DATA from JavaScript
    m = re.search(r"ALL_VIDEO_DATA\s*=\s*(\{[^}]+\})", resp.text)
    if m:
        try:
            data = json.loads(m.group(1))
            metadata["title"] = data.get("title", "")
            metadata["duration"] = data.get("duration", 0)
            metadata["category"] = data.get("categoryName", "")
            metadata["video_id"] = data.get("videoId", 0)
        except json.JSONDecodeError:
            pass

    # Try to find teacher name
    if "tom bradford" in resp.text.lower():
        metadata["teacher"] = "Tom Bradford"
    elif "baruch korman" in resp.text.lower():
        metadata["teacher"] = "Baruch Korman"

    return metadata


def discover(delay=REQUEST_DELAY):
    """
    Discover all English lessons from Torah Class sitemaps.

    Writes manifest to CONFIG_DIR.
    """
    os.makedirs(CONFIG_DIR, exist_ok=True)

    # Collect all URLs from sitemaps
    all_urls = []
    for sitemap_url in SITEMAPS:
        try:
            urls = fetch_sitemap_urls(sitemap_url)
            all_urls.extend(urls)
            time.sleep(delay)
        except Exception as e:
            log.error(f"Failed to fetch {sitemap_url}: {e}")

    # Filter to English lessons
    lesson_urls = [u for u in all_urls if is_english_lesson(u)]
    log.info(f"Found {len(lesson_urls)} English lesson URLs (from {len(all_urls)} total)")

    # Parse each URL into structured data
    books = {}
    for url in sorted(lesson_urls):
        parsed = parse_lesson_url(url)
        if not parsed:
            log.warning(f"Could not parse: {url}")
            continue

        testament, book, lesson_num, slug = parsed
        transcript_url_guess = build_transcript_url_guess(book, lesson_num, slug)

        lesson = {
            "url": url,
            "testament": testament,
            "book": book,
            "lesson_number": lesson_num,
            "slug": slug,
            "transcript_url_guess": transcript_url_guess,
        }

        if book not in books:
            books[book] = {"testament": testament, "lessons": []}
        books[book]["lessons"].append(lesson)

    # Sort lessons within each book
    for book_data in books.values():
        book_data["lessons"].sort(key=lambda x: x["lesson_number"])
        book_data["count"] = len(book_data["lessons"])

    # Build manifest
    total = sum(b["count"] for b in books.values())
    manifest = {
        "source": SOURCE_NAME,
        "discovered_at": datetime.utcnow().isoformat() + "Z",
        "total_lessons": total,
        "books": books,
    }

    # Write manifest
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    log.info(f"Manifest written: {MANIFEST_PATH}")
    log.info(f"Total: {total} lessons across {len(books)} books")
    for book, data in sorted(books.items()):
        log.info(f"  {book}: {data['count']} lessons ({data['testament']} testament)")

    return manifest


# ---------------------------------------------------------------------------
# Download & Extract
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_bytes):
    """Extract text from PDF bytes using pypdf."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    return "\n\n".join(text_parts)


def derive_scripture_refs(book, slug):
    """
    Derive scripture references from the URL slug.

    Examples:
        slug="intro-10" book="genesis" → ["Genesis 1-10"]
        slug="ch2" → ["Genesis 2"]
        slug="ch12-ch13" → ["Genesis 12-13"]
        slug="ch1-ch3" → ["Genesis 1-3"]
    """
    book_title = book.replace("-", " ").title()

    # Extract chapter numbers from slug
    chapters = re.findall(r"ch(\d+)", slug)
    if chapters:
        chapters = [int(c) for c in chapters]
        if len(chapters) == 1:
            return [f"{book_title} {chapters[0]}"]
        else:
            return [f"{book_title} {min(chapters)}-{max(chapters)}"]

    # Check for intro pattern
    m = re.search(r"intro-?(\d+)?", slug)
    if m:
        end_ch = m.group(1)
        if end_ch:
            return [f"{book_title} 1-{end_ch}"]
        return [f"{book_title} (Introduction)"]

    return [f"{book_title}"]


def load_download_log():
    """Load download tracking log."""
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "r") as f:
            return json.load(f)
    return {"downloaded": [], "failed": [], "skipped": []}


def save_download_log(log_data):
    """Save download tracking log."""
    with open(LOG_PATH, "w") as f:
        json.dump(log_data, f, indent=2)


def download_lessons(book_filter=None, limit=None, delay=REQUEST_DELAY):
    """
    Download transcript PDFs, extract text, write raw JSON.

    Args:
        book_filter: Only download this book (e.g., "genesis")
        limit: Max lessons to download
        delay: Seconds between requests
    """
    # Load manifest
    if not os.path.exists(MANIFEST_PATH):
        log.error(f"Manifest not found. Run --discover first.")
        log.error(f"Expected: {MANIFEST_PATH}")
        return

    with open(MANIFEST_PATH, "r") as f:
        manifest = json.load(f)

    os.makedirs(RAW_DIR, exist_ok=True)

    # Collect lessons to download
    lessons = []
    for book, data in manifest["books"].items():
        if book_filter and book.lower() != book_filter.lower():
            continue
        for lesson in data["lessons"]:
            lessons.append(lesson)

    if not lessons:
        log.error(f"No lessons found" + (f" for book '{book_filter}'" if book_filter else ""))
        return

    if limit:
        lessons = lessons[:limit]

    log.info(f"Downloading {len(lessons)} lessons")

    dl_log = load_download_log()
    downloaded_urls = set(dl_log["downloaded"])

    success = 0
    errors = 0

    for i, lesson in enumerate(lessons, 1):
        url = lesson["url"]
        book = lesson["book"]
        num = lesson["lesson_number"]
        slug = lesson["slug"]

        # Skip already downloaded
        if url in downloaded_urls:
            log.info(f"[{i}/{len(lessons)}] Skip (already done): lesson-{num}-{slug}")
            continue

        filename = f"torah-class-{book}-l{num:02d}-{slug}.txt"
        output_path = os.path.join(RAW_DIR, filename.replace(".txt", ".json"))

        # Skip if raw JSON already exists
        if os.path.exists(output_path):
            log.info(f"[{i}/{len(lessons)}] Skip (file exists): {filename}")
            dl_log["downloaded"].append(url)
            save_download_log(dl_log)
            continue

        log.info(f"[{i}/{len(lessons)}] {book} lesson {num}: {slug}")

        try:
            # Get real transcript URL from lesson page
            transcript_url = extract_transcript_url(url)
            if not transcript_url:
                log.warning(f"  No transcript URL found on page")
                dl_log["failed"].append({"url": url, "reason": "no transcript URL on page"})
                save_download_log(dl_log)
                errors += 1
                time.sleep(delay)
                continue

            time.sleep(delay)  # rate limit between page fetch and PDF fetch

            # Download transcript PDF
            resp = requests.get(transcript_url, headers=HEADERS, timeout=60)

            if resp.status_code == 404:
                log.warning(f"  Transcript not found: {transcript_url}")
                dl_log["failed"].append({"url": url, "reason": "transcript 404"})
                save_download_log(dl_log)
                errors += 1
                time.sleep(delay)
                continue

            resp.raise_for_status()

            # Save original PDF to NAS
            pdf_filename = f"text-{book}-l{num:02d}-{slug}.pdf"
            nas_book_dir = os.path.join(NAS_TORAHCLASS_DIR, book)
            os.makedirs(nas_book_dir, exist_ok=True)
            nas_pdf_path = os.path.join(nas_book_dir, pdf_filename)
            with open(nas_pdf_path, "wb") as pdf_f:
                pdf_f.write(resp.content)
            log.info(f"  Saved PDF to NAS: {nas_pdf_path}")

            # stored_path is relative to /mnt/library/
            stored_path = os.path.join("religious", "torahclass", book, pdf_filename)

            # Extract text from PDF
            raw_text = extract_pdf_text(resp.content)
            if not raw_text or len(raw_text.strip()) < 100:
                log.warning(f"  Transcript too short ({len(raw_text)} chars)")
                dl_log["failed"].append({"url": url, "reason": "text too short"})
                save_download_log(dl_log)
                errors += 1
                time.sleep(delay)
                continue

            # Clean the text
            text = clean_extracted_text(raw_text)
            word_count = len(text.split())

            # Derive metadata
            book_title = book.replace("-", " ").title()
            # Build readable title from slug, stripping trailing numbers
            slug_label = re.sub(r"-\d+$", "", slug).replace("-", " ").title()
            title = f"{book_title} Lesson {num}: {slug_label}"
            scripture_refs = derive_scripture_refs(book, slug)

            # Build raw JSON
            raw_item = {
                "text": text,
                "filename": pdf_filename,
                "stored_path": stored_path,
                "mime_type": "application/pdf",
                "source_name": SOURCE_NAME,
                "title": title,
                "teacher": TEACHER_DEFAULT,
                "collection": COLLECTION_NAME,
                "content_type": "lesson",
                "url": url,
                "topics": [book_title.lower(), "torah", "bible study"],
                "series": book_title,
                "metadata": {
                    "theological_stream": THEOLOGICAL_STREAM,
                    "scripture_refs": scripture_refs,
                    "language": "en",
                    "original_format": "pdf",
                    "word_count": word_count,
                    "lesson_number": num,
                    "transcript_pdf_url": transcript_url,
                },
                "copyright_note": "Personal research use only. Content from torahclass.com.",
            }

            # Write raw JSON
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(raw_item, f, indent=2, ensure_ascii=False)

            log.info(f"  OK: {word_count} words, {len(text)} chars → {os.path.basename(output_path)}")

            dl_log["downloaded"].append(url)
            save_download_log(dl_log)
            success += 1

        except Exception as e:
            log.error(f"  Error: {e}")
            dl_log["failed"].append({"url": url, "reason": str(e)})
            save_download_log(dl_log)
            errors += 1

        time.sleep(delay)

    log.info(f"Done: {success} downloaded, {errors} errors, {len(lessons) - success - errors} skipped")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Torah Class scraper — torahclass.com"
    )
    parser.add_argument(
        "--discover", action="store_true",
        help="Discover all lessons and build manifest"
    )
    parser.add_argument(
        "--download", action="store_true",
        help="Download transcripts and write raw JSON"
    )
    parser.add_argument(
        "--book", type=str, default=None,
        help="Filter to specific book (e.g., genesis)"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max lessons to download"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Download all books (use with --download)"
    )
    parser.add_argument(
        "--delay", type=float, default=REQUEST_DELAY,
        help=f"Delay between requests in seconds (default: {REQUEST_DELAY})"
    )
    parser.add_argument(
        "--manifest", action="store_true",
        help="Print manifest summary"
    )

    args = parser.parse_args()

    if args.manifest:
        if not os.path.exists(MANIFEST_PATH):
            print("No manifest found. Run --discover first.")
            return
        with open(MANIFEST_PATH, "r") as f:
            m = json.load(f)
        print(f"Source: {m['source']}")
        print(f"Discovered: {m['discovered_at']}")
        print(f"Total: {m['total_lessons']} lessons\n")
        for book, data in sorted(m["books"].items()):
            print(f"  {book:20s} {data['count']:3d} lessons  ({data['testament']})")
        return

    if args.discover:
        discover(delay=args.delay)
    elif args.download:
        if not args.book and not args.all:
            parser.error("Specify --book NAME or --all with --download")
        download_lessons(
            book_filter=args.book if not args.all else None,
            limit=args.limit,
            delay=args.delay,
        )
    else:
        parser.error("Specify --discover or --download")


if __name__ == "__main__":
    main()
