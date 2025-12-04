import json
import os
import sqlite3

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from sentence_transformers import SentenceTransformer
import numpy as np
from openai import OpenAI
import requests


app = Flask(__name__)
CORS(app)

# ---------- ENV & CONFIG ----------

load_dotenv()

PERSONALITY_FILE = os.getenv("PERSONALITY_FILE")
MEMORY_DB = os.getenv("MEMORY_DB")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w342"  # good size for posters

TMDB_CACHE = {}  # simple in-memory cache: movie_id -> meta dict

# Playlist storage
PLAYLIST_DIR = "/home/tamor/playlists"
CHRISTMAS_PLAYLIST_FILE = os.path.join(PLAYLIST_DIR, "christmas.json")

# Default playlist (used on first run to seed the JSON file)
DEFAULT_CHRISTMAS_MOVIES = [
    {
        "id": "tt0218967",
        "type": "movie",
        "name": "The Family Man",
        "tmdb_query": "The Family Man 2000",
    },
    {
        "id": "tt0039628",
        "type": "movie",
        "name": "Miracle on 34th Street (1947)",
        "tmdb_query": "Miracle on 34th Street 1947",
    },
    {
        "id": "tt0038650",
        "type": "movie",
        "name": "It's a Wonderful Life",
        "tmdb_query": "It's a Wonderful Life 1946",
    },
    {
        "id": "tt0072424",
        "type": "movie",
        "name": "The Year Without a Santa Claus",
        "tmdb_query": "The Year Without a Santa Claus 1974",
    },
    {
        "id": "tt0097958",
        "type": "movie",
        "name": "National Lampoon's Christmas Vacation",
        "tmdb_query": "National Lampoon's Christmas Vacation 1989",
    },
    {
        "id": "tt0095016",
        "type": "movie",
        "name": "Die Hard",
        "tmdb_query": "Die Hard 1988",
    },
    {
        "id": "tt0075988",
        "type": "movie",
        "name": "Emmet Otter's Jug-Band Christmas",
        "tmdb_query": "Emmet Otter's Jug-Band Christmas 1977",
    },
    {
        "id": "tt0104940",
        "type": "movie",
        "name": "The Muppet Christmas Carol",
        "tmdb_query": "The Muppet Christmas Carol 1992",
    },
    {
        "id": "tt0066327",
        "type": "movie",
        "name": "Santa Claus Is Coming to Town",
        "tmdb_query": "Santa Claus Is Coming to Town 1970",
    },
    {
        "id": "tt0319343",
        "type": "movie",
        "name": "Elf",
        "tmdb_query": "Elf 2003",
    },
    {
        "id": "tt0059026",
        "type": "movie",
        "name": "A Charlie Brown Christmas",
        "tmdb_query": "A Charlie Brown Christmas 1965",
    },
    {
        "id": "tt0085334",
        "type": "movie",
        "name": "A Christmas Story",
        "tmdb_query": "A Christmas Story 1983",
    },
    {
        "id": "tt0486583",
        "type": "movie",
        "name": "Fred Claus",
        "tmdb_query": "Fred Claus 2007",
    },
    {
        "id": "tt0369436",
        "type": "movie",
        "name": "Four Christmases",
        "tmdb_query": "Four Christmases 2008",
    },
    {
        "id": "tt0060345",
        "type": "movie",
        "name": "How the Grinch Stole Christmas (1966)",
        "tmdb_query": "How the Grinch Stole Christmas 1966",
    },
    {
        "id": "tt0058536",
        "type": "movie",
        "name": "Rudolph the Red-Nosed Reindeer",
        "tmdb_query": "Rudolph the Red-Nosed Reindeer 1964",
    },
    {
        "id": "tt0096061",
        "type": "movie",
        "name": "Scrooged",
        "tmdb_query": "Scrooged 1988",
    },
]


def load_christmas_playlist():
    """
    Load the Christmas playlist from JSON.
    If the file doesn't exist, seed it with DEFAULT_CHRISTMAS_MOVIES.
    """
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


