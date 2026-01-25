#!/usr/bin/env python3
"""
Transcription Worker Runner

Runs the transcription worker as a background service.
Processes the transcription queue continuously.

Usage:
    python -m scripts.run_transcription_worker [--interval SECONDS]

Options:
    --interval    Poll interval when queue is empty (default: 30)
"""

import sys
import os
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.library.transcription_worker import TranscriptionWorker


def main():
    parser = argparse.ArgumentParser(description='Run transcription worker')
    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        help='Poll interval in seconds when queue is empty (default: 30)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Process one item and exit'
    )
    parser.add_argument(
        '--batch',
        type=int,
        default=0,
        help='Process N items and exit'
    )

    args = parser.parse_args()

    worker = TranscriptionWorker()

    if args.once:
        result = worker.process_next()
        if result:
            print(f"Result: {result}")
        else:
            print("Queue empty")
        return

    if args.batch > 0:
        result = worker.process_batch(count=args.batch)
        print(f"Processed: {result['processed']}, Success: {result['success']}, Failed: {result['failed']}")
        return

    # Run continuously
    worker.run_continuous(poll_interval=args.interval)


if __name__ == '__main__':
    main()
