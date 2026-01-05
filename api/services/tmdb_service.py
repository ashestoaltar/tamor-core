# services/tmdb_service.py
import time
import random
import re
import requests
from requests import Response

from core.config import TMDB_API_KEY, TMDB_BASE_URL, TMDB_IMAGE_BASE


_SESSION = requests.Session()

# Conservative defaults to prevent burst failures
_MAX_RETRIES = 6
_BASE_BACKOFF = 0.6  # seconds
_TIMEOUT = 8         # seconds

# Match trailing year patterns:
#   "Title 1946"
#   "Title (1946)"
#   "Title [1946]"
_YEAR_AT_END_RE = re.compile(r"^(.*?)(?:\s*[\(\[]?(\d{4})[\)\]]?)\s*$")


def _sleep_with_jitter(seconds: float) -> None:
    # small jitter prevents thundering herd
    time.sleep(seconds + random.uniform(0, 0.25))


def _request_with_retry(url: str, *, params: dict) -> Response:
    """
    Retries on:
      - 429 (rate limit) using Retry-After when present
      - 5xx
      - network timeouts / connection errors
    Raises if all retries exhausted.
    """
    last_exc: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            resp = _SESSION.get(url, params=params, timeout=_TIMEOUT)

            # Handle rate limit
            if resp.status_code == 429:
                ra = resp.headers.get("Retry-After")
                if ra:
                    try:
                        wait = float(ra)
                    except Exception:
                        wait = _BASE_BACKOFF * (2 ** attempt)
                else:
                    wait = _BASE_BACKOFF * (2 ** attempt)

                _sleep_with_jitter(min(wait, 15))
                continue

            # Retry on transient server errors
            if 500 <= resp.status_code <= 599:
                wait = _BASE_BACKOFF * (2 ** attempt)
                _sleep_with_jitter(min(wait, 10))
                continue

            resp.raise_for_status()
            return resp

        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
            wait = _BASE_BACKOFF * (2 ** attempt)
            _sleep_with_jitter(min(wait, 10))
            continue
        except Exception as e:
            # Non-retryable or unexpected
            last_exc = e
            break

    if last_exc:
        raise last_exc
    raise RuntimeError("TMDb request failed with unknown error")


def _split_title_year(q: str) -> tuple[str, str | None]:
    """
    Split "Title 1946" or "Title (1946)" into ("Title", "1946").
    If it doesn't look like a trailing year, returns (q, None).
    """
    q = (q or "").strip()
    if not q:
        return "", None
    m = _YEAR_AT_END_RE.match(q)
    if not m:
        return q, None
    title = (m.group(1) or "").strip()
    year = (m.group(2) or "").strip()
    if not title:
        return q, None
    return title, year


def tmdb_lookup_movie(query: str) -> dict:
    """
    Returns:
      { tmdb_id, imdb_id, poster, year, overview, title }
    """
    if not TMDB_API_KEY:
        return {}

    query = (query or "").strip()
    if not query:
        return {}

    try:
        title, year = _split_title_year(query)

        # 1) Try search with year as an actual param (much more reliable)
        params = {"api_key": TMDB_API_KEY, "query": title}
        if year:
            params["year"] = year

        search_resp = _request_with_retry(
            f"{TMDB_BASE_URL}/search/movie",
            params=params,
        )
        results = (search_resp.json().get("results") or [])

        # 2) Fallback: if year-filtered search returns nothing, retry without year
        if not results and year:
            search_resp = _request_with_retry(
                f"{TMDB_BASE_URL}/search/movie",
                params={"api_key": TMDB_API_KEY, "query": title},
            )
            results = (search_resp.json().get("results") or [])

        if not results:
            return {}

        m = results[0]
        tmdb_id = m.get("id")
        poster = m.get("poster_path")
        release_year = (m.get("release_date") or "")[:4]
        overview = m.get("overview") or ""
        resolved_title = m.get("title") or m.get("name") or title
        resolved_year = release_year or (year or "")

        imdb_id = None
        if tmdb_id:
            detail_resp = _request_with_retry(
                f"{TMDB_BASE_URL}/movie/{tmdb_id}",
                params={"api_key": TMDB_API_KEY, "append_to_response": "external_ids"},
            )
            external_ids = (detail_resp.json().get("external_ids") or {})
            imdb_id = external_ids.get("imdb_id")

        return {
            "tmdb_id": tmdb_id,
            "imdb_id": imdb_id,
            "poster": (TMDB_IMAGE_BASE + poster) if poster else None,
            "year": resolved_year,
            "overview": overview,
            "title": resolved_title,
        }

    except Exception as e:
        print("TMDb lookup failed for", query, "->", e)
        return {}


def tmdb_search_candidates(query: str, max_results: int = 5) -> list[dict]:
    """
    Returns list of candidates:
      { tmdb_id, imdb_id, title, year, overview, poster }
    """
    if not TMDB_API_KEY:
        return []

    query = (query or "").strip()
    if not query:
        return []

    try:
        title, year = _split_title_year(query)

        # Prefer year param if we can infer it.
        params = {"api_key": TMDB_API_KEY, "query": title}
        if year:
            params["year"] = year

        search_resp = _request_with_retry(
            f"{TMDB_BASE_URL}/search/movie",
            params=params,
        )
        results = (search_resp.json().get("results") or [])[:max_results]

        # If year constrained too hard, broaden.
        if not results and year:
            search_resp = _request_with_retry(
                f"{TMDB_BASE_URL}/search/movie",
                params={"api_key": TMDB_API_KEY, "query": title},
            )
            results = (search_resp.json().get("results") or [])[:max_results]

        if not results:
            return []

        candidates: list[dict] = []
        for m in results:
            tmdb_id = m.get("id")
            if not tmdb_id:
                continue

            cand_title = m.get("title") or m.get("name") or title
            release_date = m.get("release_date") or ""
            cand_year = release_date.split("-")[0] if release_date else (year or "")

            overview = m.get("overview") or ""
            poster_path = m.get("poster_path") or ""
            poster_url = (TMDB_IMAGE_BASE + poster_path) if poster_path else None

            imdb_id = None
            try:
                detail_resp = _request_with_retry(
                    f"{TMDB_BASE_URL}/movie/{tmdb_id}",
                    params={"api_key": TMDB_API_KEY, "append_to_response": "external_ids"},
                )
                external_ids = (detail_resp.json().get("external_ids") or {})
                imdb_id = external_ids.get("imdb_id")
            except Exception as inner_e:
                print("TMDb detail lookup failed for", tmdb_id, "->", inner_e)

            candidates.append(
                {
                    "tmdb_id": tmdb_id,
                    "imdb_id": imdb_id,
                    "title": cand_title,
                    "year": cand_year,
                    "overview": overview,
                    "poster": poster_url,
                }
            )

        return candidates
    except Exception as e:
        print("TMDb candidate search failed for", query, "->", e)
        return []

