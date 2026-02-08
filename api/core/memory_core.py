import sqlite3
import numpy as np

from .config import MEMORY_DB, model


def embed(text: str) -> bytes:
    vec = model.encode([text])[0]
    return vec.astype(np.float32).tobytes()


def embed_many(texts: list[str]) -> list[bytes]:
    """
    Embed many texts at once and return a list of BLOBs suitable for SQLite.
    """
    if not texts:
        return []
    vecs = model.encode(texts)
    blobs: list[bytes] = []
    for vec in vecs:
        blobs.append(vec.astype(np.float32).tobytes())
    return blobs


def search_memories(query: str, limit: int = 5):
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


def auto_store_memory_if_relevant(
    text: str,
    mode: str,
    source: str = "user",
    user_id: int | None = None,
) -> str | None:
    """
    DEPRECATED: Phase 9.1 replaced regex classification with LLM-based archivist.
    Kept as stub for backwards compatibility with /memory/auto endpoint.
    Always returns None — the archivist agent handles memory decisions now.
    """
    return None

