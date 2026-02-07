#!/usr/bin/env python3
"""
TorahResource scraper — torahresource.com

Scrapes Tim Hegg's articles and Torah commentaries (PDFs hosted on S3).

Usage:
    # Phase 1: Discover all content from sitemaps
    python3 torah_resource.py --discover

    # Phase 2: Download PDFs and write raw JSON
    python3 torah_resource.py --download --type articles --limit 5
    python3 torah_resource.py --download --type commentaries
    python3 torah_resource.py --download --all

Runs on: scraper machine or Tamor (for testing)
Output: /mnt/library/harvest/raw/torahresource/*.json
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

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: beautifulsoup4 not installed. Run: pip install beautifulsoup4")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HARVEST_BASE = "/mnt/library/harvest"
RAW_DIR = os.path.join(HARVEST_BASE, "raw", "torahresource")
CONFIG_DIR = os.path.join(HARVEST_BASE, "config")
MANIFEST_PATH = os.path.join(CONFIG_DIR, "torahresource-manifest.json")
LOG_PATH = os.path.join(CONFIG_DIR, "torahresource-download-log.json")

NAS_LIBRARY_BASE = "/mnt/library"
NAS_TR_DIR = os.path.join(NAS_LIBRARY_BASE, "religious", "torahresource")

SITEMAPS = {
    "articles": "https://torahresource.com/article-sitemap.xml",
    "commentaries": "https://torahresource.com/torah-commentary-sitemap.xml",
}

# S3 URL patterns (guesses — will verify from page content)
S3_ARTICLES = "https://tr-pdf.s3-us-west-2.amazonaws.com/articles/"
S3_COMMENTARIES = "https://weekly-parashah.s3-us-west-2.amazonaws.com/"

HEADERS = {
    "User-Agent": "TamorHarvest/1.0 (personal research library)",
}

REQUEST_DELAY = 1.5  # seconds between requests

SOURCE_NAME = "TorahResource"
TEACHER_DEFAULT = "Tim Hegg"
THEOLOGICAL_STREAM = "messianic-one-law"
COLLECTION_NAME = "TorahResource"

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

    content = re.sub(r'\sxmlns="[^"]+"', '', resp.text, count=1)
    root = ET.fromstring(content)

    urls = []
    for url_elem in root.findall(".//url/loc"):
        urls.append(url_elem.text.strip())

    return urls


def parse_article_slug(url):
    """Extract slug from article URL like https://torahresource.com/article/slug/"""
    m = re.search(r"torahresource\.com/article/([^/]+)/?$", url)
    if m:
        return m.group(1)
    return None


def parse_commentary_slug(url):
    """Extract slug from commentary URL like https://torahresource.com/torah-commentary/081-leviticus/"""
    m = re.search(r"torahresource\.com/torah-commentary/([^/]+)/?$", url)
    if m:
        return m.group(1)
    return None


def discover(delay=REQUEST_DELAY):
    """
    Discover all articles and commentaries from TorahResource sitemaps.
    Writes manifest to CONFIG_DIR.
    """
    os.makedirs(CONFIG_DIR, exist_ok=True)

    manifest_data = {
        "source": SOURCE_NAME,
        "discovered_at": datetime.utcnow().isoformat() + "Z",
        "articles": [],
        "commentaries": [],
    }

    # Fetch article sitemap
    try:
        article_urls = fetch_sitemap_urls(SITEMAPS["articles"])
        log.info(f"Found {len(article_urls)} article URLs")
        for url in sorted(article_urls):
            slug = parse_article_slug(url)
            if slug:
                manifest_data["articles"].append({
                    "url": url,
                    "slug": slug,
                    "type": "article",
                })
        time.sleep(delay)
    except Exception as e:
        log.error(f"Failed to fetch article sitemap: {e}")

    # Fetch commentary sitemap
    try:
        commentary_urls = fetch_sitemap_urls(SITEMAPS["commentaries"])
        log.info(f"Found {len(commentary_urls)} commentary URLs")
        for url in sorted(commentary_urls):
            slug = parse_commentary_slug(url)
            if slug:
                manifest_data["commentaries"].append({
                    "url": url,
                    "slug": slug,
                    "type": "commentary",
                })
    except Exception as e:
        log.error(f"Failed to fetch commentary sitemap: {e}")

    manifest_data["total_articles"] = len(manifest_data["articles"])
    manifest_data["total_commentaries"] = len(manifest_data["commentaries"])
    manifest_data["total"] = manifest_data["total_articles"] + manifest_data["total_commentaries"]

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    log.info(f"Manifest written: {MANIFEST_PATH}")
    log.info(f"  Articles: {manifest_data['total_articles']}")
    log.info(f"  Commentaries: {manifest_data['total_commentaries']}")
    log.info(f"  Total: {manifest_data['total']}")

    return manifest_data


