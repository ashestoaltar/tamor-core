#!/usr/bin/env python3
"""
Main processor script: raw content → chunked → embedded → packaged.

Watches /harvest/raw/{source}/ for content, processes it, writes
ready packages to /harvest/ready/.

Usage:
    python3 process_raw.py --source yavoh
    python3 process_raw.py --source lion-lamb-youtube
    python3 process_raw.py --source torah-class
    python3 process_raw.py --all
"""

import argparse
import glob
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.harvest_config import PROCESSED_DIR, RAW_DIR, READY_DIR
from lib.chunker import chunk_text_filtered
from lib.embedder import embed_many, get_model
from lib.hebrew_corrections import apply_corrections
from lib.packager import build_package, write_package

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def load_raw_item(path):
    """
    Load a raw harvested item.

    Raw items are JSON files with at minimum:
    {
        "text": "full text content",
        "filename": "genesis-lesson-01.txt",
        "source_name": "Torah Class",
        ...optional metadata fields...
    }
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def process_item(item, apply_hebrew=True):
    """
    Process a single raw item into a ready package.

    Args:
        item: dict from load_raw_item()
        apply_hebrew: whether to apply Hebrew term corrections

    Returns:
        package dict, or None if processing fails.
    """
    text = item.get("text", "")
    if not text or not text.strip():
        log.warning(f"Skipping {item.get('filename', '?')}: no text content")
        return None

    # Apply Hebrew corrections if requested
    corrections_count = 0
    if apply_hebrew:
        text, corrections_count = apply_corrections(text)
        if corrections_count > 0:
            log.info(f"  Applied {corrections_count} Hebrew corrections")

    # Build the package (chunking + embedding happens inside)
    package = build_package(
        text=text,
        filename=item.get("filename", "unknown.txt"),
        stored_path=item.get("stored_path", ""),
        source_name=item.get("source_name", "unknown"),
        mime_type=item.get("mime_type", "text/plain"),
        title=item.get("title"),
        teacher=item.get("teacher"),
        collection=item.get("collection"),
        content_type=item.get("content_type", "article"),
        url=item.get("url"),
        date=item.get("date"),
        topics=item.get("topics"),
        series=item.get("series"),
        metadata=item.get("metadata"),
        copyright_note=item.get("copyright_note", "Personal research use only"),
        hebrew_corrections_applied=(corrections_count > 0),
    )

    return package


def process_source(source_name, apply_hebrew=True):
    """
    Process all raw items for a given source.

    Looks in /harvest/raw/{source_name}/ for JSON files.
    Writes packages to /harvest/ready/.
    Moves processed raw files to /harvest/processed/{source_name}/.
    """
    raw_dir = os.path.join(RAW_DIR, source_name)
    processed_dir = os.path.join(PROCESSED_DIR, source_name)
    os.makedirs(processed_dir, exist_ok=True)

    if not os.path.isdir(raw_dir):
        log.error(f"Raw directory not found: {raw_dir}")
        return 0, 0

    # Find all raw JSON files
    raw_files = sorted(glob.glob(os.path.join(raw_dir, "*.json")))
    if not raw_files:
        log.info(f"No raw files found in {raw_dir}")
        return 0, 0

    log.info(f"Processing {len(raw_files)} items from {source_name}")

    # Pre-load the embedding model to avoid per-item loading
    log.info("Loading embedding model...")
    get_model()
    log.info("Model loaded")

    success = 0
    errors = 0

    for i, raw_path in enumerate(raw_files, 1):
        basename = os.path.basename(raw_path)
        log.info(f"[{i}/{len(raw_files)}] {basename}")

        try:
            item = load_raw_item(raw_path)
            package = process_item(item, apply_hebrew=apply_hebrew)

            if package is None:
                errors += 1
                continue

            # Write package to ready dir
            output_path = write_package(package)
            log.info(f"  → {os.path.basename(output_path)} "
                     f"({package['processing']['chunk_count']} chunks)")

            # Move raw file to processed
            dest = os.path.join(processed_dir, basename)
            os.rename(raw_path, dest)

            success += 1

        except Exception as e:
            log.error(f"  Error: {e}")
            errors += 1

    log.info(f"Done: {success} packaged, {errors} errors")
    return success, errors


def process_all(apply_hebrew=True):
    """Process all sources that have raw content waiting."""
    if not os.path.isdir(RAW_DIR):
        log.error(f"Raw directory not found: {RAW_DIR}")
        return

    sources = [
        d for d in os.listdir(RAW_DIR)
        if os.path.isdir(os.path.join(RAW_DIR, d))
    ]

    if not sources:
        log.info("No sources found in raw directory")
        return

    log.info(f"Found {len(sources)} sources: {', '.join(sources)}")

    total_success = 0
    total_errors = 0

    for source in sorted(sources):
        s, e = process_source(source, apply_hebrew=apply_hebrew)
        total_success += s
        total_errors += e

    log.info(f"All done: {total_success} packaged, {total_errors} errors")


def main():
    parser = argparse.ArgumentParser(description="Process raw harvest content")
    parser.add_argument("--source", help="Source name to process (e.g., 'yavoh')")
    parser.add_argument("--all", action="store_true", help="Process all sources")
    parser.add_argument(
        "--no-hebrew", action="store_true",
        help="Skip Hebrew term corrections"
    )
    args = parser.parse_args()

    if not args.source and not args.all:
        parser.error("Specify --source NAME or --all")

    apply_hebrew = not args.no_hebrew

    if args.all:
        process_all(apply_hebrew=apply_hebrew)
    else:
        process_source(args.source, apply_hebrew=apply_hebrew)


if __name__ == "__main__":
    main()
