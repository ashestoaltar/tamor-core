#!/usr/bin/env python3
"""
Export library_chunks (id, content) to JSONL for re-embedding.

Streams in batches of 10K to keep memory low.
Output: /mnt/library/harvest/reembed/chunks.jsonl (~1.3 GB for 1.1M chunks)

Usage:
    python3 reembed_export.py [--db PATH] [--output PATH]
"""

import argparse
import json
import os
import sqlite3
import sys
import time


def export_chunks(db_path: str, output_path: str, batch_size: int = 10_000):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    total = conn.execute("SELECT COUNT(*) FROM library_chunks").fetchone()[0]
    print(f"Total chunks to export: {total:,}")

    exported = 0
    start = time.time()

    with open(output_path, "w", encoding="utf-8") as f:
        last_id = 0
        while True:
            rows = conn.execute(
                "SELECT id, content FROM library_chunks WHERE id > ? ORDER BY id LIMIT ?",
                (last_id, batch_size),
            ).fetchall()

            if not rows:
                break

            for row_id, content in rows:
                line = json.dumps({"id": row_id, "content": content or ""})
                f.write(line + "\n")
                last_id = row_id

            exported += len(rows)
            elapsed = time.time() - start
            rate = exported / elapsed if elapsed > 0 else 0
            pct = exported / total * 100 if total > 0 else 100
            print(f"  Exported {exported:,}/{total:,} ({pct:.1f}%) — {rate:.0f} rows/sec", end="\r")

    elapsed = time.time() - start
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    conn.close()

    print(f"\nDone. Exported {exported:,} chunks in {elapsed:.1f}s")
    print(f"Output: {output_path} ({file_size_mb:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Export library chunks to JSONL for re-embedding")
    parser.add_argument(
        "--db",
        default="/home/tamor/tamor-core/api/memory/tamor.db",
        help="Path to tamor.db",
    )
    parser.add_argument(
        "--output",
        default="/mnt/library/harvest/reembed/chunks.jsonl",
        help="Output JSONL path",
    )
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: Database not found: {args.db}")
        sys.exit(1)

    export_chunks(args.db, args.output)


if __name__ == "__main__":
    main()
