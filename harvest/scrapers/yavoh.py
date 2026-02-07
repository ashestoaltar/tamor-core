#!/usr/bin/env python3
"""
YAVOH Magazine scraper — yavohmagazine.com

Scrapes Monte Judah's messianic teaching articles from Lion & Lamb Ministries.
No sitemap available — crawls pagination to discover articles.

Usage:
    # Phase 1: Discover all articles via pagination
    python3 yavoh.py --discover

    # Phase 2: Download articles and write raw JSON
    python3 yavoh.py --download --limit 10
    python3 yavoh.py --download --all

Runs on: scraper machine or Tamor (for testing)
Output: /mnt/library/harvest/raw/yavoh/*.json
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: beautifulsoup4 not installed. Run: pip install beautifulsoup4")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HARVEST_BASE = "/mnt/library/harvest"
RAW_DIR = os.path.join(HARVEST_BASE, "raw", "yavoh")
CONFIG_DIR = os.path.join(HARVEST_BASE, "config")
MANIFEST_PATH = os.path.join(CONFIG_DIR, "yavoh-manifest.json")
LOG_PATH = os.path.join(CONFIG_DIR, "yavoh-download-log.json")

NAS_LIBRARY_BASE = "/mnt/library"
NAS_YAVOH_DIR = os.path.join(NAS_LIBRARY_BASE, "religious", "lionlamb", "yavoh")

BASE_URL = "https://www.yavohmagazine.com"
LISTING_URL = f"{BASE_URL}/messianic-teachings"

HEADERS = {
    "User-Agent": "TamorHarvest/1.0 (personal research library)",
}

REQUEST_DELAY = 1.5  # seconds between requests

SOURCE_NAME = "YAVOH Magazine"
TEACHER_DEFAULT = "Monte Judah"
THEOLOGICAL_STREAM = "messianic-torah-observant"
COLLECTION_NAME = "Lion & Lamb"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Discovery (pagination crawl)
# ---------------------------------------------------------------------------

def extract_articles_from_listing(html):
    """
    Extract article entries from a Squarespace blog listing page.

    Returns list of dicts with: url, title, date, excerpt
    """
    soup = BeautifulSoup(html, "html.parser")
    articles = []

    # Squarespace blog listing: look for article entries
    # Common patterns: <article>, div.blog-item, div.entry, etc.
    for article_el in soup.find_all("article"):
        entry = {}

        # Title + URL from heading link
        title_link = article_el.find("a", class_="entry-title-link")
        if not title_link:
            title_link = article_el.find("a")
        if title_link:
            href = title_link.get("href", "")
            if href and not href.startswith("http"):
                href = BASE_URL + href
            entry["url"] = href
            entry["title"] = title_link.get_text(strip=True)

        # Date
        time_el = article_el.find("time")
        if time_el:
            dt = time_el.get("datetime", "")
            if dt:
                entry["date"] = dt[:10]
            else:
                entry["date"] = time_el.get_text(strip=True)

        # Excerpt
        excerpt_el = article_el.find("div", class_="entry-excerpt") or \
                     article_el.find("p", class_="entry-excerpt")
        if excerpt_el:
            entry["excerpt"] = excerpt_el.get_text(strip=True)[:200]

        if entry.get("url") and entry.get("title"):
            articles.append(entry)

    # Fallback: try Squarespace summary-item pattern
    if not articles:
        for item in soup.find_all("div", class_="summary-item"):
            entry = {}
            link = item.find("a")
            if link:
                href = link.get("href", "")
                if href and not href.startswith("http"):
                    href = BASE_URL + href
                entry["url"] = href

            title_el = item.find(class_="summary-title") or item.find("h1") or item.find("h2") or item.find("h3")
            if title_el:
                entry["title"] = title_el.get_text(strip=True)

            date_el = item.find("time") or item.find(class_="summary-metadata-item--date")
            if date_el:
                dt = date_el.get("datetime", "")
                if dt:
                    entry["date"] = dt[:10]
                else:
                    entry["date"] = date_el.get_text(strip=True)

            excerpt_el = item.find(class_="summary-excerpt")
            if excerpt_el:
                entry["excerpt"] = excerpt_el.get_text(strip=True)[:200]

            if entry.get("url") and entry.get("title"):
                articles.append(entry)

    # Fallback: try generic heading + link pattern
    if not articles:
        for heading in soup.find_all(["h1", "h2", "h3"]):
            link = heading.find("a")
            if link and link.get("href"):
                href = link["href"]
                if href and not href.startswith("http"):
                    href = BASE_URL + href
                # Skip navigation/menu links
                if "/messianic-teachings/" in href or "/blog/" in href:
                    articles.append({
                        "url": href,
                        "title": link.get_text(strip=True),
                    })

    return articles


def find_next_page_url(html):
    """
    Find the next page URL from pagination controls.

    Returns URL string or None.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Squarespace "Older Posts" or "Next" link
    for a in soup.find_all("a"):
        text = a.get_text(strip=True).lower()
        if text in ("older posts", "older", "next", "next page", "›", "»"):
            href = a.get("href", "")
            if href:
                if not href.startswith("http"):
                    href = BASE_URL + href
                return href

    # Check for ?offset= or ?page= pagination
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "offset=" in href or "page=" in href:
            if not href.startswith("http"):
                href = BASE_URL + href
            # Only return if it looks like a "next" link
            if a.find_parent(class_=re.compile(r"pagination|pager|nav")):
                return href

    return None


