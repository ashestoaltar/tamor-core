#!/usr/bin/env python3
"""
Scrape multiple pronomian author sources:
1. TorahApologetics.com (Jonathan A. Brown) - Weebly site
2. TheBarkingFox.wordpress.com (Albert McCarn) - WordPress blog
3. Szumskyj's Substack - Newsletter archive
4. Caldron Pool - Szumskyj articles

Run: python3 scrape_pronomian_sources.py [--source all|torah|fox|substack|caldron]
"""

import os
import re
import sys
import time
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup, Comment
    from markdownify import markdownify as md
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install requests beautifulsoup4 markdownify")
    sys.exit(1)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
}

BASE_OUTPUT = Path("/mnt/library/religious")


def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:80].strip("-")


def clean_html_to_md(soup_el, strip_images=True):
    """Convert BeautifulSoup element to clean markdown."""
    if not soup_el:
        return ""

    if strip_images:
        for img in soup_el.find_all("img"):
            img.decompose()

    # Remove scripts, styles, etc.
    for tag in soup_el.find_all(["script", "style", "nav", "footer", "form", "iframe", "noscript"]):
        tag.decompose()
    for comment in soup_el.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    content = md(str(soup_el), heading_style="ATX")
    content = re.sub(r"\n{4,}", "\n\n\n", content)
    return content.strip()


# =============================================================================
# 1. TORAH APOLOGETICS (Jonathan A. Brown) - Weebly
# =============================================================================

TORAH_APOL_BASE = "https://www.torahapologetics.com"
TORAH_APOL_PAGES = [
    ("language--word-studies", "Language & Word Studies"),
    ("history--culture", "History & Culture"),
    ("apologetics--daily-life", "Apologetics & Daily Life"),
    ("toward-a-messianic-creed", "Toward a Messianic Creed"),
]

def scrape_torah_apologetics(output_dir: Path):
    """Scrape TorahApologetics.com category pages."""
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n{'='*60}")
    print("Scraping TorahApologetics.com (Jonathan A. Brown)")
    print(f"Output: {output_dir}")
    print("="*60)

    articles = []

    for slug, title in TORAH_APOL_PAGES:
        url = f"{TORAH_APOL_BASE}/{slug}"
        filepath = output_dir / f"{slug}.md"

        print(f"\n[{title}] Fetching {url}...", end=" ", flush=True)

        if filepath.exists():
            print("SKIP (exists)")
            articles.append({"title": title, "slug": slug})
            continue

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            # Weebly uses #wsite-content for main content
            content_el = soup.select_one("#wsite-content")
            if not content_el:
                content_el = soup.select_one("main") or soup.find("body")

            # Remove sidebar, navigation, ads
            for sel in [".blog-sidebar", ".wsite-footer", ".wsite-header",
                       "[class*='social']", "[class*='share']", "[class*='ad']"]:
                for el in content_el.select(sel):
                    el.decompose()

            content_md = clean_html_to_md(content_el)

            if not content_md or len(content_md) < 200:
                print(f"WARN (minimal content: {len(content_md)} chars)")
                continue

            # Build markdown file
            md_content = f"# {title}\n\n"
            md_content += f"**Author:** Jonathan A. Brown\n"
            md_content += f"**Source:** [{url}]({url})\n"
            md_content += f"**Retrieved:** {datetime.now().strftime('%Y-%m-%d')}\n"
            md_content += f"\n---\n\n"
            md_content += content_md

            filepath.write_text(md_content, encoding="utf-8")
            size_kb = len(md_content.encode("utf-8")) / 1024
            print(f"OK ({size_kb:.1f} KB)")
            articles.append({"title": title, "slug": slug})

        except Exception as e:
            print(f"FAILED: {e}")

        time.sleep(1)

    # Write index
    write_index(output_dir, "Jonathan A. Brown — Torah Apologetics",
                TORAH_APOL_BASE, articles)

    return len(articles)


# =============================================================================
# 2. THE BARKING FOX (Albert McCarn) - WordPress
# =============================================================================

BARKING_FOX_FEED = "https://thebarkingfox.wordpress.com/feed/"
BARKING_FOX_BASE = "https://thebarkingfox.wordpress.com"

