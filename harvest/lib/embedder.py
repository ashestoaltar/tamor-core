"""
Embedding generator — uses the same model as Tamor (all-MiniLM-L6-v2).

Output format: float32 numpy bytes, base64-encoded for JSON transport.
On import, Tamor decodes base64 → bytes → stores as BLOB in library_chunks.
"""

import base64
import sys
import os

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.harvest_config import EMBEDDING_MODEL, EMBEDDING_DIM

# Lazy-loaded model singleton
_model = None


def get_model():
    """Load embedding model (cached after first call)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_one(text):
    """
    Embed a single text string.

    Returns: base64-encoded string of float32 numpy bytes.
    """
    model = get_model()
    vec = model.encode([text])[0]
    blob = vec.astype(np.float32).tobytes()
    return base64.b64encode(blob).decode("ascii")


def embed_many(texts):
    """
    Embed a list of text strings.

    Returns: list of base64-encoded strings of float32 numpy bytes.
    """
    if not texts:
        return []

    model = get_model()
    vecs = model.encode(texts)

    results = []
    for vec in vecs:
        blob = vec.astype(np.float32).tobytes()
        results.append(base64.b64encode(blob).decode("ascii"))

    return results


def embedding_to_bytes(b64_embedding):
    """Decode a base64 embedding back to raw bytes (for SQLite BLOB storage)."""
    return base64.b64decode(b64_embedding)


def embedding_to_numpy(b64_embedding):
    """Decode a base64 embedding to numpy float32 array."""
    raw = base64.b64decode(b64_embedding)
    return np.frombuffer(raw, dtype=np.float32)
