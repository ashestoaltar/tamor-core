"""
Text chunker — exact replica of Tamor's chunk_service._chunk_text().

Uses character-based sliding window. Parameters MUST match Tamor's
chunk_service.py (CHUNK_SIZE=1200, CHUNK_OVERLAP=200).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.harvest_config import CHUNK_SIZE, CHUNK_OVERLAP


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """
    Sliding window chunking by characters.

    Returns list of (start_offset, chunk_text).
    Mirrors chunk_service.py:_chunk_text() exactly.
    """
    chunks = []
    start = 0
    length = len(text)

    while start < length:
        end = min(length, start + chunk_size)
        chunks.append((start, text[start:end]))

        if end == length:
            break

        start = max(0, end - overlap)

    return chunks


def chunk_text_filtered(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """
    Chunk text and filter out empty/whitespace-only chunks.

    Returns list of dicts:
    {
        'chunk_index': int,
        'content': str,
        'start_offset': int,
    }
    """
    raw_chunks = chunk_text(text, chunk_size, overlap)

    result = []
    for idx, (start_offset, chunk_text_str) in enumerate(raw_chunks):
        if not chunk_text_str.strip():
            continue
        result.append({
            "chunk_index": idx,
            "content": chunk_text_str,
            "start_offset": start_offset,
        })

    return result
