"""
Harvest cluster configuration.

These values MUST match Tamor's settings exactly.
Changing them without re-indexing existing content will break cosine similarity.
"""

# Embedding model — must match core/config.py EMBEDDING_MODEL
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Chunking — must match services/library/chunk_service.py
CHUNK_SIZE = 1200       # characters, NOT tokens
CHUNK_OVERLAP = 200     # characters

# NAS paths (relative to /mnt/library/)
HARVEST_BASE = "/mnt/library/harvest"
RAW_DIR = f"{HARVEST_BASE}/raw"
PROCESSED_DIR = f"{HARVEST_BASE}/processed"
READY_DIR = f"{HARVEST_BASE}/ready"
LOGS_DIR = f"{HARVEST_BASE}/logs"
CONFIG_DIR = f"{HARVEST_BASE}/config"

# Package format version
FORMAT_VERSION = "1.0"
