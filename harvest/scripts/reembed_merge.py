#!/usr/bin/env python3
"""
Merge re-embedded vectors into tamor.db.

Reads the GPU worker's binary output file and updates library_chunks,
then re-embeds small tables (file_chunks, file_symbols, memories) directly.

Binary format: sequence of (int32 id, float32[1024] embedding) records.
Each record = 4 + 4096 = 4100 bytes.

Prerequisites:
  - GPU worker completion marker present
  - Database backup exists at tamor.db.backup-pre-bge-m3
  - Tamor API is stopped (exclusive DB access)

Usage:
    python3 reembed_merge.py [--db PATH] [--embeddings PATH]
"""

import argparse
import os
import sqlite3
import struct
import sys
import time

import numpy as np


EMBEDDING_DIM = 1024
RECORD_SIZE = 4 + (EMBEDDING_DIM * 4)  # int32 id + float32[1024]


def check_prerequisites(db_path: str, embeddings_path: str):
    """Verify all prerequisites before merge."""
    errors = []

    backup_path = db_path + ".backup-pre-bge-m3"
    if not os.path.exists(backup_path):
        errors.append(f"Backup not found: {backup_path}")

    if not os.path.exists(embeddings_path):
        errors.append(f"Embeddings file not found: {embeddings_path}")

    marker_path = embeddings_path + ".done"
    if not os.path.exists(marker_path):
        errors.append(f"Completion marker not found: {marker_path}")

    if errors:
        print("ERROR: Prerequisites not met:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    print("All prerequisites met.")


def merge_library_chunks(db_path: str, embeddings_path: str, batch_size: int = 5_000):
    """Read binary embeddings file and update library_chunks."""
    print("\n=== Merging library_chunks ===")

    file_size = os.path.getsize(embeddings_path)
    total = file_size // RECORD_SIZE
    print(f"  Embeddings file: {file_size / (1024**2):.0f} MB, {total:,} records")

    # Open DB with WAL mode and large cache
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA cache_size=-2097152")  # 2 GB cache
    conn.execute("PRAGMA synchronous=NORMAL")

    db_count = conn.execute("SELECT COUNT(*) FROM library_chunks").fetchone()[0]
    print(f"  Database has {db_count:,} chunks")

    if total < db_count:
        print(f"  WARNING: Only {total:,} embeddings for {db_count:,} chunks")
        print(f"  {db_count - total:,} chunks will keep old embeddings")

    # Stream binary file and batch-update DB
    start = time.time()
    updated = 0

    with open(embeddings_path, "rb") as f:
        batch = []
        while True:
            raw = f.read(RECORD_SIZE)
            if len(raw) < RECORD_SIZE:
                break

            chunk_id = struct.unpack("<i", raw[:4])[0]
            embedding_blob = raw[4:]
            batch.append((embedding_blob, chunk_id))

            if len(batch) >= batch_size:
                conn.execute("BEGIN")
                conn.executemany(
                    "UPDATE library_chunks SET embedding = ? WHERE id = ?",
                    batch,
                )
                conn.commit()
                updated += len(batch)
                batch.clear()

                elapsed = time.time() - start
                rate = updated / elapsed if elapsed > 0 else 0
                pct = updated / total * 100
                print(f"  Updated {updated:,}/{total:,} ({pct:.1f}%) — {rate:.0f} rows/sec", end="\r")

        # Final batch
        if batch:
            conn.execute("BEGIN")
            conn.executemany(
                "UPDATE library_chunks SET embedding = ? WHERE id = ?",
                batch,
            )
            conn.commit()
            updated += len(batch)

    elapsed = time.time() - start
    print(f"\n  library_chunks: merged {updated:,} embeddings in {elapsed:.1f}s")
    conn.close()


def reembed_small_table(conn, table: str, content_column: str, model):
    """Re-embed a small table directly using the new model."""
    rows = conn.execute(f"SELECT id, {content_column} FROM {table}").fetchall()
    if not rows:
        print(f"  {table}: 0 rows, skipping")
        return

    ids = [r[0] for r in rows]
    texts = [r[1] or "" for r in rows]

    print(f"  {table}: encoding {len(rows)} rows...")
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)

    conn.execute("BEGIN")
    for row_id, emb in zip(ids, embeddings):
        blob = emb.astype(np.float32).tobytes()
        conn.execute(
            f"UPDATE {table} SET embedding = ? WHERE id = ?",
            (blob, row_id),
        )
    conn.commit()
    print(f"  {table}: {len(rows)} rows re-embedded")


def reembed_small_tables(db_path: str):
    """Re-embed file_chunks, file_symbols, and memories with bge-m3."""
    print("\n=== Re-embedding small tables ===")

    from sentence_transformers import SentenceTransformer

    print("  Loading BAAI/bge-m3...")
    model = SentenceTransformer("BAAI/bge-m3")
    model.max_seq_length = 512
    print(f"  Model loaded. Dim: {model.encode(['test']).shape[1]}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    reembed_small_table(conn, "file_chunks", "content", model)
    reembed_small_table(conn, "file_symbols", "snippet", model)
    reembed_small_table(conn, "memories", "content", model)

    conn.close()


def verify_dimensions(db_path: str, expected_dim: int = 1024):
    """Verify all embedding columns have the expected dimension."""
    print(f"\n=== Verifying dimensions (expected: {expected_dim}) ===")
    conn = sqlite3.connect(db_path)

    tables = [
        ("library_chunks", "embedding"),
        ("file_chunks", "embedding"),
        ("file_symbols", "embedding"),
        ("memories", "embedding"),
    ]

    all_ok = True
    for table, col in tables:
        row = conn.execute(
            f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL LIMIT 1"
        ).fetchone()

        if row is None or row[0] is None:
            print(f"  {table}: no embeddings found")
            continue

        blob = row[0]
        dim = len(blob) // 4  # float32 = 4 bytes
        status = "OK" if dim == expected_dim else "MISMATCH"
        print(f"  {table}: dim={dim} [{status}]")
        if dim != expected_dim:
            all_ok = False

        # Spot-check a few more
        sample = conn.execute(
            f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL ORDER BY RANDOM() LIMIT 5"
        ).fetchall()
        for s in sample:
            d = len(s[0]) // 4
            if d != expected_dim:
                print(f"    WARNING: found dim={d} in {table}")
                all_ok = False

    conn.close()

    if all_ok:
        print("\nAll dimensions verified OK.")
    else:
        print("\nWARNING: Dimension mismatches found!")

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Merge re-embedded vectors into tamor.db")
    parser.add_argument(
        "--db",
        default="/home/tamor/tamor-core/api/memory/tamor.db",
        help="Path to tamor.db",
    )
    parser.add_argument(
        "--embeddings",
        default="/mnt/library/harvest/reembed/embeddings-gpu.bin",
        help="Path to binary embeddings file from GPU worker",
    )
    parser.add_argument("--skip-small-tables", action="store_true", help="Skip re-embedding small tables")
    parser.add_argument("--verify-only", action="store_true", help="Only verify dimensions")
    args = parser.parse_args()

    if args.verify_only:
        verify_dimensions(args.db)
        return

    check_prerequisites(args.db, args.embeddings)
    merge_library_chunks(args.db, args.embeddings)

    if not args.skip_small_tables:
        reembed_small_tables(args.db)

    verify_dimensions(args.db)


if __name__ == "__main__":
    main()
