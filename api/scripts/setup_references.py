#!/usr/bin/env python3
"""
Setup script to download initial SWORD modules.

This script downloads Bible translations for offline use.
Run from the api directory.

Usage:
    python -m scripts.setup_references
    python -m scripts.setup_references --modules KJV WEB ASV
    python -m scripts.setup_references --list
    python -m scripts.setup_references --all

Examples:
    # Download default modules (KJV, WEB, ASV, YLT)
    cd api && python -m scripts.setup_references

    # List available modules
    cd api && python -m scripts.setup_references --list

    # Download specific modules
    cd api && python -m scripts.setup_references --modules KJV SBLGNT

    # Download all available modules
    cd api && python -m scripts.setup_references --all
"""

import argparse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.references.sword_manager import SwordManager, SWORD_MODULES
from services.references.storage import ReferenceStorage

# Default modules to download (public domain, English)
# Note: WEB is not available on CrossWire, using SBLGNT for Greek NT instead
DEFAULT_MODULES = ["KJV", "ASV", "YLT", "SBLGNT"]


def print_progress(downloaded: int, total: int):
    """Print download progress bar."""
    if total == 0:
        return
    percent = (downloaded / total) * 100
    bar_length = 30
    filled = int(bar_length * downloaded / total)
    bar = "=" * filled + "-" * (bar_length - filled)
    print(f"\r    [{bar}] {percent:.1f}%", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Setup SWORD reference modules for Tamor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.setup_references              # Download default modules
  python -m scripts.setup_references --list       # List available modules
  python -m scripts.setup_references --modules KJV WEB  # Download specific
  python -m scripts.setup_references --all        # Download all modules
        """
    )
    parser.add_argument(
        "--modules",
        nargs="+",
        default=None,
        metavar="MODULE",
        help="Specific modules to download (e.g., KJV WEB ASV)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available modules and exit"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all available modules"
    )
    parser.add_argument(
        "--remove",
        nargs="+",
        metavar="MODULE",
        help="Remove specified modules"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current installation status"
    )
    args = parser.parse_args()

    # Ensure storage structure exists
    storage = ReferenceStorage()
    print(f"Reference storage: {storage.base_path}")
    print(f"SWORD modules path: {storage.sword_path}")
    print()

    manager = SwordManager()

    # Handle --list
    if args.list:
        print("Available SWORD modules:")
        print("-" * 60)
        for module in manager.list_available():
            installed = "✓" if module["installed"] else " "
            lang = module.get("language", "en")
            print(f"  [{installed}] {module['code']:10} {module['name']}")
            print(f"      Language: {lang}, Size: ~{module['size_mb']}MB")
            if module.get("description"):
                print(f"      {module['description']}")
            print()
        return 0

    # Handle --status
    if args.status:
        installed = manager.list_installed()
        print(f"Installed modules: {len(installed)}")
        for code in installed:
            info = manager.get_module_info(code)
            if info:
                print(f"  - {code}: {info['name']}")
            else:
                print(f"  - {code}")

        config = storage.get_config()
        print(f"\nDefault translation: {config.get('default_translation', 'KJV')}")
        print(f"Enabled modules: {config.get('enabled_modules', [])}")
        return 0

    # Handle --remove
    if args.remove:
        print("Removing modules:")
        for module in args.remove:
            print(f"  {module}: ", end="", flush=True)
            if manager.remove_module(module):
                print("removed")
            else:
                print("not installed")
        return 0

    # Determine which modules to download
    if args.all:
        modules_to_download = list(SWORD_MODULES.keys())
    elif args.modules:
        modules_to_download = [m.upper() for m in args.modules]
    else:
        modules_to_download = DEFAULT_MODULES

    # Validate module names
    available_codes = set(SWORD_MODULES.keys())
    invalid = [m for m in modules_to_download if m not in available_codes]
    if invalid:
        print(f"Error: Unknown modules: {', '.join(invalid)}")
        print(f"Available modules: {', '.join(sorted(available_codes))}")
        return 1

    # Download modules
    print(f"Downloading {len(modules_to_download)} module(s):")
    print("-" * 40)

    success_count = 0
    skip_count = 0
    fail_count = 0

    for module in modules_to_download:
        info = SWORD_MODULES.get(module, {})
        name = info.get("name", module)

        if manager.is_installed(module):
            print(f"  {module}: already installed ({name})")
            skip_count += 1
            continue

        print(f"  {module}: downloading {name} (~{info.get('size_mb', '?')}MB)...")

        try:
            manager.download_module(module, progress_callback=print_progress)
            print("\r" + " " * 50 + "\r", end="")  # Clear progress bar
            print(f"  {module}: ✓ installed")
            success_count += 1
        except Exception as e:
            print(f"\n  {module}: ✗ failed - {e}")
            fail_count += 1

    # Summary
    print("-" * 40)
    print(f"Downloaded: {success_count}, Skipped: {skip_count}, Failed: {fail_count}")

    # Show final status
    print("\nInstalled modules:")
    for module in manager.list_installed():
        info = manager.get_module_info(module)
        name = info["name"] if info else module
        print(f"  - {module}: {name}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