# ---------- TMDb HELPERS ----------


def tmdb_lookup_movie(query):
    """
    Look up a movie on TMDb by text query.

    If the query includes a year, e.g.:
        "Christmas in Connecticut 1945"
        "Christmas in Connecticut (1945)"
    we will:
      - strip the year from the search text, and
      - send it as the TMDb `year` parameter.

    Returns a dict with poster, overview, year, tmdb_id, imdb_id, or {} on failure.
    """
    if not TMDB_API_KEY:
        return {}

    raw_query = (query or "").strip()
    if not raw_query:
        return {}

    wanted_year = None
    base_query = raw_query

    # --- Try to extract a year from the end of the string ---

    # Case 1: ends with "(YYYY)"
    if raw_query.endswith(")") and "(" in raw_query:
        paren_start = raw_query.rfind("(")
        inside = raw_query[paren_start + 1 : -1].strip()
        if inside.isdigit() and len(inside) == 4:
            wanted_year = inside
            base_query = raw_query[:paren_start].strip()

    # Case 2: ends with " YYYY"
    if wanted_year is None:
        parts = raw_query.rsplit(" ", 1)
        if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 4:
            wanted_year = parts[1]
            base_query = parts[0].strip()

    try:
        # Build params for TMDb search
        params = {
            "api_key": TMDB_API_KEY,
            "query": base_query or raw_query,
        }
        if wanted_year:
            params["year"] = wanted_year  # <--- the important part

        # 1) Search by text (and optional year) to find the TMDb movie ID
        search_resp = requests.get(
            f"{TMDB_BASE_URL}/search/movie",
            params=params,
            timeout=5,
        )
        search_resp.raise_for_status()
        search_data = search_resp.json()
        results = search_data.get("results") or []
        if not results:
            return {}

        # Default choice
        chosen = results[0]

        # Extra safety: if a year was requested, try to pick a result with that year
        if wanted_year:
            for r in results:
                rd = (r.get("release_date") or "")[:4]
                if rd == wanted_year:
                    chosen = r
                    break

        m = chosen
        tmdb_id = m.get("id")
        poster = m.get("poster_path")
        year = (m.get("release_date") or "")[:4]

        imdb_id = None

        # 2) Fetch external_ids to get imdb_id
        if tmdb_id:
            detail_resp = requests.get(
                f"{TMDB_BASE_URL}/movie/{tmdb_id}",
                params={"api_key": TMDB_API_KEY, "append_to_response": "external_ids"},
                timeout=5,
            )
            detail_resp.raise_for_status()
            detail_data = detail_resp.json()
            external_ids = (detail_data.get("external_ids") or {})
            imdb_id = external_ids.get("imdb_id")

        return {
            "tmdb_id": tmdb_id,
            "imdb_id": imdb_id,
            "poster": TMDB_IMAGE_BASE + poster if poster else None,
            "year": year,
            "overview": m.get("overview") or "",
        }
    except Exception as e:
        print("TMDb lookup failed for", query, "->", e)
        return {}



# ---------- CORE TAMOR SETUP ----------

# OpenAI client
client = OpenAI()

# Load personality
with open(PERSONALITY_FILE, "r") as f:
    personality = json.load(f)

# Optional modes.json if present
MODES_FILE = os.path.join(os.path.dirname(PERSONALITY_FILE), "modes.json")
if os.path.exists(MODES_FILE):
    with open(MODES_FILE, "r") as f:
        modes = json.load(f)
else:
    modes = {}

# Load embedding model
model = SentenceTransformer(EMBEDDING_MODEL)

