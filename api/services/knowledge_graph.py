# services/knowledge_graph.py
"""
Phase 2.3 – Project knowledge graph (symbols / config keys).

Responsibilities:
- Ensure file_symbols table exists (mirrors upgrade_db_phase2_knowledge.py).
- Extract symbols / parameters / config keys from text-like project files.
- Store one row per symbol occurrence in file_symbols.
- Provide a fuzzy search API over those symbols using embeddings.
"""

from __future__ import annotations

import os
import re
import sqlite3
from typing import Any, Dict, List, Tuple

import numpy as np

from utils.db import get_db
from core.memory_core import embed
from routes.files_api import get_or_extract_file_text_for_row

# Reuse the same placeholder detection idea as file_semantic_service
_PLACEHOLDER_PREFIXES = (
    "This file is not a plain-text type.",
    "This file is a PDF, but the PDF parser",
    "This PDF appears to have no extractable text",
    "Error extracting text from PDF:",
    "Error reading file:",
)

_TEXT_EXTS = (
    ".txt",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".conf",
)


def _looks_text_like(filename: str, mime_type: str | None) -> bool:
    """
    Very rough check: we only process files that are likely to be text / configs.
    """
    if mime_type and mime_type.startswith("text/"):
        return True
    if not filename:
        return False
    lower = filename.lower()
    return any(lower.endswith(ext) for ext in _TEXT_EXTS)


def _load_file_text_for_row(row: sqlite3.Row) -> str:
    """
    Read text for a project_files row using the same logic (and cache)
    as the /files/<id>/summarize endpoint.
    """
    text, _meta, _parser = get_or_extract_file_text_for_row(row)
    return text


_SYMBOL_REGEXES: List[re.Pattern] = [
    # JSON / YAML / INI style: key: value
    re.compile(r"(?P<name>[A-Za-z_][A-Za-z0-9_\.]*)\s*:\s*"),
    # Code / config: key = value
    re.compile(r"(?P<name>[A-Za-z_][A-Za-z0-9_\.]*)\s*=\s*"),
]


def _extract_symbols_from_text(text: str) -> List[Tuple[str, int, str]]:
    """
    Naive but robust extraction of "symbols" from a text blob.

    Returns a list of (symbol_name, char_offset, context_snippet).
    """
    if not text or any(text.startswith(p) for p in _PLACEHOLDER_PREFIXES):
        return []

    results: List[Tuple[str, int, str]] = []
    length = len(text)

    for regex in _SYMBOL_REGEXES:
        for match in regex.finditer(text):
            name = match.group("name")
            start = match.start("name")
            snippet_start = max(0, start - 40)
            snippet_end = min(length, start + len(name) + 40)
            snippet = text[snippet_start:snippet_end]
            results.append((name, start, snippet))

    return results


def ensure_file_symbols_table() -> None:
    """
    Ensure the file_symbols table exists *and* has the columns we expect.

    This handles the case where an older version of the table was created
    without char_offset / snippet / embedding / created_at.
    """
    conn = get_db()
    cur = conn.cursor()

    # 1) Create table if it doesn't exist at all
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS file_symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            char_offset INTEGER,
            snippet TEXT,
            embedding BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES project_files(id)
        )
        """
    )

    # 2) Introspect existing columns and add any missing ones
    cur.execute("PRAGMA table_info(file_symbols)")
    cols = {row[1] for row in cur.fetchall()}  # row[1] = column name

    if "char_offset" not in cols:
        cur.execute("ALTER TABLE file_symbols ADD COLUMN char_offset INTEGER")

    if "snippet" not in cols:
        cur.execute("ALTER TABLE file_symbols ADD COLUMN snippet TEXT")

    if "embedding" not in cols:
        cur.execute("ALTER TABLE file_symbols ADD COLUMN embedding BLOB")

    if "created_at" not in cols:
        cur.execute(
            "ALTER TABLE file_symbols ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        )

    # 3) Index on symbol for faster lookups
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_file_symbols_symbol ON file_symbols(symbol)"
    )

    conn.commit()



def extract_symbols_for_project(project_id: int, user_id: int) -> int:
    """
    Extract symbols from all text-like files in a project and store them in file_symbols.

    Returns total number of symbols stored.
    """
    ensure_file_symbols_table()

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT pf.*
        FROM project_files pf
        JOIN projects p ON pf.project_id = p.id
        WHERE pf.project_id = ? AND p.user_id = ?
        ORDER BY pf.id DESC
        """,
        (project_id, user_id),
    )
    rows = cur.fetchall()

    total_symbols = 0

    for row in rows:
        filename = row["filename"]
        mime_type = row["mime_type"] or ""

        if not _looks_text_like(filename, mime_type):
            continue

        text = _load_file_text_for_row(row)
        if not text or any(text.startswith(p) for p in _PLACEHOLDER_PREFIXES):
            continue

        symbols = _extract_symbols_from_text(text)
        if not symbols:
            continue

        file_id = row["id"]

        cur.execute("DELETE FROM file_symbols WHERE file_id = ?", (file_id,))

        cur.executemany(
            """
            INSERT INTO file_symbols (file_id, symbol, char_offset, snippet)
            VALUES (?, ?, ?, ?)
            """,
            [(file_id, name, offset, snippet) for (name, offset, snippet) in symbols],
        )
        conn.commit()

        total_symbols += len(symbols)

    return total_symbols


