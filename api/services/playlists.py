import json
import os
import re
import time
import requests
from typing import Any

from core.config import (
    PLAYLIST_DIR,
    CHRISTMAS_PLAYLIST_FILE,
    TMDB_CACHE,
    TMDB_BASE_URL,
    TMDB_API_KEY,
)
from .tmdb_service import tmdb_lookup_movie


# TMDb image base (HTTPS) — prevents mixed-content "about:blank#blocked"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/"
TMDB_POSTER_SIZE = "w342"

# Optional on-disk cache (safe even if TMDB_CACHE is already persistent elsewhere)
TMDB_CACHE_FILE = os.path.join(PLAYLIST_DIR, "tmdb_cache.json")


DEFAULT_CHRISTMAS_MOVIES = [
    {
        "id": "tt0218967",
        "type": "movie",
        "name": "The Family Man",
        "tmdb_query": "The Family Man 2000",
    },
    # ... your full list lives in /data/playlists/christmas.json ...
]


# ----------------------------
# Basic helpers
# ----------------------------

_YEAR_PAREN_RE = re.compile(r"\s*\((\d{4})\)\s*$")


def _parse_title_year_from_string(s: str) -> tuple[str, str]:
    """
    If string ends with " (YYYY)", split it into (title, year).
    Otherwise return (s, "").
    """
    if not s:
        return "", ""
    s = s.strip()
    m = _YEAR_PAREN_RE.search(s)
    if m:
        year = m.group(1)
        title = _YEAR_PAREN_RE.sub("", s).strip()
        return title, year
    return s, ""


def _normalize_movie_name(name: str) -> str:
    """
    Normalize a movie name for loose matching:
    - lowercased
    - strip trailing year in parentheses
    - trim whitespace and punctuation
    """
    if not name:
        return ""
    s = name.lower().strip()

    # Remove " (YYYY)" at the end if present
    if s.endswith(")"):
        idx = s.rfind("(")
        if idx != -1 and idx < len(s) - 2:
            year_part = s[idx + 1 : -1]
            if year_part.isdigit() and len(year_part) == 4:
                s = s[:idx].strip()

    s = s.strip(' "“”‘’\'.,!?')
    return s


def _build_tmdb_query(title: str, year: str | int | None) -> str:
    y = str(year).strip() if year else ""
    t = (title or "").strip()
    return f"{t} {y}".strip()


def _safe_https(url: str | None) -> str | None:
    if not url:
        return None
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    return u


# ----------------------------
# TMDb cache (supports dict or filepath in core.config)
# ----------------------------

def _load_disk_cache_into_memory() -> None:
    """
    If TMDB_CACHE is a dict, we can optionally merge an on-disk cache file into it.
    This is intentionally best-effort.
    """
    if not isinstance(TMDB_CACHE, dict):
        return
    try:
        if not os.path.exists(TMDB_CACHE_FILE):
            return
        with open(TMDB_CACHE_FILE, "r", encoding="utf-8") as f:
            disk = json.load(f) or {}
        if isinstance(disk, dict):
            # Don't overwrite existing keys in memory
            for k, v in disk.items():
                TMDB_CACHE.setdefault(k, v)
    except Exception:
        pass


