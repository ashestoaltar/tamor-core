#!/usr/bin/env python3
"""
Re-embedding worker — runs on each machine in the cluster.

Reads the exported JSONL, filters to its assigned slice (id % total_machines == machine_id),
encodes with BAAI/bge-m3, and saves results as a pickle file on NAS.

Features:
  - Resume support: reloads existing pickle on restart, skips completed IDs
  - Atomic saves: writes to temp file then os.replace() every 5K chunks
  - Completion marker: writes done-{id}.marker when finished

Usage:
    python3 reembed_worker.py --machine-id 0 --total-machines 3
    python3 reembed_worker.py --machine-id 1 --total-machines 3
    python3 reembed_worker.py --machine-id 2 --total-machines 3
"""

import argparse
import json
import os
import pickle
import sys
import time

import numpy as np


def load_existing_results(pkl_path: str) -> dict:
    """Load previously saved results for resume support."""
    if os.path.exists(pkl_path):
        with open(pkl_path, "rb") as f:
            data = pickle.load(f)
        print(f"  Resumed: loaded {len(data):,} existing embeddings from {pkl_path}")
        return data
    return {}


def atomic_save(results: dict, pkl_path: str):
    """Save results atomically via temp file + os.replace."""
    tmp_path = pkl_path + ".tmp"
    with open(tmp_path, "wb") as f:
        pickle.dump(results, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp_path, pkl_path)


def run_worker(
    machine_id: int,
    total_machines: int,
    jsonl_path: str,
    output_dir: str,
    batch_size: int = 32,
    save_interval: int = 5_000,
):
    pkl_path = os.path.join(output_dir, f"embeddings-{machine_id}.pkl")
    marker_path = os.path.join(output_dir, f"done-{machine_id}.marker")

    if os.path.exists(marker_path):
        print(f"Machine {machine_id}: already completed (marker exists). Nothing to do.")
        return

    # Load model
    print(f"Machine {machine_id}/{total_machines}: Loading BAAI/bge-m3...")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("BAAI/bge-m3")
    model.max_seq_length = 512
    dim = model.encode(["test"]).shape[1]
    print(f"  Model loaded. Embedding dimension: {dim}")

    # Load existing results for resume
    results = load_existing_results(pkl_path)
    done_ids = set(results.keys())

    # Read and filter JSONL
    print(f"  Reading {jsonl_path}...")
    my_chunks = []
    total_lines = 0
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            total_lines += 1
            row = json.loads(line)
            chunk_id = row["id"]
            if chunk_id % total_machines == machine_id and chunk_id not in done_ids:
                my_chunks.append((chunk_id, row["content"]))

    already_done = len(done_ids)
    remaining = len(my_chunks)
    my_total = already_done + remaining
    print(f"  Total lines in JSONL: {total_lines:,}")
    print(f"  My slice: {my_total:,} chunks ({already_done:,} done, {remaining:,} remaining)")

    if remaining == 0:
        print("  All chunks already encoded!")
        with open(marker_path, "w") as f:
            f.write(f"completed at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"total embeddings: {len(results)}\n")
        print(f"  Wrote completion marker: {marker_path}")
        return

    # Encode in batches
    start = time.time()
    encoded_this_run = 0
    last_save = 0

    for batch_start in range(0, remaining, batch_size):
        batch = my_chunks[batch_start : batch_start + batch_size]
        ids = [c[0] for c in batch]
        texts = [c[1] for c in batch]

        embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)

        for chunk_id, emb in zip(ids, embeddings):
            results[chunk_id] = emb.astype(np.float32).tobytes()

        encoded_this_run += len(batch)
        total_done = already_done + encoded_this_run

        # Progress
        elapsed = time.time() - start
        rate = encoded_this_run / elapsed if elapsed > 0 else 0
        eta_sec = (remaining - encoded_this_run) / rate if rate > 0 else 0
        eta_h = eta_sec / 3600
        pct = total_done / my_total * 100 if my_total > 0 else 100
        print(
            f"  [{total_done:,}/{my_total:,}] {pct:.1f}% — "
            f"{rate:.1f} chunks/sec — ETA: {eta_h:.1f}h",
            end="\r",
        )

        # Periodic save
        if encoded_this_run - last_save >= save_interval:
            atomic_save(results, pkl_path)
            last_save = encoded_this_run
            size_mb = os.path.getsize(pkl_path) / (1024 * 1024)
            print(f"\n  Saved checkpoint: {len(results):,} embeddings ({size_mb:.1f} MB)")

    # Final save
    atomic_save(results, pkl_path)
    elapsed = time.time() - start
    size_mb = os.path.getsize(pkl_path) / (1024 * 1024)

    print(f"\n  Done! Encoded {encoded_this_run:,} chunks in {elapsed / 3600:.1f}h")
    print(f"  Output: {pkl_path} ({size_mb:.1f} MB)")
    print(f"  Total embeddings in pickle: {len(results):,}")

    # Write completion marker
    with open(marker_path, "w") as f:
        f.write(f"completed at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"total embeddings: {len(results)}\n")
        f.write(f"encoding time: {elapsed / 3600:.1f}h\n")
    print(f"  Wrote completion marker: {marker_path}")


def main():
    parser = argparse.ArgumentParser(description="BGE-M3 re-embedding worker")
    parser.add_argument("--machine-id", type=int, required=True, help="This machine's ID (0-indexed)")
    parser.add_argument("--total-machines", type=int, default=3, help="Total machines in cluster")
    parser.add_argument(
        "--jsonl",
        default="/mnt/library/harvest/reembed/chunks.jsonl",
        help="Input JSONL path",
    )
    parser.add_argument(
        "--output-dir",
        default="/mnt/library/harvest/reembed",
        help="Output directory for pickle files",
    )
    parser.add_argument("--batch-size", type=int, default=32, help="Encoding batch size")
    args = parser.parse_args()

    if args.machine_id < 0 or args.machine_id >= args.total_machines:
        print(f"ERROR: machine-id must be 0..{args.total_machines - 1}")
        sys.exit(1)

    if not os.path.exists(args.jsonl):
        print(f"ERROR: JSONL not found: {args.jsonl}")
        sys.exit(1)

    run_worker(
        machine_id=args.machine_id,
        total_machines=args.total_machines,
        jsonl_path=args.jsonl,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    main()
