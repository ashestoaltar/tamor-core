import os
import json
import sqlite3

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# Load .env
load_dotenv()

# ---- ENV VALUES ----
PERSONALITY_FILE = os.getenv("PERSONALITY_FILE")
MEMORY_DB = os.getenv("MEMORY_DB")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w342"

# Playlist storage
PLAYLIST_DIR = "/home/tamor/tamor-core/data/playlists"
CHRISTMAS_PLAYLIST_FILE = os.path.join(PLAYLIST_DIR, "christmas.json")

# Simple in-memory TMDb cache
TMDB_CACHE: dict[str, dict] = {}

# ---- SEMANTIC FILE SEARCH CONFIG ----
# Character-based chunking size + overlap for file embeddings
FILE_CHUNK_SIZE = int(os.getenv("FILE_CHUNK_SIZE", "800"))
FILE_CHUNK_OVERLAP = int(os.getenv("FILE_CHUNK_OVERLAP", "200"))

# ---- LLM ----
# LLM client is now centralized in services.llm_service
# Import from there: from services.llm_service import get_llm_client, get_model_name

# ---- PERSONALITY / MODES ----
with open(PERSONALITY_FILE, "r", encoding="utf-8") as f:
    personality = json.load(f)

MODES_FILE = os.path.join(os.path.dirname(PERSONALITY_FILE), "modes.json")
if os.path.exists(MODES_FILE):
    with open(MODES_FILE, "r", encoding="utf-8") as f:
        modes = json.load(f)
else:
    modes = {}

# ---- EMBEDDING MODEL ----
model = SentenceTransformer(EMBEDDING_MODEL)

# ---- MEMORY DB INIT ----
def init_memory_db() -> None:
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

# Run once on import
init_memory_db()

