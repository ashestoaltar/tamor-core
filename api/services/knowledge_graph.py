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
from routes.files_api import _get_upload_root, _read_file_text

# Reuse the same placeholder detection idea as file_semantic_service
_PLACEHOLDER_PREFIXES = (
    "This file is not a plain-text type.",
    "This file is a PDF, but the PDF parser",
    "This PDF appears to have no extractable text",
    "Error extracting text from PDF:",
    "Error reading file contents.",
)

_TEXT_EXTS = {
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".py",
    ".lisp",
    ".html",
    ".css",
    ".csv",
    ".yml",
    ".yaml",
    ".ini",
    ".cfg",
    ".conf",
}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def ensure_file_symbols_table() -> None:
    """
    Create the file_symbols table if it does not exist.

    This mirrors upgrade_db_phase2_knowledge.py, but is safe to re-call.
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS file_symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            file_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            value TEXT,
            line_number INTEGER,
            snippet TEXT,
            embedding BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (file_id) REFERENCES project_files(id)
        );
        """
    )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_file_symbols_project
        ON file_symbols(project_id);
        """
    )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_file_symbols_symbol
        ON file_symbols(symbol);
        """
    )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# File loading + symbol extraction
# ---------------------------------------------------------------------------


def _is_placeholder_text(text: str | None) -> bool:
    t = (text or "").strip()
    return any(t.startswith(p) for p in _PLACEHOLDER_PREFIXES)


def _is_text_like_row(row: sqlite3.Row) -> bool:
    mime = (row["mime_type"] or "").lower()
    name = (row["filename"] or "").lower()

    if mime.startswith("text/"):
        return True

    return any(name.endswith(ext) for ext in _TEXT_EXTS)


def _load_file_text_for_row(row: sqlite3.Row) -> str:
    """Read text for a project_files row using the same logic as /files/content."""
    upload_root = _get_upload_root()
    stored_name_rel = row["stored_name"]
    mime_type = row["mime_type"] or ""

    full_path = os.path.join(upload_root, stored_name_rel)
    if not os.path.isfile(full_path):
        return ""

    return _read_file_text(full_path, mime_type)


_SYMBOL_REGEXES: List[re.Pattern] = [
    # JSON / YAML / INI style: key: value
    re.compile(r'(?P<name>[A-Za-z_][A-Za-z0-9_\.]*)\s*:\s*'),
    # Code / config: key = value
    re.compile(r'(?P<name>[A-Za-z_][A-Za-z0-9_\.]*)\s*=\s*'),
]


def _extract_symbols_from_text(text: str) -> List[Tuple[str, int, str]]:
    """
    Naive but robust extraction of "symbols" from a text blob.

    Returns list of (symbol, line_number, snippet).
    """
    if not text:
        return []

    results: List[Tuple[str, int, str]] = []
    seen_for_line: set[tuple[int, str]] = set()

    # Limit lines to avoid exploding on huge files
    lines = text.splitlines()
    for idx, raw_line in enumerate(lines[:5000]):  # safety limit
        line = raw_line.strip()
        if not line:
            continue

        for rex in _SYMBOL_REGEXES:
            for m in rex.finditer(line):
                name = m.group("name")
                key = (idx, name)
                if key in seen_for_line:
                    continue
                seen_for_line.add(key)

                snippet = line
                if len(snippet) > 240:
                    snippet = snippet[:237] + "..."
                results.append((name, idx + 1, snippet))

    return results


# ---------------------------------------------------------------------------
# Public API: extraction
# ---------------------------------------------------------------------------


