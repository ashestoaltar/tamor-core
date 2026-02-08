#!/usr/bin/env python3
"""
GPU re-embedding worker — memory-efficient streaming version.

Reads JSONL in streaming fashion, encodes with BAAI/bge-m3 on GPU,
writes results directly to a binary file (not pickle, to avoid RAM bloat).

Output format: binary file of (int32 id, float32[1024] embedding) records.
Each record = 4 + 4096 = 4100 bytes.

Usage:
    python reembed_gpu_worker.py
    python reembed_gpu_worker.py --batch-size 32 --jsonl C:/reembed/chunks.jsonl
"""

import argparse
import json
import os
import struct
import sys
import time

import numpy as np


EMBEDDING_DIM = 1024
RECORD_SIZE = 4 + (EMBEDDING_DIM * 4)  # int32 id + float32[1024]


def count_completed(output_path):
    """Count how many records are already in the output file."""
    if not os.path.exists(output_path):
        return set()
    file_size = os.path.getsize(output_path)
    n_records = file_size // RECORD_SIZE
    done_ids = set()
    with open(output_path, "rb") as f:
        for _ in range(n_records):
            raw_id = f.read(4)
            if len(raw_id) < 4:
                break
            chunk_id = struct.unpack("<i", raw_id)[0]
            done_ids.add(chunk_id)
            f.seek(EMBEDDING_DIM * 4, 1)  # skip embedding bytes
    return done_ids


def run_worker(jsonl_path, output_path, batch_size=32, flush_interval=1000):
    marker_path = output_path + ".done"

    if os.path.exists(marker_path):
        print("Already completed. Nothing to do.")
        return

    # Load model on GPU
    print("Loading BAAI/bge-m3 on GPU...", flush=True)
    import torch
    from sentence_transformers import SentenceTransformer

    if not torch.cuda.is_available():
        print("ERROR: CUDA not available!")
        sys.exit(1)

    gpu_name = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"  GPU: {gpu_name} ({vram_gb:.1f} GB VRAM)", flush=True)

    model = SentenceTransformer("BAAI/bge-m3", device="cuda")
    model.max_seq_length = 512
    print(f"  Model loaded. Dim: {EMBEDDING_DIM}", flush=True)

    # Check what's already done (for resume)
    done_ids = count_completed(output_path)
    if done_ids:
        print(f"  Resuming: {len(done_ids):,} already encoded", flush=True)

    # Count total lines first (fast scan)
    print(f"  Counting JSONL lines...", flush=True)
    total_lines = 0
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for _ in f:
            total_lines += 1
    remaining = total_lines - len(done_ids)
    print(f"  Total: {total_lines:,} chunks ({len(done_ids):,} done, {remaining:,} remaining)", flush=True)

    if remaining <= 0:
        print("  All done!", flush=True)
        with open(marker_path, "w") as f:
            f.write(f"completed at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        return

    # Open output file for appending
    out_f = open(output_path, "ab")

    start = time.time()
    encoded = 0
    batch_ids = []
    batch_texts = []

    # Stream through JSONL
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            chunk_id = row["id"]

            if chunk_id in done_ids:
                continue

            batch_ids.append(chunk_id)
            batch_texts.append(row["content"] or "")

            if len(batch_ids) >= batch_size:
                # Encode batch
                embeddings = model.encode(
                    batch_texts, show_progress_bar=False, normalize_embeddings=True
                )

                # Write directly to file
                for cid, emb in zip(batch_ids, embeddings):
                    out_f.write(struct.pack("<i", cid))
                    out_f.write(emb.astype(np.float32).tobytes())

                encoded += len(batch_ids)
                batch_ids.clear()
                batch_texts.clear()

                # Periodic flush
                if encoded % flush_interval < batch_size:
                    out_f.flush()

                # Progress (every 640 chunks = ~20 batches)
                if encoded % (batch_size * 20) == 0:
                    elapsed = time.time() - start
                    rate = encoded / elapsed if elapsed > 0 else 0
                    total_done = len(done_ids) + encoded
                    pct = total_done / total_lines * 100
                    eta_h = (remaining - encoded) / rate / 3600 if rate > 0 else 0
                    vram_used = torch.cuda.memory_allocated() / 1024**3
                    print(
                        f"  [{total_done:,}/{total_lines:,}] {pct:.1f}% | "
                        f"{rate:.1f}/sec | ETA: {eta_h:.1f}h | VRAM: {vram_used:.1f}GB",
                        flush=True,
                    )

    # Final partial batch
    if batch_ids:
        embeddings = model.encode(
            batch_texts, show_progress_bar=False, normalize_embeddings=True
        )
        for cid, emb in zip(batch_ids, embeddings):
            out_f.write(struct.pack("<i", cid))
            out_f.write(emb.astype(np.float32).tobytes())
        encoded += len(batch_ids)

    out_f.flush()
    out_f.close()

    elapsed = time.time() - start
    rate = encoded / elapsed if elapsed > 0 else 0
    size_mb = os.path.getsize(output_path) / (1024 * 1024)

    print(f"\n  Done! {encoded:,} chunks in {elapsed/3600:.1f}h ({rate:.1f}/sec)", flush=True)
    print(f"  Output: {output_path} ({size_mb:.0f} MB)", flush=True)

    with open(marker_path, "w") as f:
        f.write(f"completed at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"total: {len(done_ids) + encoded}\n")
        f.write(f"time: {elapsed/3600:.1f}h\n")
        f.write(f"rate: {rate:.1f}/sec\n")


def main():
    parser = argparse.ArgumentParser(description="BGE-M3 GPU re-embedding (streaming)")
    parser.add_argument("--jsonl", default="C:/reembed/chunks.jsonl", help="Input JSONL")
    parser.add_argument("--output", default="C:/reembed/embeddings-gpu.bin", help="Output binary file")
    parser.add_argument("--batch-size", type=int, default=32, help="Encoding batch size")
    args = parser.parse_args()

    if not os.path.exists(args.jsonl):
        print(f"ERROR: JSONL not found: {args.jsonl}")
        sys.exit(1)

    run_worker(args.jsonl, args.output, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
