#!/usr/bin/env python3
"""
Run transcription queue with progress display.
Output shows progress bar and time estimates.
"""

import sys
import os
import time

# Add api to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.library import TranscriptionWorker, TranscriptionQueueService

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
    log(msg, flush=True)

def main():
    worker = TranscriptionWorker()
    queue = TranscriptionQueueService()

    # Get initial stats
    stats = queue.get_queue_stats()
    total = stats['pending'] + stats['processing']
    completed_start = stats['completed']

    log(f"\n=== Transcription Queue Processing ===")
    log(f"Total to process: {total}")
    log(f"Already completed: {completed_start}")
    log()

    times = []  # Track processing times for ETA
    processed = 0
    start_time = time.time()

    while True:
        item = queue.get_next_pending()
        if not item:
            break

        item_start = time.time()
        filename = item['filename']

        # Show current file
        log(f"\n[{processed + 1}/{total}] Processing: {filename}")

        result = worker.process_queue_item(item)
        item_time = time.time() - item_start
        times.append(item_time)
        processed += 1

        if result['success']:
            log(f"    Done in {format_time(item_time)}")

            # Calculate ETA
            avg_time = sum(times) / len(times)
            remaining = total - processed
            eta = avg_time * remaining

            # Show progress
            elapsed = time.time() - start_time
            log(f"    {progress_bar(processed, total)}")
            log(f"    Elapsed: {format_time(elapsed)} | ETA: {format_time(eta)} | Avg: {format_time(avg_time)}/file")
        else:
            log(f"    FAILED: {result.get('error', 'unknown')}")

    # Final summary
    total_time = time.time() - start_time
    log(f"\n=== Complete ===")
    log(f"Processed: {processed} files")
    log(f"Total time: {format_time(total_time)}")
    if times:
        log(f"Average time per file: {format_time(sum(times)/len(times))}")

    # Final queue stats
    stats = queue.get_queue_stats()
    log(f"\nQueue status:")
    log(f"  Completed: {stats['completed']}")
    log(f"  Failed: {stats['failed']}")
    log(f"  Pending: {stats['pending']}")

if __name__ == '__main__':
    main()