# ---------------------------------------------------------------------------
# Page scraping helpers
# ---------------------------------------------------------------------------

def extract_article_info(url):
    """
    Fetch an article page and extract title, date, and PDF download URL.

    Returns dict with keys: title, date, pdf_url, scripture_refs, topics
    """
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    info = {
        "title": None,
        "date": None,
        "pdf_url": None,
        "scripture_refs": [],
        "topics": [],
    }

    # Title: try <h1> first, then <title>
    h1 = soup.find("h1", class_="entry-title") or soup.find("h1")
    if h1:
        info["title"] = h1.get_text(strip=True)
    elif soup.title:
        info["title"] = soup.title.get_text(strip=True).split("|")[0].strip()

    # Date: look for time element or date in meta
    time_el = soup.find("time")
    if time_el:
        dt = time_el.get("datetime", "")
        if dt:
            info["date"] = dt[:10]  # YYYY-MM-DD

    # PDF URL: look for links to S3 PDFs
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "s3" in href and href.endswith(".pdf"):
            info["pdf_url"] = href
            break
        if "tr-pdf" in href and href.endswith(".pdf"):
            info["pdf_url"] = href
            break

    # Also check for direct download links with .pdf
    if not info["pdf_url"]:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.endswith(".pdf") and ("amazonaws" in href or "torahresource" in href):
                info["pdf_url"] = href
                break

    # Topics: look for category/tag links
    for tag_link in soup.find_all("a", rel="tag"):
        info["topics"].append(tag_link.get_text(strip=True).lower())

    # Scripture refs: try to extract from content
    content_div = soup.find("div", class_="entry-content") or soup.find("article")
    if content_div:
        text = content_div.get_text()
        # Look for scripture reference patterns
        refs = re.findall(
            r'(?:Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|'
            r'1\s*Samuel|2\s*Samuel|1\s*Kings|2\s*Kings|1\s*Chronicles|2\s*Chronicles|'
            r'Ezra|Nehemiah|Esther|Job|Psalms?|Proverbs|Ecclesiastes|Song\s*of\s*Solomon|'
            r'Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|'
            r'Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|'
            r'Matthew|Mark|Luke|John|Acts|Romans|1\s*Corinthians|2\s*Corinthians|'
            r'Galatians|Ephesians|Philippians|Colossians|1\s*Thessalonians|'
            r'2\s*Thessalonians|1\s*Timothy|2\s*Timothy|Titus|Philemon|Hebrews|'
            r'James|1\s*Peter|2\s*Peter|1\s*John|2\s*John|3\s*John|Jude|Revelation)'
            r'\s+\d+[:\d\-,\s]*',
            text,
        )
        # Deduplicate and take first few
        seen = set()
        for ref in refs[:5]:
            ref_clean = ref.strip()
            if ref_clean not in seen:
                info["scripture_refs"].append(ref_clean)
                seen.add(ref_clean)

    return info


