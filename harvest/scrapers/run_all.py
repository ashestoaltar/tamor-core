#!/usr/bin/env python3
"""
Run all harvest scrapers — sequential or concurrent.

Usage:
    # Sequential: each scraper finishes before next begins (default)
    python3 run_all.py

    # Concurrent: all scrapers run in parallel
    python3 run_all.py --concurrent

    # Discovery only (build manifests, no downloads)
    python3 run_all.py --discover-only

    # Download only (assumes manifests exist)
    python3 run_all.py --download-only

    # Specific scrapers
    python3 run_all.py --scrapers torah_resource yavoh

    # Test run with limit
    python3 run_all.py --limit 5

    # Dry run (show what would run)
    python3 run_all.py --dry-run
"""

import argparse
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime

# ---------------------------------------------------------------------------
# Scraper definitions — add new scrapers here
# ---------------------------------------------------------------------------

SCRAPERS = [
    {
        "name": "torah_class",
        "script": "torah_class.py",
        "discover_args": ["--discover"],
        "download_args": ["--download", "--all"],
        "description": "Torah Class (Tom Bradford) — verse-by-verse Bible studies",
    },
    {
        "name": "torah_resource",
        "script": "torah_resource.py",
        "discover_args": ["--discover"],
        "download_args": ["--download", "--all"],
        "description": "TorahResource (Tim Hegg) — articles + Torah commentaries",
    },
    {
        "name": "yavoh",
        "script": "yavoh.py",
        "discover_args": ["--discover"],
        "download_args": ["--download", "--all"],
        "description": "YAVOH Magazine (Monte Judah) — messianic teachings",
    },
    {
        "name": "founders_online",
        "script": "founders_online.py",
        "discover_args": ["--discover"],
        "download_args": ["--download", "--all", "--resume"],
        "description": "Founders Online (National Archives) — ~184K founding-era documents via API",
    },
]


def get_scraper_dir():
    """Return the directory containing this script."""
    import os
    return os.path.dirname(os.path.abspath(__file__))


def run_scraper(scraper, phase, limit=None, delay=None):
    """
    Run a single scraper phase.

    Args:
        scraper: Scraper definition dict
        phase: "discover" or "download"
        limit: Optional download limit
        delay: Optional request delay

    Returns:
        (name, phase, returncode, elapsed_seconds, output_tail)
    """
    scraper_dir = get_scraper_dir()
    script_path = f"{scraper_dir}/{scraper['script']}"

    if phase == "discover":
        args = [sys.executable, script_path] + scraper["discover_args"]
    else:
        args = [sys.executable, script_path] + scraper["download_args"]
        if limit:
            args += ["--limit", str(limit)]

    if delay:
        args += ["--delay", str(delay)]

    start = time.time()
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=7200,  # 2 hour max per scraper
        )
        elapsed = time.time() - start

        # Get last 20 lines of output for summary
        output = result.stdout + result.stderr
        tail = "\n".join(output.strip().split("\n")[-20:])

        return (scraper["name"], phase, result.returncode, elapsed, tail)

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        return (scraper["name"], phase, -1, elapsed, "TIMEOUT after 2 hours")
    except Exception as e:
        elapsed = time.time() - start
        return (scraper["name"], phase, -2, elapsed, str(e))


def print_result(result):
    """Print a scraper result."""
    name, phase, code, elapsed, tail = result
    status = "OK" if code == 0 else f"FAILED (code={code})"
    mins = elapsed / 60

    print(f"\n{'='*60}")
    print(f"  {name} — {phase} — {status} — {mins:.1f} min")
    print(f"{'='*60}")
    if tail:
        for line in tail.split("\n"):
            print(f"  {line}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Run all harvest scrapers"
    )
    parser.add_argument(
        "--concurrent", action="store_true",
        help="Run scrapers concurrently (default: sequential)"
    )
    parser.add_argument(
        "--discover-only", action="store_true",
        help="Only run discovery phase (build manifests)"
    )
    parser.add_argument(
        "--download-only", action="store_true",
        help="Only run download phase (requires existing manifests)"
    )
    parser.add_argument(
        "--scrapers", nargs="+", metavar="NAME",
        help="Only run specific scrapers (by name)"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Limit downloads per scraper"
    )
    parser.add_argument(
        "--delay", type=float, default=None,
        help="Override request delay (seconds)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would run without executing"
    )
    parser.add_argument(
        "--workers", type=int, default=3,
        help="Max concurrent workers (default: 3)"
    )

    args = parser.parse_args()

    # Filter scrapers
    scrapers = SCRAPERS
    if args.scrapers:
        names = set(args.scrapers)
        scrapers = [s for s in scrapers if s["name"] in names]
        unknown = names - {s["name"] for s in scrapers}
        if unknown:
            print(f"Unknown scrapers: {', '.join(unknown)}")
            print(f"Available: {', '.join(s['name'] for s in SCRAPERS)}")
            sys.exit(1)

    if not scrapers:
        print("No scrapers to run.")
        sys.exit(1)

    # Determine phases
    phases = []
    if not args.download_only:
        phases.append("discover")
    if not args.discover_only:
        phases.append("download")

    # Build task list
    tasks = []
    for phase in phases:
        for scraper in scrapers:
            tasks.append((scraper, phase))

    print(f"\n{'#'*60}")
    print(f"  Harvest Runner — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Mode: {'concurrent' if args.concurrent else 'sequential'}")
    print(f"  Scrapers: {len(scrapers)}")
    print(f"  Phases: {', '.join(phases)}")
    if args.limit:
        print(f"  Limit: {args.limit} per scraper")
    print(f"{'#'*60}")

    for scraper, phase in tasks:
        print(f"  [{phase:10s}] {scraper['name']:20s} — {scraper['description']}")

    if args.dry_run:
        print("\n  (dry run — nothing executed)")
        return

    print()
    start_all = time.time()
    results = []

    if args.concurrent:
        # Run all tasks concurrently (grouped by phase)
        for phase in phases:
            phase_tasks = [(s, phase) for s, p in tasks if p == phase]
            print(f"--- Starting {phase} phase ({len(phase_tasks)} scrapers) ---")

            with ProcessPoolExecutor(max_workers=args.workers) as executor:
                futures = {
                    executor.submit(run_scraper, s, phase, args.limit, args.delay): s
                    for s, _ in phase_tasks
                }
                for future in as_completed(futures):
                    result = future.result()
                    print_result(result)
                    results.append(result)

            # Wait for discover to finish before download
            if phase == "discover" and "download" in phases:
                print("--- Discovery complete, starting downloads ---\n")
    else:
        # Sequential: discover all, then download all
        for scraper, phase in tasks:
            print(f"--- Running {scraper['name']} {phase} ---")
            result = run_scraper(scraper, phase, args.limit, args.delay)
            print_result(result)
            results.append(result)

    # Summary
    total_elapsed = time.time() - start_all
    ok = sum(1 for _, _, code, _, _ in results if code == 0)
    failed = len(results) - ok

    print(f"\n{'#'*60}")
    print(f"  SUMMARY")
    print(f"  Total time: {total_elapsed/60:.1f} min")
    print(f"  Tasks: {ok} OK, {failed} failed")
    print(f"{'#'*60}")

    for name, phase, code, elapsed, _ in results:
        status = "OK" if code == 0 else "FAIL"
        print(f"  [{status}] {name:20s} {phase:10s} ({elapsed/60:.1f} min)")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
