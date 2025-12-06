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


def classify_auto_memory(text: str, mode: str, source: str) -> str | None:
    t = text.lower().strip()

    if len(t) < 30:
        return None
    if t in {"ok", "thanks", "thank you", "yes", "no"}:
        return None
    if t.endswith("?"):
        return None

    if source == "user":
        if any(p in t for p in ["my name is", "i am ", "i work at", "i'm the creator"]):
            return "identity"

        if any(p in t for p in ["i like", "i prefer", "i love", "i usually", "i always"]):
            return "preference"

        if any(p in t for p in ["project", "working on", "build", "create tamor"]):
            return "project"

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

        if any(p in t for p in ["ashestoaltar.com", "github pages", "index.html", "website"]):
            return "website"

        if len(t) > 400:
            return "long_note"
        if len(t) > 120:
            return "conversation"

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


def auto_store_memory_if_relevant(text: str, mode: str, source: str = "user") -> None:
    import sqlite3  # local to avoid circular import issues

    from .config import MEMORY_DB  # avoid top-level cycles

    category = classify_auto_memory(text, mode, source=source)
    if not category:
        return

    conn = sqlite3.connect(MEMORY_DB)
    cursor = conn.cursor()

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