def extract_commentary_info(url):
    """
    Fetch a commentary page and extract title, portion name, scripture refs, PDF URL.

    Returns dict with keys: title, pdf_url, scripture_refs, portion_name
    """
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    info = {
        "title": None,
        "pdf_url": None,
        "scripture_refs": [],
        "portion_name": None,
    }

    # Title
    h1 = soup.find("h1", class_="entry-title") or soup.find("h1")
    if h1:
        info["title"] = h1.get_text(strip=True)
    elif soup.title:
        info["title"] = soup.title.get_text(strip=True).split("|")[0].strip()

    # Extract Torah portion name from title
    if info["title"]:
        # Titles often like "Parashah #1 B'resheet" or "B'resheet – Genesis 1:1-6:8"
        info["portion_name"] = info["title"]

    # PDF URL: look for S3 parashah PDFs
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.endswith(".pdf") and ("weekly-parashah" in href or "s3" in href):
            info["pdf_url"] = href
            break
        if href.endswith(".pdf") and "amazonaws" in href:
            info["pdf_url"] = href
            break

    # Also try direct PDF links
    if not info["pdf_url"]:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.endswith(".pdf"):
                info["pdf_url"] = href
                break

    # Scripture refs from content
    content_div = soup.find("div", class_="entry-content") or soup.find("article")
    if content_div:
        text = content_div.get_text()
        # Look for Torah portion scripture ranges
        refs = re.findall(
            r'(?:Genesis|Exodus|Leviticus|Numbers|Deuteronomy)'
            r'\s+\d+[:\d\-,\s]*',
            text,
        )
        seen = set()
        for ref in refs[:3]:
            ref_clean = ref.strip()
            if ref_clean not in seen:
                info["scripture_refs"].append(ref_clean)
                seen.add(ref_clean)

    return info


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