def discover(delay=REQUEST_DELAY, max_pages=100):
    """
    Discover all articles by crawling pagination.
    Writes manifest to CONFIG_DIR.
    """
    os.makedirs(CONFIG_DIR, exist_ok=True)

    all_articles = []
    seen_urls = set()
    current_url = LISTING_URL
    page_num = 1

    while current_url and page_num <= max_pages:
        log.info(f"Page {page_num}: {current_url}")

        try:
            resp = requests.get(current_url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            log.error(f"  Failed to fetch page: {e}")
            break

        articles = extract_articles_from_listing(resp.text)
        new_count = 0

        for article in articles:
            url = article["url"]
            if url not in seen_urls:
                seen_urls.add(url)
                # Generate slug from URL
                slug = url.rstrip("/").split("/")[-1]
                article["slug"] = slug
                all_articles.append(article)
                new_count += 1

        log.info(f"  Found {len(articles)} articles ({new_count} new)")

        if new_count == 0:
            log.info("  No new articles — stopping pagination")
            break

        # Find next page
        next_url = find_next_page_url(resp.text)

        # Also try Squarespace offset pagination
        if not next_url:
            # Squarespace JSON API pagination
            offset_match = re.search(r'"pagination":\s*\{[^}]*"nextPageUrl"\s*:\s*"([^"]+)"', resp.text)
            if offset_match:
                next_url = offset_match.group(1)
                if not next_url.startswith("http"):
                    next_url = BASE_URL + next_url

        if next_url == current_url:
            log.info("  Next page is same as current — stopping")
            break

        current_url = next_url
        page_num += 1

        if current_url:
            time.sleep(delay)

    # Build manifest
    manifest = {
        "source": SOURCE_NAME,
        "discovered_at": datetime.utcnow().isoformat() + "Z",
        "total_articles": len(all_articles),
        "pages_crawled": page_num,
        "articles": all_articles,
    }

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    log.info(f"Manifest written: {MANIFEST_PATH}")
    log.info(f"  Total articles: {len(all_articles)}")
    log.info(f"  Pages crawled: {page_num}")

    return manifest


# ---------------------------------------------------------------------------
# Article text extraction
# ---------------------------------------------------------------------------

def extract_article_content(url):
    """
    Fetch an article page and extract the full body text.

    Returns dict with: title, text, date, author, tags
    """
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    result = {
        "title": None,
        "text": None,
        "date": None,
        "author": TEACHER_DEFAULT,
        "tags": [],
        "scripture_refs": [],
    }

    # Title
    h1 = soup.find("h1", class_="entry-title") or soup.find("h1")
    if h1:
        result["title"] = h1.get_text(strip=True)
    elif soup.title:
        result["title"] = soup.title.get_text(strip=True).split("|")[0].strip()

    # Date — prefer JSON-LD datePublished (Squarespace puts full ISO dates there)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            ld = json.loads(script.get_text())
            if "datePublished" in ld:
                result["date"] = ld["datePublished"][:10]
                break
        except (json.JSONDecodeError, TypeError):
            pass
    if not result["date"]:
        meta_date = soup.find("meta", property="article:published_time")
        if meta_date:
            result["date"] = meta_date.get("content", "")[:10]
    if not result["date"]:
        time_el = soup.find("time")
        if time_el:
            dt = time_el.get("datetime", "")
            # Only use if it looks like a real date (has year)
            if dt and re.match(r"\d{4}", dt):
                result["date"] = dt[:10]

    # Author — Squarespace has a clean blog-author-name element
    author_el = soup.find(class_="blog-author-name") or soup.find(class_="author-name")
    if author_el:
        result["author"] = author_el.get_text(strip=True)
    else:
        author_el = soup.find(class_=re.compile(r"author|byline"))
        if author_el:
            author_text = author_el.get_text(strip=True)
            author_text = re.sub(r"^(?:by|written by|author:)\s*", "", author_text, flags=re.IGNORECASE)
            if author_text and len(author_text) < 50:
                result["author"] = author_text

    # Tags / categories
    for tag_link in soup.find_all("a", rel="tag"):
        result["tags"].append(tag_link.get_text(strip=True).lower())
    # Squarespace tags
    for tag_el in soup.find_all(class_=re.compile(r"tag-link|blog-tags")):
        for a in tag_el.find_all("a"):
            tag = a.get_text(strip=True).lower()
            if tag and tag not in result["tags"]:
                result["tags"].append(tag)

    # Body content — Squarespace uses blog-item-content-wrapper with many sqs-blocks
    content_div = (
        soup.find("div", class_="blog-item-content-wrapper") or
        soup.find("div", class_="entry-content") or
        soup.find("article") or
        soup.find("div", class_=re.compile(r"post-content|article-content"))
    )

    if content_div:
        # Remove scripts, styles, nav elements
        for unwanted in content_div.find_all(["script", "style", "nav", "header", "footer"]):
            unwanted.decompose()

        # Remove share buttons, related posts, etc.
        for unwanted in content_div.find_all(class_=re.compile(
            r"share|social|related|sidebar|comment|newsletter|subscribe"
        )):
            unwanted.decompose()

        # For Squarespace: gather text from all sqs-blocks in order
        sqs_blocks = content_div.find_all("div", class_="sqs-block")
        if sqs_blocks:
            paragraphs = []
            for block in sqs_blocks:
                # Get inner content div
                inner = block.find("div", class_="sqs-block-content") or block
                for el in inner.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "li"], recursive=True):
                    text = el.get_text(strip=True)
                    if text:
                        if el.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                            paragraphs.append(f"\n## {text}\n")
                        elif el.name == "blockquote":
                            paragraphs.append(f"> {text}")
                        elif el.name == "li":
                            paragraphs.append(f"- {text}")
                        else:
                            paragraphs.append(text)
            result["text"] = "\n\n".join(paragraphs)

        # Fallback: use get_text on entire content div
        if not result.get("text") or len(result["text"]) < 100:
            result["text"] = content_div.get_text(separator="\n\n", strip=True)
    else:
        # Last resort: try body text
        body = soup.find("body")
        if body:
            for unwanted in body.find_all(["script", "style", "nav", "header", "footer"]):
                unwanted.decompose()
            result["text"] = body.get_text(separator="\n\n", strip=True)

    # Clean up text
    if result["text"]:
        # Collapse multiple blank lines
        result["text"] = re.sub(r"\n{3,}", "\n\n", result["text"]).strip()

    # Extract scripture references
    if result["text"]:
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
            result["text"],
        )
        seen = set()
        for ref in refs[:10]:
            ref_clean = ref.strip()
            if ref_clean not in seen:
                result["scripture_refs"].append(ref_clean)
                seen.add(ref_clean)

    return result


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

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


