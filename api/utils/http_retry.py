# api/utils/http_retry.py
"""
HTTP POST with retry for rate limits and transient errors.

Shared utility for all providers that make direct HTTP requests.
Not needed for Ollama (localhost) or SDK-based providers.

Usage:
    from utils.http_retry import post_with_retry

    response = post_with_retry(
        url="https://api.anthropic.com/v1/messages",
        json=payload,
        headers=headers,
        timeout=120,
    )
    data = response.json()
"""

import logging
import time
import requests
from typing import Optional

logger = logging.getLogger(__name__)


def post_with_retry(
    url: str,
    json: dict,
    headers: dict,
    timeout: int = 120,
    max_retries: int = 3,
) -> requests.Response:
    """
    POST with automatic retry for rate limits and transient server errors.

    Retry behavior:
    - 429 (rate limit): Respects Retry-After header, falls back to exponential backoff
    - 5xx (server error): Exponential backoff
    - Connection errors: Exponential backoff
    - 4xx (client error): No retry (caller's problem)
    - Timeout: No retry (raises immediately)

    Args:
        url: Endpoint URL
        json: Request payload
        headers: HTTP headers
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts

    Returns:
        requests.Response on success

    Raises:
        RuntimeError: On timeout, client errors, or exhausted retries
    """
    last_response = None

    for attempt in range(max_retries):
        try:
            response = requests.post(
                url, json=json, headers=headers, timeout=timeout
            )

            # Rate limited — back off and retry
            if response.status_code == 429:
                retry_after = response.headers.get("retry-after")
                if retry_after:
                    try:
                        wait = int(retry_after)
                    except ValueError:
                        wait = min(2 ** attempt * 2, 30)
                else:
                    wait = min(2 ** attempt * 2, 30)

                logger.info(
                    f"Rate limited by {url}, waiting {wait}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait)
                last_response = response
                continue

            # Server error — retry with backoff
            if response.status_code >= 500:
                wait = 2 ** attempt
                logger.warning(
                    f"Server error {response.status_code} from {url}, "
                    f"retrying in {wait}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait)
                last_response = response
                continue

            # Client error or success — return immediately
            response.raise_for_status()
            return response

        except requests.ConnectionError as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning(
                    f"Connection error to {url}, retrying in {wait}s: {e}"
                )
                time.sleep(wait)
                continue
            raise RuntimeError(
                f"Connection to {url} failed after {max_retries} attempts: {e}"
            )

        except requests.Timeout:
            raise RuntimeError(f"Request to {url} timed out after {timeout}s")

        except requests.HTTPError as e:
            # Extract provider-specific error message if available
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", {}).get("message", str(e))
            except Exception:
                error_msg = str(e)
            raise RuntimeError(f"API error from {url}: {error_msg}")

    # Exhausted retries
    status = last_response.status_code if last_response else "unknown"
    raise RuntimeError(
        f"Request to {url} failed after {max_retries} retries "
        f"(last status: {status})"
    )
