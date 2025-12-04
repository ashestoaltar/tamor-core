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
        
def tmdb_search_candidates(query: str, max_results: int = 5) -> list[dict]:
    """Return top N TMDb matches for a movie query, normalized.

    Each candidate is a dict with:
      - tmdb_id
      - title
      - year
      - overview
      - poster (full URL if available)
      - imdb_id (looked up via /movie/{id} detail)
    """
    if not TMDB_API_KEY:
        return []

    try:
        search_resp = requests.get(
            f"{TMDB_BASE_URL}/search/movie",
            params={"api_key": TMDB_API_KEY, "query": query},
            timeout=5,
        )
        search_resp.raise_for_status()
        results = (search_resp.json().get("results") or [])[:max_results]
        if not results:
            return []

        candidates: list[dict] = []
        for m in results:
            tmdb_id = m.get("id")
            if not tmdb_id:
                continue

            title = m.get("title") or m.get("name") or query
            year = ""
            release_date = m.get("release_date") or ""
            if release_date:
                year = release_date.split("-")[0]

            overview = m.get("overview") or ""
            poster_path = m.get("poster_path") or ""
            poster_url = TMDB_IMAGE_BASE + poster_path if poster_path else None

            imdb_id = None
            try:
                detail_resp = requests.get(
                    f"{TMDB_BASE_URL}/movie/{tmdb_id}",
                    params={
                        "api_key": TMDB_API_KEY,
                        "append_to_response": "external_ids",
                    },
                    timeout=5,
                )
                detail_resp.raise_for_status()
                external_ids = (detail_resp.json().get("external_ids") or {})
                imdb_id = external_ids.get("imdb_id")
            except Exception as inner_e:
                print("TMDb detail lookup failed for", tmdb_id, "->", inner_e)

            candidates.append(
                {
                    "tmdb_id": tmdb_id,
                    "imdb_id": imdb_id,
                    "title": title,
                    "year": year,
                    "overview": overview,
                    "poster": poster_url,
                }
            )

        return candidates
    except Exception as e:
        print("TMDb candidate search failed for", query, "->", e)
        return []
        