def _persist_memory_cache_to_disk() -> None:
    """
    Best-effort persistence if TMDB_CACHE is in-memory dict.
    """
    if not isinstance(TMDB_CACHE, dict):
        return
    try:
        os.makedirs(PLAYLIST_DIR, exist_ok=True)
        with open(TMDB_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(TMDB_CACHE, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _cache_get(key: str) -> dict | None:
    if not key:
        return None

    # If TMDB_CACHE is a dict, use it.
    if isinstance(TMDB_CACHE, dict):
        _load_disk_cache_into_memory()
        v = TMDB_CACHE.get(key)
        return v.copy() if isinstance(v, dict) else None

    # If TMDB_CACHE is a string path, treat it as a JSON file.
    if isinstance(TMDB_CACHE, str) and TMDB_CACHE.strip():
        try:
            with open(TMDB_CACHE, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            v = data.get(key)
            return v.copy() if isinstance(v, dict) else None
        except Exception:
            return None

    return None


def _cache_set(key: str, value: dict) -> None:
    if not key or not isinstance(value, dict):
        return

    # Dict cache
    if isinstance(TMDB_CACHE, dict):
        TMDB_CACHE[key] = value
        _persist_memory_cache_to_disk()
        return

    # File cache
    if isinstance(TMDB_CACHE, str) and TMDB_CACHE.strip():
        try:
            path = TMDB_CACHE
            existing = {}
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f) or {}
            existing[key] = value
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


# ----------------------------
# Playlist load/save (fix mixed schema)
# ----------------------------

def load_christmas_playlist() -> list[dict]:
    """
    Loads christmas.json and keeps *both* legacy and newer schemas.

    Legacy example:
      { "id": "tt...", "name": "Title (Year)", "tmdb_query": "Title Year" }

    New/simple example:
      { "title": "Title", "year": 2000 }
    """
    try:
        with open(CHRISTMAS_PLAYLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f) or []
            cleaned: list[dict] = []
            for m in data:
                if not isinstance(m, dict):
                    continue
                if m.get("id") or m.get("title") or m.get("name"):
                    cleaned.append(m)
            return cleaned
    except FileNotFoundError:
        os.makedirs(PLAYLIST_DIR, exist_ok=True)
        with open(CHRISTMAS_PLAYLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CHRISTMAS_MOVIES, f, ensure_ascii=False, indent=2)
        return DEFAULT_CHRISTMAS_MOVIES.copy()
    except Exception as e:
        print("Failed to load christmas playlist:", e)
        return DEFAULT_CHRISTMAS_MOVIES.copy()


def save_christmas_playlist(movies: list[dict]) -> None:
    os.makedirs(PLAYLIST_DIR, exist_ok=True)
    with open(CHRISTMAS_PLAYLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(movies or [], f, ensure_ascii=False, indent=2)


# --- Generic multi-playlist helpers -----------------------------------------

def _playlist_file_for(slug: str) -> str:
    slug = (slug or "").lower().strip()
    if slug == "christmas":
        return CHRISTMAS_PLAYLIST_FILE
    os.makedirs(PLAYLIST_DIR, exist_ok=True)
    return os.path.join(PLAYLIST_DIR, f"{slug}.json")


def _load_generic_playlist(slug: str) -> list[dict]:
    slug = (slug or "").lower().strip()
    path = _playlist_file_for(slug)
    if slug == "christmas":
        return load_christmas_playlist()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or []
        cleaned: list[dict] = []
        for m in data:
            if not isinstance(m, dict):
                continue
            if m.get("id") or m.get("title") or m.get("name"):
                cleaned.append(m)
        return cleaned
    except FileNotFoundError:
        return []
    except Exception as e:
        print("Failed to load playlist", slug, "->", e)
        return []


def _save_generic_playlist(slug: str, movies: list[dict]) -> None:
    slug = (slug or "").lower().strip()
    path = _playlist_file_for(slug)
    if slug == "christmas":
        save_christmas_playlist(movies)
        return
    os.makedirs(PLAYLIST_DIR, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(movies or [], f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Failed to save playlist", slug, "->", e)


# ----------------------------
# Normalization + enrichment
# ----------------------------

def _normalize_playlist_item(item: dict) -> dict:
    """
    Converts any playlist row into a consistent internal form:
      - id (imdb) if known
      - title (no "(YYYY)")
      - year (string)
      - tmdb_query (title + year)
      - type (movie)
    """
    item = item or {}
    imdb_id = (item.get("id") or "").strip() if isinstance(item.get("id"), str) else ""
    raw_name = (item.get("name") or "").strip() if isinstance(item.get("name"), str) else ""
    raw_title = (item.get("title") or "").strip() if isinstance(item.get("title"), str) else ""
    raw_year = item.get("year")  # can be int or str

    title = raw_title
    year = str(raw_year).strip() if raw_year else ""

    if not title and raw_name:
        title, parsed_year = _parse_title_year_from_string(raw_name)
        if not year and parsed_year:
            year = parsed_year

    if not title:
        title = raw_name or "Unknown title"

    tmdb_query = item.get("tmdb_query")
    if not isinstance(tmdb_query, str) or not tmdb_query.strip():
        tmdb_query = _build_tmdb_query(title, year)

    return {
        "type": item.get("type") or "movie",
        "id": imdb_id or None,
        "title": title,
        "year": year or None,
        "tmdb_query": tmdb_query,
    }


def _enriched_from_tmdb_info(base: dict, info: dict) -> dict:
    """
    Create UI-ready enriched item.
    Adds tmdb_id/imdb_id as well (helps downstream routes).
    """
    title = info.get("title") or base.get("title") or "Unknown title"

    # IMPORTANT: ensure year never "disappears" if TMDb doesn't return one
    year = info.get("year") or base.get("year")

    overview = info.get("overview") or info.get("plot") or ""
    imdb_id = info.get("imdb_id") or base.get("id")
    tmdb_id = info.get("tmdb_id")

    poster = info.get("poster") or ""
    poster_path = info.get("poster_path") or ""

    if not poster and poster_path:
        poster = f"{TMDB_IMAGE_BASE}{TMDB_POSTER_SIZE}{poster_path}"

    poster = _safe_https(poster) if poster else None

    return {
        "type": "movie",
        "id": imdb_id,          # legacy/internal
        "imdb_id": imdb_id,     # explicit
        "tmdb_id": tmdb_id,
        "title": title,
        "year": year,
        "overview": overview,
        "poster": poster,
        "tmdb_query": base.get("tmdb_query"),
    }


def _enrich_movie_item(item: dict) -> dict:
    """
    Enrich a normalized playlist item.
    - Cache by IMDb id when present
    - Else cache by query string
    - Always tries TMDb lookup even without id
    """
    base = _normalize_playlist_item(item)
    imdb_id = base.get("id") or ""
    query = base.get("tmdb_query") or _build_tmdb_query(base.get("title"), base.get("year"))
    query_key = f"q:{_normalize_movie_name(query)}" if query else ""

    # 1) Cache by IMDb id first
    if imdb_id:
        cached = _cache_get(imdb_id)
        if cached:
            # ensure cached item never loses base year/title
            cached.setdefault("title", base.get("title"))
            cached.setdefault("year", base.get("year"))
            cached.setdefault("imdb_id", imdb_id)
            return _enriched_from_tmdb_info(base, cached)

    # 2) Cache by query key
    if query_key:
        cached = _cache_get(query_key)
        if cached:
            cached.setdefault("title", base.get("title"))
            cached.setdefault("year", base.get("year"))
            enriched = _enriched_from_tmdb_info(base, cached)
            if enriched.get("imdb_id"):
                _cache_set(enriched["imdb_id"], cached)
            return enriched

    # 3) Lookup via tmdb_service
    info: dict = {}
    try:
        info = tmdb_lookup_movie(query or base.get("title") or "")
    except Exception as e:
        print("TMDb enrich failed for", imdb_id or query, "->", e)
        info = {}

    if info:
        # Always backfill title/year from base if missing
        info.setdefault("title", base.get("title"))
        info.setdefault("year", base.get("year"))
        if imdb_id and not info.get("imdb_id"):
            info["imdb_id"] = imdb_id

        if query_key:
            _cache_set(query_key, info)
        resolved_imdb = info.get("imdb_id")
        if resolved_imdb:
            _cache_set(resolved_imdb, info)

        return _enriched_from_tmdb_info(base, info)

    # 4) Fallback: return normalized, UI-safe shape (year preserved)
    return {
        "type": "movie",
        "id": base.get("id"),
        "imdb_id": base.get("id"),
        "tmdb_id": None,
        "title": base.get("title"),
        "year": base.get("year"),
        "overview": "",
        "poster": None,
        "tmdb_query": base.get("tmdb_query"),
    }


def enrich_playlist_items(items: list[dict]) -> list[dict]:
    # tiny throttle to avoid bursts; search reliability is the bigger fix, but this helps too
    out: list[dict] = []
    for m in (items or []):
        out.append(_enrich_movie_item(m))
        time.sleep(0.10)
    return out


# ----------------------------
# Public API used by routes
# ----------------------------

def list_christmas_playlist() -> list[dict]:
    movies = load_christmas_playlist()
    return movies or []


def list_playlist(slug: str, *, enriched: bool = True) -> list[dict]:
    slug = (slug or "").lower().strip()
    if slug == "christmas":
        items = list_christmas_playlist()
    else:
        items = _load_generic_playlist(slug)

    return enrich_playlist_items(items) if enriched else (items or [])


def add_movie_to_christmas_by_title(title: str) -> str:
    title = title.strip()
    if not title:
        return "I need a movie title to add."

    info = tmdb_lookup_movie(title)
    imdb_id = info.get("imdb_id")
    year = info.get("year") or ""

    if not imdb_id:
        return f"I couldn't find a matching IMDb entry for “{title}” on TMDb."

    resolved_name = info.get("title") or title

    try:
        # (Optional) keep your original secondary lookup; but pass year correctly if we have it
        params = {"api_key": TMDB_API_KEY, "query": resolved_name}
        if year:
            params["year"] = year
        search_resp = requests.get(f"{TMDB_BASE_URL}/search/movie", params=params, timeout=5)
        search_resp.raise_for_status()
        results = search_resp.json().get("results") or []
        if results:
            m = results[0]
            resolved_name = m.get("title") or m.get("name") or resolved_name
            year = (m.get("release_date") or "")[:4] or year
    except Exception as e:
        print("Secondary TMDb lookup failed:", e)

    movies = load_christmas_playlist()

    if any((m.get("id") == imdb_id) for m in movies):
        return f"“{resolved_name}” is already in the Christmas playlist."

    movies.append(
        {
            "id": imdb_id,
            "name": f"{resolved_name}{f' ({year})' if year else ''}",
            "type": "movie",
            "tmdb_query": f"{resolved_name} {year}".strip(),
        }
    )
    save_christmas_playlist(movies)

    # Bust caches for this imdb id
    try:
        if imdb_id:
            if isinstance(TMDB_CACHE, dict):
                TMDB_CACHE.pop(imdb_id, None)
                _persist_memory_cache_to_disk()
    except Exception:
        pass

    return f"I’ve added “{resolved_name}{f' ({year})' if year else ''}” to the Christmas playlist."


def _normalize_movie_name_for_set(s: str) -> str:
    return _normalize_movie_name(s or "")


def add_movie_to_playlist_by_title(slug: str, title: str) -> str:
    slug = (slug or "christmas").lower().strip()
    title = (title or "").strip()

    if not title:
        return "I need a movie title to add."

    if slug == "christmas":
        return add_movie_to_christmas_by_title(title)

    movies = _load_generic_playlist(slug)
    existing = {_normalize_movie_name_for_set(m.get("name") or m.get("title") or "") for m in movies}
    if _normalize_movie_name_for_set(title) in existing:
        return f"“{title}” is already in the {slug.capitalize()} playlist."

    movies.append({"title": title})
    _save_generic_playlist(slug, movies)
    return f"I’ve added “{title}” to the {slug.capitalize()} playlist."


def remove_movie_from_christmas(title: str) -> str:
    if not title:
        return (
            "Tell me which movie to remove, like: "
            "“Remove The Polar Express from the Christmas playlist.”"
        )

    movies = load_christmas_playlist()
    if not movies:
        return "Your Christmas playlist is currently empty."

    target_norm = _normalize_movie_name(title)

    idx_to_remove = None
    removed_movie = None

    for idx, m in enumerate(movies):
        name = m.get("name") or m.get("title") or ""
        if not name:
            continue
        if _normalize_movie_name(name) == target_norm:
            idx_to_remove = idx
            removed_movie = m
            break

    if idx_to_remove is None:
        return (
            f"I couldn't find “{title}” in your Christmas playlist. "
            "You can say “Show my Christmas playlist” to see what's there."
        )

    movies.pop(idx_to_remove)
    save_christmas_playlist(movies)

    removed_name = removed_movie.get("name") or removed_movie.get("title") or title
    return f"I’ve removed “{removed_name}” from the Christmas playlist."


def remove_movie_from_playlist(slug: str, title: str) -> str:
    slug = (slug or "").lower().strip()
    if slug == "christmas":
        return remove_movie_from_christmas(title)

    if not title:
        return (
            "Tell me which movie to remove, like: "
            f"“Remove The Family Man from the {slug} playlist.”"
        )

    movies = _load_generic_playlist(slug)
    if not movies:
        return (
            f"I couldn't find “{title}” in your {slug.capitalize()} playlist. "
            f"You can say “Show my {slug} playlist” to see what's there."
        )

    target_norm = _normalize_movie_name(title)
    idx_to_remove = None
    removed_movie: dict | None = None

    for idx, m in enumerate(movies):
        name = m.get("name") or m.get("title") or ""
        if not name:
            continue
        if _normalize_movie_name(name) == target_norm:
            idx_to_remove = idx
            removed_movie = m
            break

    if idx_to_remove is None:
        return (
            f"I couldn't find “{title}” in your {slug.capitalize()} playlist. "
            f"You can say “Show my {slug} playlist” to see what's there."
        )

    movies.pop(idx_to_remove)
    _save_generic_playlist(slug, movies)

    removed_name = (removed_movie.get("name") or removed_movie.get("title") or title) if removed_movie else title
    return f"I’ve removed “{removed_name}” from the {slug.capitalize()} playlist."


def add_tmdb_candidate_to_christmas(candidate: dict) -> str:
    imdb_id = candidate.get("imdb_id")
    title = candidate.get("title") or candidate.get("name") or "Unknown title"
    year = candidate.get("year") or ""

    if not imdb_id:
        return f"I couldn't resolve an IMDb ID for “{title}”, so I can't add it."

    movies = load_christmas_playlist()

    if any(m.get("id") == imdb_id for m in movies):
        return f"“{title}{f' ({year})' if year else ''}” is already in the Christmas playlist."

    display_name = f"{title}{f' ({year})' if year else ''}"

    movies.append(
        {
            "id": imdb_id,
            "name": display_name,
            "type": "movie",
            "tmdb_query": f"{title} {year}".strip(),
        }
    )
    save_christmas_playlist(movies)

    try:
        if isinstance(TMDB_CACHE, dict):
            TMDB_CACHE.pop(imdb_id, None)
            _persist_memory_cache_to_disk()
    except Exception:
        pass

    return f"I’ve added “{display_name}” to the Christmas playlist."

