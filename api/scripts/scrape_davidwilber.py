#!/usr/bin/env python3
"""
Scrape all blog articles from davidwilber.com and save as clean markdown.

Run: python3 scrape_davidwilber.py [--output-dir /path/to/save]

Requires: pip install requests beautifulsoup4 markdownify
Default output: ./davidwilber_articles/
"""

import os
import re
import sys
import time
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup, Comment
    from markdownify import markdownify as md
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install requests beautifulsoup4 markdownify")
    sys.exit(1)

BASE_URL = "https://davidwilber.com"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
}


def get_article_urls_from_sitemap() -> list[str]:
    """Fetch sitemap.xml and extract all /articles/* URLs."""
    print("Fetching sitemap...")
    try:
        resp = requests.get(SITEMAP_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Failed to fetch sitemap: {e}")
        return []

    # Squarespace sitemaps may have nested sitemap indexes
    urls = []
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError:
        print("  Failed to parse sitemap XML")
        return []

    # Handle sitemap namespace
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    # Check if this is a sitemap index (has <sitemap> children)
    sitemap_refs = root.findall(".//sm:sitemap/sm:loc", ns)
    if sitemap_refs:
        print(f"  Found sitemap index with {len(sitemap_refs)} sub-sitemaps")
        for ref in sitemap_refs:
            sub_url = ref.text.strip()
            try:
                sub_resp = requests.get(sub_url, headers=HEADERS, timeout=30)
                sub_resp.raise_for_status()
                sub_root = ET.fromstring(sub_resp.content)
                for loc in sub_root.findall(".//sm:loc", ns):
                    url = loc.text.strip()
                    if "/articles/" in url and "/tag/" not in url and "/category/" not in url:
                        urls.append(url)
            except Exception as e:
                print(f"  Failed to fetch sub-sitemap {sub_url}: {e}")
            time.sleep(0.5)
    else:
        # Direct sitemap with <url> entries
        for loc in root.findall(".//sm:loc", ns):
            url = loc.text.strip()
            if "/articles/" in url and "/tag/" not in url and "/category/" not in url:
                urls.append(url)

    # Deduplicate and filter out the bare /articles page
    urls = sorted(set(u for u in urls if u != f"{BASE_URL}/articles"))
    print(f"  Found {len(urls)} article URLs")
    return urls


def extract_article(html: str, url: str) -> dict:
    """Extract article content, title, date, and metadata from HTML."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove scripts, styles, nav, footer, comments, forms
    for tag in soup.find_all(["script", "style", "nav", "footer", "form", "iframe", "noscript"]):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Try to get title
    title = ""
    # Squarespace article titles are typically in h1 or meta
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)

    if not title:
        og_title = soup.find("meta", property="og:title")
        if og_title:
            title = og_title.get("content", "")

    if not title:
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True).replace(" — David Wilber", "")

    # Try to get date
    date = ""
    time_tag = soup.find("time")
    if time_tag:
        date = time_tag.get("datetime", "") or time_tag.get_text(strip=True)

    if not date:
        meta_date = soup.find("meta", property="article:published_time")
        if meta_date:
            date = meta_date.get("content", "")

    # Try to get description
    description = ""
    meta_desc = soup.find("meta", property="og:description")
    if meta_desc:
        description = meta_desc.get("content", "")

    # Extract main article content
    # Squarespace typically uses .entry-content, .sqs-block-content, or article tag
    content_el = None
    for selector in [
        "article .entry-content",
        "article .sqs-layout",
        ".blog-item-content",
        "article",
        ".entry-content",
        "main .sqs-layout",
    ]:
        content_el = soup.select_one(selector)
        if content_el:
            break

    if not content_el:
        # Fallback: use the main content area
        content_el = soup.find("main") or soup.find("body")

    # Remove sidebar elements, share buttons, newsletter forms, related articles
    if content_el:
        for sel in [
            ".blog-item-meta",
            ".share-buttons",
            ".sqs-block-newsletter",
            ".related-posts",
            ".squarespace-social-buttons",
            '[data-block-type="51"]',  # newsletter blocks
            ".blog-item-comments",
        ]:
            for el in content_el.select(sel):
                el.decompose()

    # Convert to markdown
    if content_el:
        # Remove images before converting (markdownify doesn't allow both strip and convert)
        for img in content_el.find_all("img"):
            img.decompose()
        content_md = md(
            str(content_el),
            heading_style="ATX",
        )
    else:
        content_md = ""

    # Clean up excessive whitespace
    content_md = re.sub(r"\n{4,}", "\n\n\n", content_md)
    content_md = content_md.strip()

    return {
        "title": title,
        "date": date,
        "description": description,
        "url": url,
        "content": content_md,
    }


def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:80].strip("-")


def scrape_articles(output_dir: str, delay: float = 1.5):
    """Main scraping function."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Step 1: Discover article URLs
    urls = get_article_urls_from_sitemap()

    if not urls:
        print("\nNo articles found via sitemap. Trying fallback discovery...")
        # Fallback: known article slugs from search results
        urls = get_fallback_urls()

    total = len(urls)
    if total == 0:
        print("No article URLs found. Exiting.")
        return

    print(f"\nScraping {total} articles to {out.resolve()}\n")

    success = 0
    failed = []
    articles_index = []

    for i, url in enumerate(urls, 1):
        slug = url.rstrip("/").split("/")[-1]
        filepath = out / f"{slug}.md"

        if filepath.exists():
            print(f"[{i}/{total}] SKIP (exists): {slug}")
            success += 1
            # Try to extract title from existing file for index
            try:
                first_line = filepath.read_text(encoding="utf-8").split("\n")[0]
                title = first_line.replace("# ", "")
            except Exception:
                title = slug
            articles_index.append({"title": title, "slug": slug, "url": url})
            continue

        print(f"[{i}/{total}] Scraping: {slug}...", end=" ", flush=True)

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()

            article = extract_article(resp.text, url)

            if not article["content"]:
                print("WARN (no content extracted)")
                failed.append((slug, "No content extracted"))
                continue

            # Build markdown file with frontmatter
            md_content = f"# {article['title']}\n\n"
            md_content += f"**Author:** David Wilber\n"
            if article["date"]:
                md_content += f"**Date:** {article['date']}\n"
            md_content += f"**Source:** [{url}]({url})\n"
            if article["description"]:
                md_content += f"\n> {article['description']}\n"
            md_content += f"\n---\n\n"
            md_content += article["content"]

            filepath.write_text(md_content, encoding="utf-8")
            size_kb = len(md_content.encode("utf-8")) / 1024
            print(f"OK ({size_kb:.1f} KB)")
            success += 1

            articles_index.append({
                "title": article["title"],
                "date": article["date"],
                "slug": slug,
                "url": url,
            })

        except requests.RequestException as e:
            print(f"FAILED: {e}")
            failed.append((slug, str(e)))

        # Be polite
        if i < total:
            time.sleep(delay)

    # Write index file
    index_path = out / "INDEX.md"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("# David Wilber — Article Index\n\n")
        f.write(f"**Source:** [davidwilber.com]({BASE_URL})\n")
        f.write(f"**Scraped:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Total articles:** {success}/{total}\n\n---\n\n")
        for art in sorted(articles_index, key=lambda a: a.get("date", ""), reverse=True):
            date_str = f" ({art['date'][:10]})" if art.get("date") else ""
            f.write(f"- [{art['title']}]({art['slug']}.md){date_str}\n")

    # Summary
    print(f"\n{'='*60}")
    print(f"Complete: {success}/{total} articles scraped")
    print(f"Location: {out.resolve()}")
    print(f"Index:    {index_path}")
    if failed:
        print(f"\nFailed ({len(failed)}):")
        for name, err in failed:
            print(f"  - {name}: {err}")


def get_fallback_urls() -> list[str]:
    """Fallback list of known article URLs if sitemap fails."""
    slugs = [
        "does-colossians-2v16-17-abolish-the-sabbath-and-festivals",
        "choose-gratitude-living-out-gods-will-in-all-circumstances",
        "the-holy-spirits-divine-nature-and-personhood-in-hebrews",
        "sabbath-observance-in-luke-acts",
        "sex-on-the-sabbath-does-it-violate-the-commandment",
        "peters-warning-about-the-antinomians-who-misinterpret-pauls-letters",
        "the-law-of-moses-vs-the-law-of-christ",
        "the-divine-son-exploring-the-messiahs-deity-in-hebrews-1",
        "the-book-of-jubilees-is-not-inspired-scripture",
        "the-messiahs-preexistence-and-divinity-in-philippians-2v5-11",
        "does-ephesians-2v15-say-that-christ-abolished-the-law-of-moses",
        "yes-leviticus-18v22-explicitly-prohibits-homosexual-activity",
        "did-jesus-reject-the-torahs-dietary-laws-mark-7v1-23",
        "addressing-r-l-solbergs-disappointing-mischaracterization-of-me",
        "does-peter-call-jesus-god-in-2-peter-1v1",
        "five-reasons-christians-should-keep-torah",
        "polygamy-harms-men-women-and-children",
        "understanding-the-torahs-polygamy-regulations",
        "does-the-torah-prohibit-polygamy",
        "the-problem-with-hebrew-word-pictures",
        "when-a-biblical-day-begins-and-ends",
        "follow-the-cloud",
        "a-season-of-teshuvah",
        "jesus-saved-israel-out-of-egypt-jude-5",
        "seven-ways-to-keep-the-sabbath",
        "debate-recap-should-christians-keep-the-torah",
        "matthew-nolan-and-david-perrys-melchizedek-doctrine-subtracting-from-torah",
        "is-yeshua-god-part-1-the-son-as-creator",
        "should-we-submit-to-our-wives-ephesians-5v22",
        "what-does-abraham-teach-us-about-hospitality",
        "the-days-of-noah",
        "how-to-identify-a-false-teacher",
        "keep-your-word",
        "judge-not",
        "is-christmas-pagan",
        "responding-to-christian-truthers-was-paul-a-false-apostle",
        "responding-to-christian-truthers-questioning-historicity-of-jesus",
    ]
    return [f"{BASE_URL}/articles/{s}" for s in slugs]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape David Wilber's blog articles as markdown"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="./davidwilber_articles",
        help="Directory to save articles (default: ./davidwilber_articles)",
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=1.5,
        help="Seconds between requests (default: 1.5)",
    )
    args = parser.parse_args()
    scrape_articles(args.output_dir, args.delay)
