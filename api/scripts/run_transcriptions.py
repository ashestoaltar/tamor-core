#!/usr/bin/env python3
"""
Run transcription queue with progress display.
Output shows progress bar and time estimates.

Usage:
    python3 run_transcriptions.py                  # Run until queue empty
    python3 run_transcriptions.py --max-hours 8    # Run for max 8 hours
    python3 run_transcriptions.py --max-count 50   # Process max 50 files
    python3 run_transcriptions.py --max-hours 6 --max-count 100  # Either limit
"""

import sys
import os
import time
import argparse

# Add api to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.library import TranscriptionWorker, TranscriptionQueueService

def parse_args():
    parser = argparse.ArgumentParser(description='Process transcription queue')
    parser.add_argument('--max-hours', type=float, default=0,
                        help='Maximum hours to run (0 = unlimited)')
    parser.add_argument('--max-count', type=int, default=0,
                        help='Maximum files to process (0 = unlimited)')
    return parser.parse_args()

def format_time(seconds):
    """Format seconds as h:mm:ss or m:ss"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds//60)}m {int(seconds%60)}s"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h {m}m"

def progress_bar(current, total, width=40):
    """Create a text progress bar"""
    filled = int(width * current / total) if total > 0 else 0
    bar = '=' * filled + '-' * (width - filled)
    percent = (current / total * 100) if total > 0 else 0
    return f"[{bar}] {percent:.1f}%"

def log(msg):
    """Print and flush immediately"""
    print(msg, flush=True)

def main():
    args = parse_args()
    max_seconds = args.max_hours * 3600 if args.max_hours > 0 else float('inf')
    max_count = args.max_count if args.max_count > 0 else float('inf')

    worker = TranscriptionWorker()
    queue = TranscriptionQueueService()

    # Get initial stats
    stats = queue.get_queue_stats()
    total = stats['pending'] + stats['processing']
    completed_start = stats['completed']

    print(f"\n=== Transcription Queue Processing ===")
    print(f"Total to process: {total}")
    print(f"Already completed: {completed_start}")
    if args.max_hours > 0:
        print(f"Time limit: {args.max_hours} hours")
    if args.max_count > 0:
        print(f"Count limit: {args.max_count} files")
    print()

    times = []  # Track processing times for ETA
    processed = 0
    start_time = time.time()
    stop_reason = "queue empty"

    while True:
        # Check time limit
        elapsed = time.time() - start_time
        if elapsed >= max_seconds:
            stop_reason = f"time limit ({args.max_hours}h)"
            break

        # Check count limit
        if processed >= max_count:
            stop_reason = f"count limit ({args.max_count})"
            break

        item = queue.get_next_pending()
        if not item:
            break

        item_start = time.time()
        filename = item['filename']

        # Show current file
        print(f"\n[{processed + 1}/{total}] Processing: {filename}")

        result = worker.process_queue_item(item)
        item_time = time.time() - item_start
        times.append(item_time)
        processed += 1

        if result['success']:
            print(f"    Done in {format_time(item_time)}")

            # Calculate ETA
            avg_time = sum(times) / len(times)
            remaining = min(total - processed, max_count - processed) if max_count < float('inf') else total - processed
            eta = avg_time * remaining

            # Check if we'll hit time limit before count
            time_remaining = max_seconds - (time.time() - start_time)
            if time_remaining < eta and max_seconds < float('inf'):
                eta = time_remaining
                remaining = int(time_remaining / avg_time)

            # Show progress
            elapsed = time.time() - start_time
            print(f"    {progress_bar(processed, total)}")
            print(f"    Elapsed: {format_time(elapsed)} | ETA: {format_time(eta)} | Avg: {format_time(avg_time)}/file")
        else:
            print(f"    FAILED: {result.get('error', 'unknown')}")

    # Final summary
    total_time = time.time() - start_time
    print(f"\n=== Stopped: {stop_reason} ===")
    print(f"Processed: {processed} files")
    print(f"Total time: {format_time(total_time)}")
    if times:
        print(f"Average time per file: {format_time(sum(times)/len(times))}")

    # Final queue stats
    stats = queue.get_queue_stats()
    print(f"\nQueue status:")
    print(f"  Completed: {stats['completed']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Pending: {stats['pending']}")

    if stats['pending'] > 0:
        print(f"\nTo continue: python3 scripts/run_transcriptions.py")

if __name__ == '__main__':
    main()