def get_wordpress_posts_from_feed(feed_url: str, max_pages: int = 10) -> list:
    """Get all posts from a WordPress RSS feed (paginated)."""
    posts = []

    for page in range(1, max_pages + 1):
        url = f"{feed_url}?paged={page}" if page > 1 else feed_url
        print(f"  Fetching feed page {page}...", end=" ", flush=True)

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code != 200:
                print(f"done (status {resp.status_code})")
                break

            root = ET.fromstring(resp.content)
            items = root.findall(".//item")

            if not items:
                print("done (no items)")
                break

            for item in items:
                title = item.find("title")
                link = item.find("link")
                pub_date = item.find("pubDate")
                creator = item.find("{http://purl.org/dc/elements/1.1/}creator")
                content = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")

                posts.append({
                    "title": title.text if title is not None else "Untitled",
                    "url": link.text if link is not None else "",
                    "date": pub_date.text if pub_date is not None else "",
                    "author": creator.text if creator is not None else "Albert J. McCarn",
                    "content_html": content.text if content is not None else "",
                })

            print(f"got {len(items)} posts")
            time.sleep(0.5)

        except Exception as e:
            print(f"error: {e}")
            break

    return posts


def scrape_barking_fox(output_dir: Path):
    """Scrape The Barking Fox WordPress blog via RSS + full page fetch."""
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n{'='*60}")
    print("Scraping TheBarkingFox.wordpress.com (Albert McCarn)")
    print(f"Output: {output_dir}")
    print("="*60)

    # Get posts from RSS feed
    print("\nFetching RSS feed...")
    posts = get_wordpress_posts_from_feed(BARKING_FOX_FEED, max_pages=50)
    print(f"Found {len(posts)} posts total")

    if not posts:
        print("No posts found!")
        return 0

    success = 0
    articles = []

    for i, post in enumerate(posts, 1):
        slug = slugify(post["title"])
        filepath = output_dir / f"{slug}.md"

        print(f"[{i}/{len(posts)}] {post['title'][:50]}...", end=" ", flush=True)

        if filepath.exists():
            print("SKIP")
            articles.append({"title": post["title"], "slug": slug, "date": post["date"]})
            success += 1
            continue

        # RSS often has only excerpts - fetch full page
        content_html = post["content_html"]
        if post["url"] and (not content_html or len(content_html) < 500):
            try:
                page_resp = requests.get(post["url"], headers=HEADERS, timeout=30)
                page_resp.raise_for_status()
                page_soup = BeautifulSoup(page_resp.text, "html.parser")

                # WordPress.com uses .entry-content
                content_el = (page_soup.select_one(".entry-content") or
                             page_soup.select_one("article .post-content") or
                             page_soup.select_one(".post-entry") or
                             page_soup.select_one("article"))

                if content_el:
                    content_html = str(content_el)
                time.sleep(0.5)  # Be polite
            except Exception as e:
                pass  # Fall back to RSS content

        if not content_html:
            print("SKIP (no content)")
            continue

        # Convert HTML content to markdown
        soup = BeautifulSoup(content_html, "html.parser")
        content_md = clean_html_to_md(soup)

        if not content_md or len(content_md) < 100:
            print("SKIP (empty)")
            continue

        # Parse date
        date_str = ""
        if post["date"]:
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(post["date"])
                date_str = dt.strftime("%Y-%m-%d")
            except:
                date_str = post["date"][:10] if len(post["date"]) >= 10 else ""

        # Build markdown file
        md_content = f"# {post['title']}\n\n"
        md_content += f"**Author:** {post['author']}\n"
        if date_str:
            md_content += f"**Date:** {date_str}\n"
        md_content += f"**Source:** [{post['url']}]({post['url']})\n"
        md_content += f"\n---\n\n"
        md_content += content_md

        filepath.write_text(md_content, encoding="utf-8")
        size_kb = len(md_content.encode("utf-8")) / 1024
        print(f"OK ({size_kb:.1f} KB)")

        articles.append({"title": post["title"], "slug": slug, "date": date_str})
        success += 1

    # Write index
    write_index(output_dir, "Albert J. McCarn — The Barking Fox",
                BARKING_FOX_BASE, articles)

    return success