def download_items(content_type="articles", limit=None, delay=REQUEST_DELAY):
    """
    Download PDFs, extract text, write raw JSON.

    Args:
        content_type: "articles" or "commentaries"
        limit: Max items to download
        delay: Seconds between requests
    """
    if not os.path.exists(MANIFEST_PATH):
        log.error(f"Manifest not found. Run --discover first.")
        log.error(f"Expected: {MANIFEST_PATH}")
        return

    with open(MANIFEST_PATH, "r") as f:
        manifest = json.load(f)

    items = manifest.get(content_type, [])
    if not items:
        log.error(f"No {content_type} found in manifest")
        return

    if limit:
        items = items[:limit]

    os.makedirs(RAW_DIR, exist_ok=True)

    # NAS directories
    if content_type == "articles":
        nas_dir = os.path.join(NAS_TR_DIR, "articles")
    else:
        nas_dir = os.path.join(NAS_TR_DIR, "commentaries")
    os.makedirs(nas_dir, exist_ok=True)

    dl_log = load_download_log()
    downloaded_urls = set(dl_log["downloaded"])

    success = 0
    errors = 0

    log.info(f"Downloading {len(items)} {content_type}")

    for i, item in enumerate(items, 1):
        url = item["url"]
        slug = item["slug"]

        # Skip already downloaded
        if url in downloaded_urls:
            log.info(f"[{i}/{len(items)}] Skip (already done): {slug}")
            continue

        # Check if raw JSON already exists
        output_filename = f"torahresource-{slug}.json"
        output_path = os.path.join(RAW_DIR, output_filename)
        if os.path.exists(output_path):
            log.info(f"[{i}/{len(items)}] Skip (file exists): {slug}")
            dl_log["downloaded"].append(url)
            save_download_log(dl_log)
            continue

        log.info(f"[{i}/{len(items)}] {content_type[:-1]}: {slug}")

        try:
            # Fetch page and extract info
            if content_type == "articles":
                info = extract_article_info(url)
            else:
                info = extract_commentary_info(url)

            time.sleep(delay)

            pdf_url = info.get("pdf_url")
            if not pdf_url:
                log.warning(f"  No PDF URL found on page: {url}")
                dl_log["failed"].append({"url": url, "reason": "no PDF URL on page"})
                save_download_log(dl_log)
                errors += 1
                continue

            # Download PDF
            log.info(f"  Downloading PDF: {os.path.basename(pdf_url)}")
            pdf_resp = requests.get(pdf_url, headers=HEADERS, timeout=120)

            if pdf_resp.status_code == 404:
                log.warning(f"  PDF not found: {pdf_url}")
                dl_log["failed"].append({"url": url, "reason": "PDF 404"})
                save_download_log(dl_log)
                errors += 1
                time.sleep(delay)
                continue

            pdf_resp.raise_for_status()

            # Save original PDF to NAS
            pdf_filename = f"{slug}.pdf"
            nas_pdf_path = os.path.join(nas_dir, pdf_filename)
            with open(nas_pdf_path, "wb") as pdf_f:
                pdf_f.write(pdf_resp.content)
            log.info(f"  Saved PDF to NAS: {nas_pdf_path}")

            # stored_path relative to /mnt/library/
            subdir = "articles" if content_type == "articles" else "commentaries"
            stored_path = f"religious/torahresource/{subdir}/{pdf_filename}"

            # Extract text
            raw_text = extract_pdf_text(pdf_resp.content)
            if not raw_text or len(raw_text.strip()) < 50:
                log.warning(f"  Text too short ({len(raw_text) if raw_text else 0} chars) — may be scanned PDF")
                dl_log["failed"].append({"url": url, "reason": "text too short (scanned?)"})
                save_download_log(dl_log)
                errors += 1
                time.sleep(delay)
                continue

            text = clean_extracted_text(raw_text)
            word_count = len(text.split())

            # Build title
            title = info.get("title") or slug.replace("-", " ").title()

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
                "content_type": "article" if content_type == "articles" else "commentary",
                "url": url,
                "topics": info.get("topics", []),
                "series": "Torah Commentaries" if content_type == "commentaries" else None,
                "metadata": {
                    "theological_stream": THEOLOGICAL_STREAM,
                    "scripture_refs": info.get("scripture_refs", []),
                    "language": "en",
                    "original_format": "pdf",
                    "word_count": word_count,
                    "pdf_url": pdf_url,
                },
                "copyright_note": "Personal research use only. Free content from torahresource.com.",
            }

            if info.get("date"):
                raw_item["date"] = info["date"]

            if content_type == "commentaries" and info.get("portion_name"):
                raw_item["metadata"]["portion_name"] = info["portion_name"]

            # Write raw JSON
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(raw_item, f, indent=2, ensure_ascii=False)

            log.info(f"  OK: {word_count} words, {len(text)} chars → {output_filename}")

            dl_log["downloaded"].append(url)
            save_download_log(dl_log)
            success += 1

        except Exception as e:
            log.error(f"  Error: {e}")
            dl_log["failed"].append({"url": url, "reason": str(e)})
            save_download_log(dl_log)
            errors += 1

        time.sleep(delay)

    log.info(f"Done: {success} downloaded, {errors} errors, {len(items) - success - errors} skipped")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="TorahResource scraper — torahresource.com"
    )
    parser.add_argument(
        "--discover", action="store_true",
        help="Discover all content from sitemaps and build manifest"
    )
    parser.add_argument(
        "--download", action="store_true",
        help="Download PDFs and write raw JSON"
    )
    parser.add_argument(
        "--type", type=str, choices=["articles", "commentaries"],
        help="Content type to download (use with --download)"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max items to download"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Download all content types (use with --download)"
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
        print(f"  Articles:      {m['total_articles']}")
        print(f"  Commentaries:  {m['total_commentaries']}")
        print(f"  Total:         {m['total']}")
        return

    if args.discover:
        discover(delay=args.delay)
    elif args.download:
        if not args.type and not args.all:
            parser.error("Specify --type articles|commentaries or --all with --download")
        if args.all:
            download_items("articles", limit=args.limit, delay=args.delay)
            download_items("commentaries", limit=args.limit, delay=args.delay)
        else:
            download_items(args.type, limit=args.limit, delay=args.delay)
    else:
        parser.error("Specify --discover or --download")


if __name__ == "__main__":
    main()
