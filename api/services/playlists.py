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

    TMDB_CACHE.pop(imdb_id, None)

    return f"I’ve added “{resolved_name}{f' ({year})' if year else ''}” to the Christmas playlist."
