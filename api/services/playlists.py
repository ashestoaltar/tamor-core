# services/playlists.py
import json
import os
import requests

from core.config import (
    PLAYLIST_DIR,
    CHRISTMAS_PLAYLIST_FILE,
    TMDB_CACHE,
    TMDB_BASE_URL,
    TMDB_API_KEY,
)
from .tmdb_service import tmdb_lookup_movie


DEFAULT_CHRISTMAS_MOVIES = [
    {
        "id": "tt0218967",
        "type": "movie",
        "name": "The Family Man",
        "tmdb_query": "The Family Man 2000",
    },
    # ... put your full list back here ...
]


def load_christmas_playlist():
    try:
        with open(CHRISTMAS_PLAYLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [m for m in data if "id" in m and "name" in m]
    except FileNotFoundError:
        os.makedirs(PLAYLIST_DIR, exist_ok=True)
        with open(CHRISTMAS_PLAYLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CHRISTMAS_MOVIES, f, ensure_ascii=False, indent=2)
        return DEFAULT_CHRISTMAS_MOVIES.copy()
    except Exception as e:
        print("Failed to load christmas playlist:", e)
        return DEFAULT_CHRISTMAS_MOVIES.copy()


def save_christmas_playlist(movies):
    os.makedirs(PLAYLIST_DIR, exist_ok=True)
    with open(CHRISTMAS_PLAYLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(movies, f, ensure_ascii=False, indent=2)


def add_movie_to_christmas_by_title(title: str) -> str:
    title = title.strip()
    if not title:
        return "I need a movie title to add."

    info = tmdb_lookup_movie(title)
    imdb_id = info.get("imdb_id")
    year = info.get("year") or ""

    if not imdb_id:
        return f"I couldn't find a matching IMDb entry for “{title}” on TMDb."

    resolved_name = title
    try:
        search_resp = requests.get(
            f"{TMDB_BASE_URL}/search/movie",
            params={"api_key": TMDB_API_KEY, "query": title},
            timeout=5,
        )
        search_resp.raise_for_status()
        results = search_resp.json().get("results") or []
        if results:
            m = results[0]
            resolved_name = m.get("title") or m.get("name") or resolved_name
            year = (m.get("release_date") or "")[:4] or year
    except Exception as e:
        print("Secondary TMDb lookup failed:", e)

    movies = load_christmas_playlist()

    if any(m.get("id") == imdb_id for m in movies):
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

def list_christmas_playlist():
    """
    Return the current Christmas playlist as a list of movie dicts.
    Each entry is typically:
    {
      "id": imdb_id,
      "name": "Title (Year)",
      "type": "movie",
      "tmdb_query": ...
    }
    """
    movies = load_christmas_playlist()
    return movies or []


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
            # Cheap check for 4-digit year
            year_part = s[idx + 1 : -1]
            if year_part.isdigit() and len(year_part) == 4:
                s = s[:idx].strip()

    # Strip surrounding quotes and trailing punctuation
    s = s.strip(' "“”‘’\'.,!?')
    return s


def remove_movie_from_christmas(title: str) -> str:
    """
    Remove a movie from the Christmas playlist by title (loose match).

    - Case-insensitive
    - Ignores trailing year in the stored name
    - If multiple matches, removes the first and reports what it removed
    """
    if not title:
        return (
            "Tell me which movie to remove, like: "
            "“Remove The Polar Express from the Christmas playlist.”"
        )

    movies = load_christmas_playlist()
    if not movies:
        return "Your Christmas playlist is currently empty."

    target_norm = _normalize_movie_name(title)

    # Find first matching movie
    idx_to_remove = None
    removed_movie = None

    for idx, m in enumerate(movies):
        name = m.get("name") or ""
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

    removed_name = removed_movie.get("name") or title
    return f"I’ve removed “{removed_name}” from the Christmas playlist."

    TMDB_CACHE.pop(imdb_id, None)

    return f"I’ve added “{resolved_name}{f' ({year})' if year else ''}” to the Christmas playlist."
    
 
 # --- Generic multi-playlist helpers -----------------------------------------

def _playlist_file_for(slug: str) -> str:
    """
    Return the JSON file path for a named playlist.

    For the built-in Christmas playlist we continue to use the dedicated
    CHRISTMAS_PLAYLIST_FILE path so existing behavior is unchanged.
    """
    slug = (slug or "").lower().strip()
    if slug == "christmas":
        return CHRISTMAS_PLAYLIST_FILE
    os.makedirs(PLAYLIST_DIR, exist_ok=True)
    return os.path.join(PLAYLIST_DIR, f"{slug}.json")


def _load_generic_playlist(slug: str) -> list[dict]:
    """Load a non-Christmas playlist from disk (returns [] if missing)."""
    slug = (slug or "").lower().strip()
    path = _playlist_file_for(slug)
    if slug == "christmas":
        # Delegate to the dedicated loader so defaults are respected
        return load_christmas_playlist()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or []
        # Keep only sane dict entries with at least id + name/title
        cleaned = []
        for m in data:
            if not isinstance(m, dict):
                continue
            if "id" in m and (m.get("name") or m.get("title")):
                cleaned.append(m)
        return cleaned
    except FileNotFoundError:
        return []
    except Exception as e:
        print("Failed to load playlist", slug, "->", e)
        return []


def _save_generic_playlist(slug: str, movies: list[dict]) -> None:
    """Save a non-Christmas playlist to disk."""
    slug = (slug or "").lower().strip()
    path = _playlist_file_for(slug)
    if slug == "christmas":
        # Keep using the dedicated saver for the default playlist
        save_christmas_playlist(movies)
        return
    os.makedirs(PLAYLIST_DIR, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(movies or [], f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Failed to save playlist", slug, "->", e)


def list_playlist(slug: str) -> list[dict]:
    """Return a playlist by slug ("christmas", "thanksgiving", etc.)."""
    slug = (slug or "").lower().strip()
    if slug == "christmas":
        return list_christmas_playlist()
    return _load_generic_playlist(slug)


def remove_movie_from_playlist(slug: str, title: str) -> str:
    """Remove a movie from the given playlist by title (loose match)."""
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
        name = m.get("name") or m.get("title")
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

    removed_name = (
        (removed_movie.get("name") if removed_movie else None)
        or (removed_movie.get("title") if removed_movie else None)
        or title
    )
    return f"I’ve removed “{removed_name}” from the {slug.capitalize()} playlist."

    
def add_tmdb_candidate_to_christmas(candidate: dict) -> str:
    """Add a specific TMDb candidate (already chosen) to the Christmas playlist.

    Expects `candidate` to have at least:
      - imdb_id
      - title
      - year
    """
    imdb_id = candidate.get("imdb_id")
    title = candidate.get("title") or candidate.get("name") or "Unknown title"
    year = candidate.get("year") or ""

    if not imdb_id:
        return f"I couldn't resolve an IMDb ID for “{title}”, so I can't add it."

    movies = load_christmas_playlist()

    if any(m.get("id") == imdb_id for m in movies):
        return f"“{title}{f' ({year})' if year else ''}” is already in the Christmas playlist."

    resolved_name = title
    display_name = f"{resolved_name}{f' ({year})' if year else ''}"

    movies.append(
        {
            "id": imdb_id,
            "name": display_name,
            "type": "movie",
            "tmdb_query": f"{resolved_name} {year}".strip(),
        }
    )
    save_christmas_playlist(movies)

    # If you're caching TMDb lookups keyed by imdb_id, keep that in sync.
    try:
        from core.config import TMDB_CACHE  # type: ignore
        TMDB_CACHE.pop(imdb_id, None)
    except Exception:
        # Cache is optional; don't fail the add if this import or pop fails.
        pass

    return f"I’ve added “{display_name}” to the Christmas playlist."
    