def download_articles(limit=None, delay=REQUEST_DELAY):
    """
    Download article content, save HTML to NAS, write raw JSON.

    Args:
        limit: Max articles to download
        delay: Seconds between requests
    """
    if not os.path.exists(MANIFEST_PATH):
        log.error(f"Manifest not found. Run --discover first.")
        log.error(f"Expected: {MANIFEST_PATH}")
        return

    with open(MANIFEST_PATH, "r") as f:
        manifest = json.load(f)

    articles = manifest.get("articles", [])
    if not articles:
        log.error("No articles found in manifest")
        return

    if limit:
        articles = articles[:limit]

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(NAS_YAVOH_DIR, exist_ok=True)

    dl_log = load_download_log()
    downloaded_urls = set(dl_log["downloaded"])

    success = 0
    errors = 0

    log.info(f"Downloading {len(articles)} articles")

    for i, article in enumerate(articles, 1):
        url = article["url"]
        slug = article.get("slug", url.rstrip("/").split("/")[-1])

        # Skip already downloaded
        if url in downloaded_urls:
            log.info(f"[{i}/{len(articles)}] Skip (already done): {slug}")
            continue

        # Check if raw JSON already exists
        output_filename = f"yavoh-{slug}.json"
        output_path = os.path.join(RAW_DIR, output_filename)
        if os.path.exists(output_path):
            log.info(f"[{i}/{len(articles)}] Skip (file exists): {slug}")
            dl_log["downloaded"].append(url)
            save_download_log(dl_log)
            continue

        log.info(f"[{i}/{len(articles)}] {article.get('title', slug)}")

        try:
            # Fetch and extract article content
            content = extract_article_content(url)

            if not content["text"] or len(content["text"]) < 50:
                log.warning(f"  Article text too short ({len(content['text']) if content['text'] else 0} chars)")
                dl_log["failed"].append({"url": url, "reason": "text too short"})
                save_download_log(dl_log)
                errors += 1
                time.sleep(delay)
                continue

            # Save HTML to NAS
            html_filename = f"{slug}.html"
            nas_html_path = os.path.join(NAS_YAVOH_DIR, html_filename)

            # Build a simple HTML document with the extracted text
            html_content = f"""<!DOCTYPE html>
<html>
<head><title>{content['title'] or slug}</title></head>
<body>
<h1>{content['title'] or slug}</h1>
{content['text']}
</body>
</html>"""

            with open(nas_html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            log.info(f"  Saved HTML to NAS: {nas_html_path}")

            # stored_path relative to /mnt/library/
            stored_path = f"religious/lionlamb/yavoh/{html_filename}"

            word_count = len(content["text"].split())
            title = content["title"] or article.get("title") or slug.replace("-", " ").title()

            # Build raw JSON
            raw_item = {
                "text": content["text"],
                "filename": html_filename,
                "stored_path": stored_path,
                "mime_type": "text/html",
                "source_name": SOURCE_NAME,
                "title": title,
                "teacher": content.get("author") or TEACHER_DEFAULT,
                "collection": COLLECTION_NAME,
                "content_type": "article",
                "url": url,
                "topics": content.get("tags", []),
                "metadata": {
                    "theological_stream": THEOLOGICAL_STREAM,
                    "scripture_refs": content.get("scripture_refs", []),
                    "language": "en",
                    "original_format": "html",
                    "word_count": word_count,
                    "tags": content.get("tags", []),
                },
                "copyright_note": "Personal research use only. Content from Lion & Lamb Ministries.",
            }

            if content.get("date"):
                raw_item["date"] = content["date"]

            # Write raw JSON
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(raw_item, f, indent=2, ensure_ascii=False)

            log.info(f"  OK: {word_count} words → {output_filename}")

            dl_log["downloaded"].append(url)
            save_download_log(dl_log)
            success += 1

        except Exception as e:
            log.error(f"  Error: {e}")
            dl_log["failed"].append({"url": url, "reason": str(e)})
            save_download_log(dl_log)
            errors += 1

        time.sleep(delay)

    log.info(f"Done: {success} downloaded, {errors} errors, {len(articles) - success - errors} skipped")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="YAVOH Magazine scraper — yavohmagazine.com"
    )
    parser.add_argument(
        "--discover", action="store_true",
        help="Discover all articles via pagination and build manifest"
    )
    parser.add_argument(
        "--download", action="store_true",
        help="Download articles and write raw JSON"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max articles to download"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Download all articles (use with --download)"
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
        print(f"  Articles: {m['total_articles']}")
        print(f"  Pages crawled: {m['pages_crawled']}")
        # Show a few sample titles
        for a in m["articles"][:10]:
            print(f"    - {a.get('title', a['slug'])}")
        if len(m["articles"]) > 10:
            print(f"    ... and {len(m['articles']) - 10} more")
        return

    if args.discover:
        discover(delay=args.delay)
    elif args.download:
        if not args.all and not args.limit:
            parser.error("Specify --all or --limit N with --download")
        download_articles(limit=args.limit, delay=args.delay)
    else:
        parser.error("Specify --discover or --download")


if __name__ == "__main__":
    main()
