"""
Tamor Database Migration Runner

Handles database schema migrations with:
- Version tracking in migrations table
- Checksum validation
- Migration history
- Dry-run support
- Validation utilities

Usage:
    python -m utils.run_migrations [--dry-run] [--validate] [--status]
"""

import hashlib
import os
import sys
from datetime import datetime

from utils.db import get_db


MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "migrations"
)


def get_file_checksum(filepath: str) -> str:
    """Calculate MD5 checksum of a migration file."""
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def ensure_migrations_table(conn):
    """Create the migrations tracking table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version INTEGER NOT NULL,
            name TEXT NOT NULL,
            checksum TEXT,
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(version)
        )
    """)
    conn.commit()


def get_applied_migrations(conn) -> dict:
    """Get all applied migrations as {version: {name, checksum, applied_at}}."""
    ensure_migrations_table(conn)
    cur = conn.execute(
        "SELECT version, name, checksum, applied_at FROM migrations ORDER BY version"
    )
    return {
        row["version"]: {
            "name": row["name"],
            "checksum": row["checksum"],
            "applied_at": row["applied_at"]
        }
        for row in cur.fetchall()
    }


def get_legacy_version(conn) -> int:
    """Get version from legacy schema_version table (for migration)."""
    try:
        cur = conn.execute("SELECT version FROM schema_version LIMIT 1")
        row = cur.fetchone()
        return row["version"] if row else 0
    except Exception:
        return 0


def get_pending_migrations() -> list:
    """Get list of migration files sorted by version."""
    if not os.path.isdir(MIGRATIONS_DIR):
        return []

    migrations = []
    for filename in os.listdir(MIGRATIONS_DIR):
        if not filename.endswith(".sql"):
            continue

        try:
            version = int(filename.split("_")[0])
        except (ValueError, IndexError):
            print(f"Warning: Skipping invalid migration filename: {filename}")
            continue

        filepath = os.path.join(MIGRATIONS_DIR, filename)
        migrations.append({
            "version": version,
            "name": filename,
            "path": filepath,
            "checksum": get_file_checksum(filepath)
        })

    return sorted(migrations, key=lambda m: m["version"])


def migrate_from_legacy(conn):
    """
    Migrate from legacy schema_version tracking to new migrations table.
    This handles existing databases that used the old single-version tracking.
    """
    legacy_version = get_legacy_version(conn)
    applied = get_applied_migrations(conn)

    if legacy_version > 0 and not applied:
        print(f"Migrating from legacy schema_version (v{legacy_version})...")

        # Mark all migrations up to legacy_version as applied
        all_migrations = get_pending_migrations()
        for migration in all_migrations:
            if migration["version"] <= legacy_version:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO migrations (version, name, checksum, applied_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        migration["version"],
                        migration["name"],
                        migration["checksum"],
                        datetime.now().isoformat()
                    )
                )
        conn.commit()
        print(f"Migrated {legacy_version} version(s) to new tracking system.")


def run(dry_run: bool = False) -> bool:
    """
    Run pending migrations.

    Args:
        dry_run: If True, only show what would be done without applying.

    Returns:
        True if successful, False if errors occurred.
    """
    conn = get_db()

    try:
        ensure_migrations_table(conn)
        migrate_from_legacy(conn)

        applied = get_applied_migrations(conn)
        all_migrations = get_pending_migrations()

        pending = [m for m in all_migrations if m["version"] not in applied]

        if not pending:
            print("No pending migrations.")
            return True

        print(f"Found {len(pending)} pending migration(s):")
        for m in pending:
            print(f"  - {m['name']}")

        if dry_run:
            print("\nDry run - no changes applied.")
            return True

        print()

        for migration in pending:
            print(f"Applying: {migration['name']}...")

            try:
                with open(migration["path"], "r") as f:
                    sql = f.read()

                conn.executescript(sql)

                conn.execute(
                    """
                    INSERT INTO migrations (version, name, checksum, applied_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        migration["version"],
                        migration["name"],
                        migration["checksum"],
                        datetime.now().isoformat()
                    )
                )
                conn.commit()

                # Also update legacy schema_version for backwards compatibility
                conn.execute(
                    "UPDATE schema_version SET version = ?",
                    (migration["version"],)
                )
                conn.commit()

                print(f"  Applied successfully.")

            except Exception as e:
                print(f"  ERROR: {e}")
                conn.rollback()
                return False

        print("\nAll migrations applied successfully.")
        return True

    finally:
        conn.close()


def validate() -> bool:
    """
    Validate migration state and checksums.

    Returns:
        True if valid, False if issues found.
    """
    conn = get_db()

    try:
        ensure_migrations_table(conn)
        applied = get_applied_migrations(conn)
        all_migrations = get_pending_migrations()

        issues = []

        # Check for missing migration files
        migration_versions = {m["version"] for m in all_migrations}
        for version, info in applied.items():
            if version not in migration_versions:
                issues.append(
                    f"Missing file: Migration v{version} ({info['name']}) "
                    f"was applied but file not found"
                )

        # Check checksums
        for migration in all_migrations:
            if migration["version"] in applied:
                recorded = applied[migration["version"]]["checksum"]
                if recorded and recorded != migration["checksum"]:
                    issues.append(
                        f"Checksum mismatch: {migration['name']} "
                        f"(recorded: {recorded[:8]}..., current: {migration['checksum'][:8]}...)"
                    )

        # Check for gaps in version sequence
        if all_migrations:
            versions = sorted(m["version"] for m in all_migrations)
            for i, v in enumerate(versions):
                if i > 0 and v != versions[i-1] + 1:
                    # Allow gaps but warn
                    pass

        if issues:
            print("Validation issues found:")
            for issue in issues:
                print(f"  - {issue}")
            return False

        print("Validation passed: All migrations are consistent.")
        return True

    finally:
        conn.close()


def status():
    """Print current migration status."""
    conn = get_db()

    try:
        ensure_migrations_table(conn)
        migrate_from_legacy(conn)

        applied = get_applied_migrations(conn)
        all_migrations = get_pending_migrations()

        print("Migration Status")
        print("=" * 60)

        if not all_migrations:
            print("No migration files found.")
            return

        for migration in all_migrations:
            version = migration["version"]
            name = migration["name"]

            if version in applied:
                info = applied[version]
                applied_at = info["applied_at"][:19] if info["applied_at"] else "unknown"
                checksum_ok = (
                    info["checksum"] == migration["checksum"]
                    if info["checksum"] else True
                )
                status_icon = "✓" if checksum_ok else "!"
                print(f"  [{status_icon}] v{version:03d} {name}")
                print(f"        Applied: {applied_at}")
                if not checksum_ok:
                    print(f"        WARNING: Checksum mismatch")
            else:
                print(f"  [ ] v{version:03d} {name}")
                print(f"        Pending")

        pending_count = len([m for m in all_migrations if m["version"] not in applied])
        print()
        print(f"Total: {len(all_migrations)} migrations, {pending_count} pending")

    finally:
        conn.close()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Tamor Database Migration Runner"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be done without applying"
    )
    parser.add_argument(
        "--validate", "-v",
        action="store_true",
        help="Validate migration state and checksums"
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show current migration status"
    )

    args = parser.parse_args()

    if args.status:
        status()
    elif args.validate:
        success = validate()
        sys.exit(0 if success else 1)
    else:
        success = run(dry_run=args.dry_run)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
