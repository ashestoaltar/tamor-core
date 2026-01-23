"""
Web Fetch Reference Plugin

Phase 6.3: Plugin Framework

Fetch and extract content from URLs as reference material.
Explicit user action only - never silently fetches during chat.
"""

import logging
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict
from html.parser import HTMLParser

from plugins import ReferencePlugin, ReferenceItem, ReferenceResult, FetchResult

logger = logging.getLogger(__name__)


class HTMLTextExtractor(HTMLParser):
    """Simple HTML to text converter."""

    def __init__(self):
        super().__init__()
        self.result = []
        self.skip_tags = {"script", "style", "head", "meta", "link", "noscript"}
        self.current_tag = None
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        if tag in self.skip_tags:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self.skip_tags and self.skip_depth > 0:
            self.skip_depth -= 1
        if tag in {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"}:
            self.result.append("\n")
        self.current_tag = None

    def handle_data(self, data):
        if self.skip_depth == 0:
            text = data.strip()
            if text:
                self.result.append(text + " ")

    def get_text(self):
        text = "".join(self.result)
        # Clean up multiple whitespace
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r" +", " ", text)
        return text.strip()


class WebFetchReference(ReferencePlugin):
    """
    Fetch and extract content from URLs as reference.

    Guardrails (per user requirements):
    - Explicit user action only ("Add URL as reference")
    - Store snapshot: text + URL + fetched timestamp
    - Never silently fetch during chat
    - Returns content for review before any import
    """

    id = "web-fetch"
    name = "Web Fetch"
    type = "reference"
    description = "Fetch and extract content from URLs as reference"

    config_schema = {
        "url": {
            "type": "string",
            "required": True,
            "description": "URL to fetch",
        },
        "extract_text": {
            "type": "boolean",
            "default": True,
            "description": "Extract readable text from HTML",
        },
    }

    def validate_config(self, config: Dict) -> bool:
        """Validate configuration."""
        url = config.get("url", "")
        if not url:
            return False
        # Basic URL validation
        if not url.startswith(("http://", "https://")):
            return False
        return True

    def list_items(self, config: Dict) -> ReferenceResult:
        """
        List available items (for web fetch, this returns a single item representing the URL).

        Args:
            config: Plugin configuration with url

        Returns:
            ReferenceResult with single item representing the URL
        """
        url = config.get("url", "")

        if not self.validate_config(config):
            return ReferenceResult(
                success=False,
                error="Invalid URL. Must start with http:// or https://",
            )

        # Create a single reference item for the URL
        item = ReferenceItem(
            id="url-0",
            title=url,
            path=url,
            content_preview="[Click to fetch content from this URL]",
            mime_type="text/html",
            metadata={
                "url": url,
                "type": "web_url",
            },
        )

        return ReferenceResult(
            success=True,
            items=[item],
            total=1,
            metadata={"url": url},
        )

    def fetch_item(self, item_id: str, config: Dict) -> FetchResult:
        """
        Fetch full content from the URL.

        Args:
            item_id: Identifier of the item (ignored for web fetch, uses URL from config)
            config: Plugin configuration with url and extract_text

        Returns:
            FetchResult with fetched content
        """
        url = config.get("url", "")
        extract_text = config.get("extract_text", True)

        if not self.validate_config(config):
            return FetchResult(
                success=False,
                error="Invalid URL",
            )

        try:
            # Fetch the URL
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; TamorReference/1.0)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            request = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(request, timeout=30) as response:
                # Get content type
                content_type = response.headers.get("Content-Type", "")
                charset = "utf-8"

                # Extract charset from content-type if present
                if "charset=" in content_type:
                    charset = content_type.split("charset=")[-1].split(";")[0].strip()

                # Read and decode content
                raw_content = response.read()
                try:
                    html_content = raw_content.decode(charset, errors="ignore")
                except (LookupError, UnicodeDecodeError):
                    html_content = raw_content.decode("utf-8", errors="ignore")

                # Extract title from HTML
                title = self._extract_title(html_content) or url

                # Extract text if requested
                if extract_text and "text/html" in content_type.lower():
                    content = self._extract_text(html_content)
                else:
                    content = html_content

                fetched_at = datetime.now(timezone.utc).isoformat()

                logger.info(f"Fetched URL: {url} ({len(content)} chars)")

                return FetchResult(
                    success=True,
                    content=content,
                    title=title,
                    url=url,
                    fetched_at=fetched_at,
                    metadata={
                        "source": "web_fetch",
                        "content_type": content_type,
                        "content_length": len(content),
                        "raw_html_length": len(html_content),
                    },
                )

        except urllib.error.HTTPError as e:
            logger.error(f"HTTP error fetching {url}: {e.code} {e.reason}")
            return FetchResult(
                success=False,
                error=f"HTTP {e.code}: {e.reason}",
                url=url,
            )
        except urllib.error.URLError as e:
            logger.error(f"URL error fetching {url}: {e.reason}")
            return FetchResult(
                success=False,
                error=f"URL error: {e.reason}",
                url=url,
            )
        except TimeoutError:
            logger.error(f"Timeout fetching {url}")
            return FetchResult(
                success=False,
                error="Request timed out",
                url=url,
            )
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return FetchResult(
                success=False,
                error=str(e),
                url=url,
            )

    def _extract_title(self, html: str) -> str:
        """Extract title from HTML."""
        # Simple regex extraction
        match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_text(self, html: str) -> str:
        """Extract readable text from HTML."""
        try:
            extractor = HTMLTextExtractor()
            extractor.feed(html)
            return extractor.get_text()
        except Exception as e:
            logger.warning(f"Error extracting text from HTML: {e}")
            # Fall back to simple tag stripping
            text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text)
            return text.strip()