def extract_symbols_for_project(project_id: int, user_id: int) -> Dict[str, Any]:
    """
    Scan all text-like files in a project, extract symbols, and write them
    into file_symbols.

    Returns stats:
      {
        "project_id": ...,
        "files_scanned": ...,
        "files_with_symbols": ...,
        "symbols_written": ...
      }
    """
    ensure_file_symbols_table()

    conn = get_db()
    cur = conn.cursor()

    # Fetch candidate files
    cur.execute(
        """
        SELECT id, filename, stored_name, mime_type
        FROM project_files
        WHERE project_id = ? AND user_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (project_id, user_id),
    )
    file_rows = cur.fetchall()

    # Clear any previous symbols for this project (simple + predictable)
    cur.execute("DELETE FROM file_symbols WHERE project_id = ?", (project_id,))
    conn.commit()

    files_scanned = 0
    files_with_symbols = 0
    symbols_written = 0

    for row in file_rows:
        if not _is_text_like_row(row):
            continue

        files_scanned += 1
        file_id = row["id"]
        text = _load_file_text_for_row(row)

        if not text or _is_placeholder_text(text):
            continue

        symbols = _extract_symbols_from_text(text)
        if not symbols:
            continue

        files_with_symbols += 1

        rows_to_insert: List[Tuple[Any, ...]] = []
        for symbol, line_number, snippet in symbols:
            # Embed (symbol + snippet) as the vector anchor
            emb_blob = embed(f"{symbol}\n{snippet or ''}")
            rows_to_insert.append(
                (
                    project_id,
                    file_id,
                    symbol,
                    None,  # value (future: we could try to parse the RHS)
                    line_number,
                    snippet,
                    emb_blob,
                )
            )

        cur.executemany(
            """
            INSERT INTO file_symbols
                (project_id, file_id, symbol, value, line_number, snippet, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows_to_insert,
        )
        symbols_written += len(rows_to_insert)

    conn.commit()
    conn.close()

    return {
        "project_id": project_id,
        "files_scanned": files_scanned,
        "files_with_symbols": files_with_symbols,
        "symbols_written": symbols_written,
    }


# ---------------------------------------------------------------------------
# Public API: symbol search
# ---------------------------------------------------------------------------


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def query_symbol(
    project_id: int,
    user_id: int,
    symbol: str,
    top_k: int = 25,
) -> Dict[str, Any]:
    """
    Fuzzy search for a symbol / config key within a project's extracted symbols.

    Returns:
      {
        "query": "WidthMM",
        "results": [
          {
            "id": ...,
            "project_id": ...,
            "file_id": ...,
            "symbol": "WidthMM",
            "line_number": 42,
            "snippet": "WidthMM = 3650",
            "filename": "config.json",
            "mime_type": "application/json",
            "score": 0.91
          },
          ...
        ]
      }
    """
    symbol = (symbol or "").strip()
    if not symbol:
        return {"query": "", "results": []}

    ensure_file_symbols_table()

    # Embed query text
    q_vec = np.frombuffer(embed(symbol), dtype=np.float32)

    conn = get_db()
    cur = conn.cursor()

    # Only search within this project; we *could* also filter on user_id for safety,
    # but project_id is already tied to user ownership elsewhere.
    cur.execute(
        """
        SELECT
            fs.id,
            fs.project_id,
            fs.file_id,
            fs.symbol,
            fs.line_number,
            fs.snippet,
            fs.embedding,
            pf.filename,
            pf.mime_type
        FROM file_symbols fs
        JOIN project_files pf ON fs.file_id = pf.id
        WHERE fs.project_id = ?
        """,
        (project_id,),
    )
    rows = cur.fetchall()
    conn.close()

    scored: List[Dict[str, Any]] = []
    for row in rows:
        emb_blob = row["embedding"]
        if not emb_blob:
            continue

        emb_vec = np.frombuffer(emb_blob, dtype=np.float32)
        score = _cosine_similarity(q_vec, emb_vec)
        if score <= 0:
            continue

        scored.append(
            {
                "id": row["id"],
                "project_id": row["project_id"],
                "file_id": row["file_id"],
                "symbol": row["symbol"],
                "line_number": row["line_number"],
                "snippet": row["snippet"],
                "filename": row["filename"],
                "mime_type": row["mime_type"],
                "score": score,
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    if top_k and top_k > 0:
        scored = scored[: top_k]

    return {
        "query": symbol,
        "results": scored,
    }