# Ensure memory DB exists
conn = sqlite3.connect(MEMORY_DB)
cursor = conn.cursor()
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    category TEXT,
    content TEXT,
    embedding BLOB
);
"""
)
conn.commit()
conn.close()


def embed(text: str) -> bytes:
    """Generate an embedding as a numpy float32 array (bytes)."""
    vec = model.encode([text])[0]
    return vec.astype(np.float32).tobytes()


def search_memories(query: str, limit: int = 5):
    """Semantic memory recall."""
    q_vec = model.encode([query])[0].astype(np.float32)

    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT id, content, embedding FROM memories")
    rows = cursor.fetchall()
    conn.close()

    scored = []
    for mid, content, emb_blob in rows:
        emb = np.frombuffer(emb_blob, dtype=np.float32)
        denom = np.linalg.norm(q_vec) * np.linalg.norm(emb)
        if denom == 0:
            continue
        score = float(np.dot(q_vec, emb) / denom)
        scored.append((score, mid, content))

    scored.sort(reverse=True)
    return scored[:limit]


# ---------- AUTO MEMORY HELPERS ----------


def classify_auto_memory(text: str, mode: str, source: str) -> str | None:
    """
    Central classification logic.
    Determines if text should be saved and under what category.
    """

    t = text.lower().strip()

    # Skip messages that are definitely not memory-worthy
    if len(t) < 30:
        return None
    if t in ["ok", "thanks", "thank you", "yes", "no"]:
        return None
    if t.endswith("?"):
        return None

    # Personal identity
    if source == "user":
        if any(p in t for p in ["my name is", "i am ", "i work at", "i'm the creator"]):
            return "identity"

        # Preferences
        if any(p in t for p in ["i like", "i prefer", "i love", "i usually", "i always"]):
            return "preference"

        # Projects
        if any(p in t for p in ["project", "working on", "build", "create tamor"]):
            return "project"

        # Theology
        if any(
            p in t
            for p in [
                "torah",
                "yeshua",
                "covenant",
                "foundations series",
                "nazarene",
                "pa rde s",
                "church drift",
            ]
        ):
            return "theology"

        # Engineering
        if any(
            p in t
            for p in [
                "autocad",
                "inventor",
                "vba",
                "configurator",
                "toscana",
                "anchor industries",
                "louver",
                "macro",
                "fstcam",
            ]
        ):
            return "engineering"

        # Ashes to Altar / music
        if any(
            p in t
            for p in [
                "ashes to altar",
                "light upon ruin",
                "song",
                "suno",
                "lyrics",
                "spotify",
                "album",
                "artwork",
            ]
        ):
            return "music"

        # Website ecosystem
        if any(
            p in t
            for p in ["ashestoaltar.com", "github pages", "index.html", "website"]
        ):
            return "website"

        # Long reflective note
        if len(t) > 400:
            return "long_note"

        # General conversation memory
        if len(t) > 120:
            return "conversation"

    # Assistant messages (knowledge)
    if source == "assistant":
        if "```" in text:
            return "knowledge_code"
        if len(t) > 500:
            return "knowledge"
        if any(p in t for p in ["torah", "yeshua", "theology"]):
            return "knowledge_theology"
        if any(p in t for p in ["autocad", "macro", "vba", "engineer"]):
            return "knowledge_engineering"

    return None


def auto_store_memory_if_relevant(text: str, mode: str, source: str = "user"):
    """
    Decide whether to auto-store this text as memory.
    - source: "user" or "assistant"
    """
    category = classify_auto_memory(text, mode, source=source)
    if not category:
        return

    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()

    # Skip if exact same content already exists
    cursor.execute("SELECT id FROM memories WHERE content = ? LIMIT 1", (text,))
    if cursor.fetchone():
        conn.close()
        return

    emb = embed(text)
    cursor.execute(
        "INSERT INTO memories (category, content, embedding) VALUES (?, ?, ?)",
        (category, text, emb),
    )
    conn.commit()
    conn.close()


def build_system_prompt(active_mode: str) -> str:
    """
    Build the full system prompt for Tamor based on:
    - Global personality (identity, directives, tone)
    - Active mode (summary, style, persona)
    """

    # Default to Scholar if mode not found
    mode_data = modes.get(active_mode, modes.get("Scholar", {}))

    # Global personality
    name = personality.get("name", "Tamor")
    identity = personality.get(
        "identity", "Tamor is an aligned, steady, illuminating intelligence."
    )
    directives = personality.get("directives", [])
    tone = personality.get("tone", {})

    # Format directives as bullet list
    directives_text = ""
    if directives:
        directives_text = "\n".join(f"- {d}" for d in directives)

    # Format tone as a compact description
    tone_text = ", ".join(f"{k}: {v}" for k, v in tone.items()) if tone else ""

    # Mode fields
    mode_label = mode_data.get("label", active_mode)
    mode_summary = mode_data.get("summary", "")
    mode_style = mode_data.get("style", "")
    mode_when = mode_data.get("when_to_use", "")
    mode_persona = mode_data.get("persona", "")

    system_prompt = f"""