# =============================================================================
# 3. SZUMSKYJ SUBSTACK
# =============================================================================

SUBSTACK_BASE = "https://the2ndreformationwithdrszumskyj.substack.com"
SUBSTACK_FEED = f"{SUBSTACK_BASE}/feed"

def scrape_szumskyj_substack(output_dir: Path):
    """Scrape Szumskyj's Substack via RSS feed."""
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n{'='*60}")
    print("Scraping Szumskyj's Substack")
    print(f"Output: {output_dir}")
    print("="*60)

    print("\nFetching RSS feed...")

    try:
        resp = requests.get(SUBSTACK_FEED, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch feed: {e}")
        return 0

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"Failed to parse feed: {e}")
        return 0

    items = root.findall(".//item")
    print(f"Found {len(items)} posts")

    if not items:
        return 0

    success = 0
    articles = []

    for i, item in enumerate(items, 1):
        title_el = item.find("title")
        link_el = item.find("link")
        pub_date_el = item.find("pubDate")
        content_el = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")

        title = title_el.text if title_el is not None else "Untitled"
        url = link_el.text if link_el is not None else ""
        date = pub_date_el.text if pub_date_el is not None else ""
        content_html = content_el.text if content_el is not None else ""

        slug = slugify(title)
        filepath = output_dir / f"{slug}.md"

        print(f"[{i}/{len(items)}] {title[:50]}...", end=" ", flush=True)

        if filepath.exists():
            print("SKIP")
            articles.append({"title": title, "slug": slug, "date": date})
            success += 1
            continue

        if not content_html:
            # Try fetching the full page
            if url:
                try:
                    page_resp = requests.get(url, headers=HEADERS, timeout=30)
                    page_soup = BeautifulSoup(page_resp.text, "html.parser")
                    content_el = page_soup.select_one(".body") or page_soup.select_one("article")
                    if content_el:
                        content_html = str(content_el)
                except:
                    pass

        if not content_html:
            print("SKIP (no content)")
            continue

        soup = BeautifulSoup(content_html, "html.parser")
        content_md = clean_html_to_md(soup)

        if not content_md:
            print("SKIP (empty)")
            continue

        # Parse date
        date_str = ""
        if date:
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(date)
                date_str = dt.strftime("%Y-%m-%d")
            except:
                pass

        # Build markdown
        md_content = f"# {title}\n\n"
        md_content += f"**Author:** Dr. Benjamin Szumskyj\n"
        if date_str:
            md_content += f"**Date:** {date_str}\n"
        md_content += f"**Source:** [{url}]({url})\n"
        md_content += f"\n---\n\n"
        md_content += content_md

        filepath.write_text(md_content, encoding="utf-8")
        size_kb = len(md_content.encode("utf-8")) / 1024
        print(f"OK ({size_kb:.1f} KB)")

        articles.append({"title": title, "slug": slug, "date": date_str})
        success += 1

    write_index(output_dir, "Dr. Benjamin Szumskyj — The 2nd Reformation",
                SUBSTACK_BASE, articles)

    return success


# =============================================================================
# 4. CALDRON POOL (Szumskyj articles)
# =============================================================================

CALDRON_AUTHOR_URL = "https://caldronpool.com/author/drbenjaminszumskyj/"

