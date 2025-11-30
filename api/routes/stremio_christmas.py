# routes/stremio_christmas.py
from flask import Blueprint, jsonify, request

from core.config import TMDB_CACHE
from services.playlists import load_christmas_playlist
from services.tmdb_service import tmdb_lookup_movie

stremio_bp = Blueprint("stremio_christmas", __name__)


@stremio_bp.route("/stremio/christmas/manifest.json")
def manifest():
    return jsonify(
        {
            "id": "tamor.christmas",
            "version": "1.0.1",
            "name": "Christmas Playlist (Tamor)",
            "description": "Our family Christmas movie playlist served by Tamor",
            "types": ["movie"],
            "catalogs": [
                {
                    "type": "movie",
                    "id": "christmas",
                    "name": "Christmas",
                }
            ],
            "resources": ["catalog", "meta"],
            "behaviorHints": {"configurable": False},
        }
    )


@stremio_bp.route("/stremio/christmas/catalog/<content_type>/<catalog_id>.json")
@stremio_bp.route("/stremio/christmas/catalog/<content_type>/<catalog_id>/<int:skip>.json")
@stremio_bp.route(
    "/stremio/christmas/catalog/<content_type>/<catalog_id>/<int:skip>/<int:limit>.json"
)
def catalog(content_type, catalog_id, skip=0, limit=None):
    if content_type != "movie" or catalog_id != "christmas":
        return ("", 404)

    movies = load_christmas_playlist()
    metas = []

    for item in movies:
        our_id = item["id"]

        if our_id in TMDB_CACHE:
            enriched = TMDB_CACHE[our_id].copy()
        else:
            tmdb_bits = tmdb_lookup_movie(item.get("tmdb_query") or item["name"])
            enriched = tmdb_bits.copy()
            TMDB_CACHE[our_id] = enriched

        meta = {
            "id": our_id,
            "type": item.get("type", "movie"),
            "name": item["name"],
        }

        if enriched.get("poster"):
            meta["poster"] = enriched["poster"]
        if enriched.get("overview"):
            meta["description"] = enriched["overview"]
        if enriched.get("year"):
            meta["year"] = enriched["year"]

        if enriched.get("imdb_id"):
            meta["imdb_id"] = enriched["imdb_id"]
            meta["idImdb"] = enriched["imdb_id"]
        if enriched.get("tmdb_id"):
            meta["tmdb_id"] = enriched["tmdb_id"]
            meta["idTmdb"] = enriched["tmdb_id"]

        metas.append(meta)

    if limit is not None:
        metas = metas[skip : skip + limit]
    elif skip:
        metas = metas[skip:]

    return jsonify({"metas": metas})


@stremio_bp.route("/stremio/christmas/meta/<content_type>/<movie_id>.json")
def meta(content_type, movie_id):
    if content_type != "movie":
        return ("", 404)

    movies = load_christmas_playlist()

    for item in movies:
        if item["id"] == movie_id:
            if movie_id in TMDB_CACHE:
                enriched = TMDB_CACHE[movie_id].copy()
            else:
                tmdb_bits = tmdb_lookup_movie(item.get("tmdb_query") or item["name"])
                enriched = tmdb_bits.copy()
                TMDB_CACHE[movie_id] = enriched

            meta = {
                "id": item["id"],
                "type": item.get("type", "movie"),
                "name": item["name"],
            }

            if enriched.get("poster"):
                meta["poster"] = enriched["poster"]
            if enriched.get("overview"):
                meta["description"] = enriched["overview"]
            if enriched.get("year"):
                meta["year"] = enriched["year"]

            if enriched.get("imdb_id"):
                meta["imdb_id"] = enriched["imdb_id"]
                meta["idImdb"] = enriched["imdb_id"]
            if enriched.get("tmdb_id"):
                meta["tmdb_id"] = enriched["tmdb_id"]
                meta["idTmdb"] = enriched["tmdb_id"]

            return jsonify({"meta": meta})

    return ("", 404)