You are {name}, a personal AI agent.

Identity:
{identity}

Global directives:
{directives_text}

Tone profile:
{tone_text}

Active mode: {mode_label}

Mode summary:
{mode_summary}

Mode style:
{mode_style}

When to use this mode:
{mode_when}

Mode persona (deep behavior spec):
{mode_persona}

General rules:
- Stay within the active mode's behavior and style unless the user explicitly asks to switch modes.
- Respect the user's values and constraints.
- Prefer clarity over cleverness. If you must make assumptions, state them briefly.
""".strip()

    return system_prompt



# ----- STREMIO: Add movies dynamically -----
def add_movie_to_christmas_by_title(title: str) -> str:
    """
    Use TMDb to resolve a movie by title, then add it
    to the Christmas playlist JSON by IMDb ID.
    """
    title = title.strip()
    if not title:
        return "I need a movie title to add."

    # Use our existing TMDb lookup
    info = tmdb_lookup_movie(title)
    imdb_id = info.get("imdb_id")
    tmdb_id = info.get("tmdb_id")
    year = info.get("year") or ""
    overview = info.get("overview") or ""

    if not imdb_id:
        return f"I couldn't find a matching IMDb entry for “{title}” on TMDb."

    # Try to improve name/year from TMDb result
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

    # Avoid duplicates
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

    # Clear cache to force new poster/overview on next catalog request
    TMDB_CACHE.pop(imdb_id, None)

    return f"I’ve added “{resolved_name}{f' ({year})' if year else ''}” to the Christmas playlist."

def remove_movie_from_christmas(identifier: str) -> str:
    """
    Remove a movie from the Christmas playlist.

    `identifier` can be:
      - an IMDb ID (e.g. "tt0218967")
      - a title (case-insensitive, may include year)
    """
    identifier = identifier.strip()
    if not identifier:
        return "I need a movie title or IMDb ID to remove."

    movies = load_christmas_playlist()
    if not movies:
        return "The Christmas playlist is currently empty."

    # Try by IMDb ID first (exact match)
    by_id_matches = [m for m in movies if m.get("id") == identifier]
    if by_id_matches:
        remaining = [m for m in movies if m.get("id") != identifier]
        save_christmas_playlist(remaining)
        TMDB_CACHE.pop(identifier, None)
        return f"I’ve removed “{by_id_matches[0].get('name', identifier)}” from the Christmas playlist."

    # Fallback: title-based removal (case-insensitive)
    norm_identifier = identifier.lower()

    # basic normalizer to ignore year in parentheses on either side
    def normalize_title(s: str) -> str:
        s = s.lower().strip()
        # remove stuff like " (1945)" at the end
        if "(" in s and ")" in s and s.endswith(")"):
            s = s[: s.rfind("(")].strip()
        return s

    title_matches = []
    for m in movies:
        name = m.get("name", "")
        if not name:
            continue
        if normalize_title(name) == normalize_title(identifier):
            title_matches.append(m)

    if not title_matches:
        return f"I couldn’t find “{identifier}” in the Christmas playlist."

    if len(title_matches) > 1:
        # Don’t guess if multiple – ask user to be more specific
        listed = ", ".join(
            f"{m.get('name')} [{m.get('id')}]" for m in title_matches
        )
        return (
            "There are multiple matches for that title in the playlist: "
            f"{listed}. Try removing by IMDb id (tt...) or include the year."
        )

    # Exactly one title match
    to_remove = title_matches[0]
    remaining = [m for m in movies if m is not to_remove]
    save_christmas_playlist(remaining)
    mid = to_remove.get("id")
    if mid:
        TMDB_CACHE.pop(mid, None)

    return f"I’ve removed “{to_remove.get('name', identifier)}” from the Christmas playlist."


# ---------- STREMIO: CHRISTMAS ADDON ----------


@app.route("/stremio/christmas/manifest.json")
def stremio_christmas_manifest():
    """
    Stremio reads this first to know what the addon is.
    """
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


@app.route("/stremio/christmas/catalog/<content_type>/<catalog_id>.json")
@app.route("/stremio/christmas/catalog/<content_type>/<catalog_id>/<int:skip>.json")
@app.route(
    "/stremio/christmas/catalog/<content_type>/<catalog_id>/<int:skip>/<int:limit>.json"
)
def stremio_christmas_catalog(content_type, catalog_id, skip=0, limit=None):
    """
    Stremio catalog for our Christmas playlist.

    Stremio will call things like:
      /stremio/christmas/catalog/movie/christmas.json
      /stremio/christmas/catalog/movie/christmas/0/100.json
    """
    if content_type != "movie" or catalog_id != "christmas":
        return ("", 404)

    movies = load_christmas_playlist()
    metas = []

    for item in movies:
        our_id = item["id"]

        # TMDb cache / lookup
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

        # merge TMDb extras if present
        if enriched.get("poster"):
            meta["poster"] = enriched["poster"]
        if enriched.get("overview"):
            meta["description"] = enriched["overview"]
        if enriched.get("year"):
            meta["year"] = enriched["year"]

        # IMDb + TMDb IDs for stream addons
        if enriched.get("imdb_id"):
            meta["imdb_id"] = enriched["imdb_id"]
            meta["idImdb"] = enriched["imdb_id"]
        if enriched.get("tmdb_id"):
            meta["tmdb_id"] = enriched["tmdb_id"]
            meta["idTmdb"] = enriched["tmdb_id"]

        metas.append(meta)

    # apply skip/limit if Stremio sends them (optional)
    if limit is not None:
        metas = metas[skip : skip + limit]
    elif skip:
        metas = metas[skip:]

    return jsonify({"metas": metas})


@app.route("/stremio/christmas/meta/<content_type>/<movie_id>.json")
def stremio_christmas_meta(content_type, movie_id):
    """
    Stremio meta endpoint.

    Stremio calls:
      /stremio/christmas/meta/movie/tt0218967.json
    """
    if content_type != "movie":
        return ("", 404)

    movies = load_christmas_playlist()

    for item in movies:
        if item["id"] == movie_id:
            # TMDb cache / lookup
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

            # merge TMDb extras if present
            if enriched.get("poster"):
                meta["poster"] = enriched["poster"]
            if enriched.get("overview"):
                meta["description"] = enriched["overview"]
            if enriched.get("year"):
                meta["year"] = enriched["year"]

            # IMDb / TMDb IDs for stream addons
            if enriched.get("imdb_id"):
                meta["imdb_id"] = enriched["imdb_id"]
                meta["idImdb"] = enriched["imdb_id"]
            if enriched.get("tmdb_id"):
                meta["tmdb_id"] = enriched["tmdb_id"]
                meta["idTmdb"] = enriched["tmdb_id"]

            return jsonify({"meta": meta})

    return ("", 404)


@app.route("/tamor/playlist/christmas/add", methods=["POST"])
def add_to_christmas_playlist():
    """
    Add a movie to the Christmas playlist.

    Expects JSON like:
      {
        "id": "tt0369436",
        "name": "Four Christmases",
        "tmdb_query": "Four Christmases 2008",
        "type": "movie"
      }
    """
    data = request.get_json(silent=True) or {}

    movie_id = data.get("id")
    name = data.get("name")
    tmdb_query = data.get("tmdb_query") or name
    mtype = data.get("type", "movie")

    if not movie_id or not name:
        return jsonify({"error": "id and name are required"}), 400

    movies = load_christmas_playlist()

    # avoid duplicates
    if any(m.get("id") == movie_id for m in movies):
        return jsonify({"status": "exists", "movie": movie_id}), 200

    movies.append(
        {
            "id": movie_id,
            "name": name,
            "type": mtype,
            "tmdb_query": tmdb_query,
        }
    )

    save_christmas_playlist(movies)

    # clear TMDB cache for this id so it will fetch fresh details next time
    TMDB_CACHE.pop(movie_id, None)

    return jsonify({"status": "added", "movie": movie_id}), 200


# ---------- API ROUTES: PERSONALITY & MEMORY ----------


@app.route("/api/personality", methods=["GET"])
def get_personality():
    return jsonify(personality)


@app.route("/api/memory/add", methods=["POST"])
def add_memory():
    data = request.json
    content = data.get("content")
    category = data.get("category", "general")
    emb = embed(content)

    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO memories (category, content, embedding) VALUES (?, ?, ?)",
        (category, content, emb),
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "success"})


@app.route("/api/memory/search", methods=["POST"])
def memory_search():
    data = request.json
    query = data.get("query")
    results = search_memories(query)

    output = [
        {
            "score": r[0],
            "id": r[1],
            "content": r[2],
        }
        for r in results
    ]

    return jsonify(output)


@app.route("/api/memory/list", methods=["GET"])
def list_memories():
    """
    Return a list of memories, optionally filtered by category and search query.
    GET /api/memory/list?category=theology&q=torah
    """
    category = request.args.get("category")
    query = request.args.get("q")

    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()

    base_sql = "SELECT id, category, content FROM memories"
    params = []

    filters = []
    if category and category.lower() != "all":
        filters.append("category = ?")
        params.append(category)

    if query:
        # simple LIKE search on content (we still have semantic search for deeper stuff)
        filters.append("content LIKE ?")
        params.append(f"%{query}%")

    if filters:
        base_sql += " WHERE " + " AND ".join(filters)

    base_sql += " ORDER BY id DESC LIMIT 200"

    cursor.execute(base_sql, params)
    rows = cursor.fetchall()
    conn.close()

    memories = [
        {"id": row[0], "category": row[1], "content": row[2]} for row in rows
    ]
    return jsonify(memories)


@app.route("/api/memory/<int:memory_id>", methods=["DELETE"])
def delete_memory(memory_id):
    """
    Delete a memory by ID.
    """
    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted", "id": memory_id})


@app.route("/api/memory/auto", methods=["POST"])
def auto_memory_ingest():
    """
    Ingests user or assistant text and automatically classifies + stores it.
    Request JSON:
    {
        "text": "...",
        "mode": "Forge",
        "source": "user" or "assistant"
    }
    """
    data = request.get_json()
    text = data.get("text", "").strip()
    mode = data.get("mode", "Default")
    source = data.get("source", "user")

    if not text:
        return jsonify({"stored": False, "reason": "empty"}), 200

    category = classify_auto_memory(text, mode, source)
    if not category:
        return jsonify({"stored": False, "reason": "not relevant"}), 200

    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()

    # Skip duplicates
    cursor.execute("SELECT id FROM memories WHERE content = ? LIMIT 1", (text,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"stored": False, "reason": "duplicate"}), 200

    emb = embed(text)
    cursor.execute(
        "INSERT INTO memories (category, content, embedding) VALUES (?, ?, ?)",
        (category, text, emb),
    )
    conn.commit()
    conn.close()

    return jsonify({"stored": True, "category": category}), 200


@app.get("/api/mode/<mode_name>")
def get_mode(mode_name):
    """Return mode metadata plus the fully built system prompt for debugging/inspection."""
    mode_data = modes.get(mode_name, {})
    system_prompt = build_system_prompt(mode_name)

    return {
        "name": mode_name,
        "mode": mode_data,
        "system_prompt": system_prompt,
    }


@app.route("/api/modes", methods=["GET"])
def get_modes():
    return jsonify(modes)


@app.route("/api/chat", methods=["POST"])
def chat():
    # Be robust to missing/invalid JSON
    data = request.get_json(silent=True) or {}

    user_message = data.get("message", "") or ""
    mode = data.get("mode", "Scholar")


    # ----- COMMAND: add movie to Christmas playlist -----
    lower_msg = (user_message or "").lower()

    # Pattern: "add [movie title] to the christmas playlist"
    if "add " in lower_msg and "to the christmas playlist" in lower_msg:
        # extract text between "add " and "to the christmas playlist"
        try:
            before, after = lower_msg.split("add ", 1)
            title_part, _ = after.split("to the christmas playlist", 1)
            raw_title = user_message[
                user_message.lower().find("add ") + 4 :
                user_message.lower().find("to the christmas playlist")
            ].strip(" .\"'")
        except Exception:
            raw_title = None

        if not raw_title:
            reply_text = "Tell me the movie title, like: “Add The Polar Express to the Christmas playlist.”"
        else:
            reply_text = add_movie_to_christmas_by_title(raw_title)

        # You can still log this interaction in memory if you want, but we short-circuit the LLM.
        return jsonify(
            {
                "tamor": reply_text,
                "mode": mode,
                "mode_info": modes.get(mode, {}),
                "memory_matches": [],
            }
        )
    # ----- COMMAND: remove movie from Christmas playlist -----
    if "remove " in lower_msg and "from the christmas playlist" in lower_msg:
        try:
            start_idx = lower_msg.find("remove ") + len("remove ")
            end_idx = lower_msg.find("from the christmas playlist")
            raw_title = user_message[start_idx:end_idx].strip(" .\"'")
        except Exception:
            raw_title = None

        if not raw_title:
            reply_text = (
                "Tell me what to remove, like: "
                "“Remove Christmas in Connecticut (1945) from the Christmas playlist.”"
            )
        else:
            reply_text = remove_movie_from_christmas(raw_title)

        return jsonify(
            {
                "tamor": reply_text,
                "mode": mode,
                "mode_info": modes.get(mode, {}),
                "memory_matches": [],
            }
        )


    # Retrieve memory
    memories = search_memories(user_message)
    memory_context = "\n".join([m[2] for m in memories])

    # Mode info if available
    mode_info = modes.get(mode, {})
    mode_summary = mode_info.get("summary", "")
    mode_style = mode_info.get("style", "")
    mode_when = mode_info.get("when_to_use", "")

    # Build system prompt using deep mode personality
    system_prompt = build_system_prompt(mode)

    # Add memory context (optional but helpful)
    system_prompt += (
        "\n\nUse the following long-term memory context only if it is helpful and relevant. "
        "Do not force it into the answer if it doesn't fit.\n"
        f"Memory context:\n{memory_context}"
    )

    try:
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        reply_text = completion.choices[0].message.content
    except Exception as e:
        reply_text = f"(Tamor encountered an error talking to the model: {e})"

    # ---- AUTO MEMORY: user message ----
    try:
        requests.post(
            "http://127.0.0.1:5055/api/memory/auto",
            json={"text": user_message, "mode": mode, "source": "user"},
            timeout=1.0,
        )
    except Exception as e:
        # Don't break chat if memory fails
        print("Auto-memory (user) failed:", e)

    # ---- AUTO MEMORY: assistant reply (for long-form knowledge) ----
    try:
        requests.post(
            "http://127.0.0.1:5055/api/memory/auto",
            json={"text": reply_text, "mode": mode, "source": "assistant"},
            timeout=1.0,
        )
    except Exception as e:
        print("Auto-memory (assistant) failed:", e)

    response = {
        "tamor": reply_text,
        "mode": mode,
        "mode_info": mode_info,
        "memory_matches": [
            {
                "id": m[1],
                "score": m[0],
                "content": m[2],
            }
            for m in memories
        ],
    }
    return jsonify(response)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5055)

