"""
Package builder — creates ready-to-import JSON packages for Tamor.

A package contains everything Tamor needs to create a library_files record
and insert pre-built chunks with embeddings into library_chunks.
"""

import hashlib
import json
import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.harvest_config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    FORMAT_VERSION,
    READY_DIR,
)

from .chunker import chunk_text_filtered
from .embedder import embed_many


def compute_content_hash(text):
    """SHA-256 hash of text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_package(
    text,
    filename,
    stored_path,
    source_name,
    mime_type="text/plain",
    title=None,
    teacher=None,
    collection=None,
    content_type="article",
    url=None,
    date=None,
    topics=None,
    series=None,
    metadata=None,
    copyright_note="Personal research use only",
    hebrew_corrections_applied=False,
):
    """
    Build a complete harvest package from raw text.

    Args:
        text: The full text content to chunk and embed.
        filename: Filename for the library record (e.g., 'genesis-lesson-01.txt').
        stored_path: Path relative to /mnt/library/ where the raw file is stored.
        source_name: Ministry/source name (e.g., 'Torah Class').
        mime_type: MIME type of the original content.
        title: Human-readable title.
        teacher: Primary teacher/author name.
        collection: Collection name for auto-assignment (must exist in Tamor DB).
        content_type: 'article', 'transcript', 'lesson', 'study', 'devotional', etc.
        url: Source URL if applicable.
        date: Original publication date (ISO format string).
        topics: List of topic tags.
        series: Series name if part of a series.
        metadata: Additional metadata dict.
        copyright_note: Copyright/usage note.
        hebrew_corrections_applied: Whether Hebrew term corrections were applied.

    Returns:
        dict: Complete package ready for JSON serialization.
    """
    # Chunk the text
    chunks = chunk_text_filtered(text)

    if not chunks:
        return None

    # Generate embeddings for all chunks
    chunk_texts = [c["content"] for c in chunks]
    embeddings = embed_many(chunk_texts)

    # Attach embeddings to chunks
    package_chunks = []
    for chunk, embedding in zip(chunks, embeddings):
        package_chunks.append({
            "index": chunk["chunk_index"],
            "content": chunk["content"],
            "embedding": embedding,
            "start_offset": chunk["start_offset"],
            "page": None,
        })

    # Build the package
    package = {
        "format_version": FORMAT_VERSION,
        "source": {
            "name": source_name,
            "teacher": teacher,
            "collection": collection,
            "content_type": content_type,
            "url": url,
            "copyright_note": copyright_note,
        },
        "file": {
            "filename": filename,
            "stored_path": stored_path,
            "title": title or filename,
            "mime_type": mime_type,
            "content_hash": compute_content_hash(text),
            "text_length": len(text),
            "metadata": metadata or {},
        },
        "chunks": package_chunks,
        "processing": {
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dim": EMBEDDING_DIM,
            "chunk_count": len(package_chunks),
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "processor_host": socket.gethostname(),
            "hebrew_corrections_applied": hebrew_corrections_applied,
        },
    }

    # Add optional fields to file metadata
    file_meta = package["file"]["metadata"]
    if date:
        file_meta["date"] = date
    if topics:
        file_meta["topics"] = topics
    if series:
        file_meta["series"] = series

    return package


def write_package(package, output_dir=None):
    """
    Write a package to the ready directory as JSON.

    Returns: path to the written file.
    """
    if output_dir is None:
        output_dir = READY_DIR

    os.makedirs(output_dir, exist_ok=True)

    # Generate a unique filename from source + content hash
    source = package["source"]["name"].lower().replace(" ", "-")
    content_hash = package["file"]["content_hash"][:12]
    filename = f"{source}_{content_hash}.json"

    output_path = os.path.join(output_dir, filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(package, f, ensure_ascii=False)

    return output_path


def write_batch(packages, batch_name=None, output_dir=None):
    """
    Write multiple packages as a single batch file.

    A batch file contains a list of packages under a 'packages' key,
    plus batch-level metadata.

    Returns: path to the written batch file.
    """
    if output_dir is None:
        output_dir = READY_DIR

    os.makedirs(output_dir, exist_ok=True)

    if batch_name is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        batch_name = f"batch-{ts}"

    batch = {
        "format_version": FORMAT_VERSION,
        "batch": True,
        "batch_name": batch_name,
        "package_count": len(packages),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "processor_host": socket.gethostname(),
        "packages": packages,
    }

    output_path = os.path.join(output_dir, f"{batch_name}.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(batch, f, ensure_ascii=False)

    return output_path