def scrape_caldron_pool(output_dir: Path):
    """Scrape Szumskyj's articles from Caldron Pool."""
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n{'='*60}")
    print("Scraping Caldron Pool (Szumskyj articles)")
    print(f"Output: {output_dir}")
    print("="*60)

    print(f"\nFetching author page: {CALDRON_AUTHOR_URL}")

    try:
        resp = requests.get(CALDRON_AUTHOR_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"Failed: {e}")
        return 0

    soup = BeautifulSoup(resp.text, "html.parser")

    # Find article links
    article_links = []
    for a in soup.select("article a, .post a, h2 a, .entry-title a"):
        href = a.get("href", "")
        if href and "caldronpool.com" in href and href not in [l[0] for l in article_links]:
            title = a.get_text(strip=True)
            if title and len(title) > 10:
                article_links.append((href, title))

    print(f"Found {len(article_links)} article links")

    if not article_links:
        return 0

    success = 0
    articles = []

    for i, (url, title) in enumerate(article_links, 1):
        slug = slugify(title)
        # Save to substack folder since it's same author
        filepath = output_dir / f"caldron-{slug}.md"

        print(f"[{i}/{len(article_links)}] {title[:50]}...", end=" ", flush=True)

        if filepath.exists():
            print("SKIP")
            articles.append({"title": title, "slug": f"caldron-{slug}"})
            success += 1
            continue

        try:
            page_resp = requests.get(url, headers=HEADERS, timeout=30)
            page_resp.raise_for_status()

            page_soup = BeautifulSoup(page_resp.text, "html.parser")

            # Find content
            content_el = (page_soup.select_one(".entry-content") or
                         page_soup.select_one("article") or
                         page_soup.select_one(".post-content"))

            if not content_el:
                print("SKIP (no content)")
                continue

            content_md = clean_html_to_md(content_el)

            if not content_md or len(content_md) < 200:
                print("SKIP (minimal)")
                continue

            # Try to get date
            date_str = ""
            time_el = page_soup.find("time")
            if time_el:
                date_str = time_el.get("datetime", "")[:10]

            md_content = f"# {title}\n\n"
            md_content += f"**Author:** Dr. Benjamin Szumskyj\n"
            if date_str:
                md_content += f"**Date:** {date_str}\n"
            md_content += f"**Source:** [{url}]({url})\n"
            md_content += f"**Publication:** Caldron Pool\n"
            md_content += f"\n---\n\n"
            md_content += content_md

            filepath.write_text(md_content, encoding="utf-8")
            size_kb = len(md_content.encode("utf-8")) / 1024
            print(f"OK ({size_kb:.1f} KB)")

            articles.append({"title": title, "slug": f"caldron-{slug}", "date": date_str})
            success += 1

        except Exception as e:
            print(f"FAILED: {e}")

        time.sleep(1)

    return success


# =============================================================================
# UTILITY
# =============================================================================

def write_index(output_dir: Path, title: str, base_url: str, articles: list):
    """Write an index.md file for the scraped articles."""
    index_path = output_dir / "INDEX.md"

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(f"**Source:** [{base_url}]({base_url})\n")
        f.write(f"**Scraped:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Total articles:** {len(articles)}\n\n---\n\n")

        # Sort by date if available
        sorted_articles = sorted(articles,
                                key=lambda a: a.get("date", ""),
                                reverse=True)

        for art in sorted_articles:
            date_str = f" ({art['date'][:10]})" if art.get("date") else ""
            f.write(f"- [{art['title']}]({art['slug']}.md){date_str}\n")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Scrape pronomian author sources"
    )
    parser.add_argument(
        "--source", "-s",
        choices=["all", "torah", "fox", "substack", "caldron"],
        default="all",
        help="Which source to scrape (default: all)",
    )
    args = parser.parse_args()

    results = {}

    if args.source in ["all", "torah"]:
        count = scrape_torah_apologetics(BASE_OUTPUT / "torahapologetics")
        results["Torah Apologetics"] = count

    if args.source in ["all", "fox"]:
        count = scrape_barking_fox(BASE_OUTPUT / "barkingfox")
        results["Barking Fox"] = count

    if args.source in ["all", "substack"]:
        count = scrape_szumskyj_substack(BASE_OUTPUT / "szumskyj-substack")
        results["Szumskyj Substack"] = count

    if args.source in ["all", "caldron"]:
        # Save Caldron Pool articles to substack folder (same author)
        count = scrape_caldron_pool(BASE_OUTPUT / "szumskyj-substack")
        results["Caldron Pool"] = count

    # Summary
    print(f"\n{'='*60}")
    print("SCRAPING COMPLETE")
    print("="*60)
    for source, count in results.items():
        print(f"  {source}: {count} articles")
    print(f"\nTotal: {sum(results.values())} articles")


if __name__ == "__main__":
    main()