def _load_symbol_embeddings(symbol_ids: List[int]) -> Dict[int, np.ndarray]:
    """Load embeddings for a subset of symbols."""
    if not symbol_ids:
        return {}

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in symbol_ids)
    cur.execute(
        f"SELECT id, embedding FROM file_symbols WHERE id IN ({placeholders})",
        symbol_ids,
    )
    rows = cur.fetchall()

    embeddings: Dict[int, np.ndarray] = {}
    for row in rows:
        emb = np.frombuffer(row["embedding"], dtype=np.float32)
        embeddings[row["id"]] = emb

    return embeddings


def _embed_missing_symbols(symbol_ids: List[int]) -> Dict[int, np.ndarray]:
    """
    Embed all symbols whose embedding is currently NULL and return embeddings for given IDs.
    """
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, symbol
        FROM file_symbols
        WHERE embedding IS NULL
        """
    )
    rows = cur.fetchall()
    if not rows:
        return _load_symbol_embeddings(symbol_ids)

    texts = [row["symbol"] for row in rows]
    embs = embed(texts)

    for row, emb in zip(rows, embs):
        cur.execute(
            "UPDATE file_symbols SET embedding = ? WHERE id = ?",
            (emb.tobytes(), row["id"]),
        )
    conn.commit()

    return _load_symbol_embeddings(symbol_ids)


def query_symbol(project_id: int, user_id: int, symbol: str, top_k: int = 10) -> Dict[str, Any]:
    """
    Fuzzy search over symbols in a project using embeddings.
    """
    ensure_file_symbols_table()

    if not symbol.strip():
        return {"query": symbol, "hits": []}

    q_emb = embed(symbol)

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT fs.id, fs.file_id, fs.symbol, fs.char_offset, fs.snippet,
               pf.filename, pf.mime_type
        FROM file_symbols fs
        JOIN project_files pf ON fs.file_id = pf.id
        JOIN projects p ON pf.project_id = p.id
        WHERE pf.project_id = ? AND p.user_id = ?
        """,
        (project_id, user_id),
    )
    rows = cur.fetchall()
    if not rows:
        return {"query": symbol, "hits": []}

    symbol_ids = [row["id"] for row in rows]
    emb_map = _embed_missing_symbols(symbol_ids)

    embs = np.vstack([emb_map[row["id"]] for row in rows])

    norms = np.linalg.norm(embs, axis=1) * np.linalg.norm(q_emb)
    sims = np.dot(embs, q_emb) / np.maximum(norms, 1e-8)

    top_indices = np.argsort(-sims)[:top_k]

    hits = []
    for idx in top_indices:
        row = rows[int(idx)]
        hits.append(
            {
                "file_id": row["file_id"],
                "filename": row["filename"],
                "mime_type": row["mime_type"],
                "symbol": row["symbol"],
                "char_offset": row["char_offset"],
                "snippet": row["snippet"],
                "score": float(sims[idx]),
            }
        )

    return {"query": symbol, "hits": hits}

