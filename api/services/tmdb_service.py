# services/tmdb_service.py
import requests

from core.config import TMDB_API_KEY, TMDB_BASE_URL, TMDB_IMAGE_BASE


def tmdb_lookup_movie(query: str) -> dict:
    if not TMDB_API_KEY:
        return {}

    try:
        search_resp = requests.get(
            f"{TMDB_BASE_URL}/search/movie",
            params={"api_key": TMDB_API_KEY, "query": query},
            timeout=5,
        )
        search_resp.raise_for_status()
        results = (search_resp.json().get("results") or [])
        if not results:
            return {}

        m = results[0]
        tmdb_id = m.get("id")
        poster = m.get("poster_path")
        year = (m.get("release_date") or "")[:4]
        overview = m.get("overview") or ""

        imdb_id = None
        if tmdb_id:
            detail_resp = requests.get(
                f"{TMDB_BASE_URL}/movie/{tmdb_id}",
                params={"api_key": TMDB_API_KEY, "append_to_response": "external_ids"},
                timeout=5,
            )
            detail_resp.raise_for_status()
            external_ids = (detail_resp.json().get("external_ids") or {})
            imdb_id = external_ids.get("imdb_id")

        return {
            "tmdb_id": tmdb_id,
            "imdb_id": imdb_id,
            "poster": TMDB_IMAGE_BASE + poster if poster else None,
            "year": year,
            "overview": overview,
        }
    except Exception as e:
        print("TMDb lookup failed for", query, "->", e)
        return {}
