"""
Tamor Database Validation Utility

Validates database schema integrity and consistency.

Usage:
    python -m utils.db_validate [--fix] [--verbose]
"""

import sys
from utils.db import get_db


# Expected tables in Tamor database
EXPECTED_TABLES = {
    "users",
    "projects",
    "conversations",
    "messages",
    "detected_tasks",
    "task_runs",
    "project_files",
    "file_text_cache",
    "file_chunks",
    "message_file_refs",
    "file_symbols",
    "memories",
    "project_notes",
    "pending_intents",
    "schema_version",
    "migrations",
}

# Required columns for each table (subset for validation)
REQUIRED_COLUMNS = {
    "users": ["id", "username"],
    "projects": ["id", "user_id", "name"],
    "conversations": ["id", "user_id"],
    "messages": ["id", "conversation_id", "content"],
    "detected_tasks": ["id", "user_id", "status"],
    "task_runs": ["id", "task_id", "status"],
    "project_files": ["id", "project_id", "filename", "stored_name"],
    "memories": ["id", "content"],
    "migrations": ["id", "version", "name"],
}


def get_tables(conn) -> set:
    """Get all table names in the database."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return {row["name"] for row in cur.fetchall()}


def get_columns(conn, table: str) -> list:
    """Get column names for a table."""
    cur = conn.execute(f"PRAGMA table_info({table})")
    return [row["name"] for row in cur.fetchall()]


def get_indexes(conn, table: str) -> list:
    """Get indexes for a table."""
    cur = conn.execute(f"PRAGMA index_list({table})")
    return [row["name"] for row in cur.fetchall()]


def check_foreign_keys(conn) -> list:
    """Check for foreign key violations (summarized by table)."""
    issues = []
    cur = conn.execute("PRAGMA foreign_key_check")

    # Group violations by table
    violations = {}
    for row in cur.fetchall():
        table = row[0]
        parent = row[2]
        key = (table, parent)
        violations[key] = violations.get(key, 0) + 1

    for (table, parent), count in violations.items():
        issues.append(
            f"Foreign key violations in {table}: "
            f"{count} row(s) reference missing row(s) in {parent}"
        )

    return issues


def check_integrity(conn) -> list:
    """Run SQLite integrity check."""
    issues = []
    cur = conn.execute("PRAGMA integrity_check")
    result = cur.fetchone()[0]
    if result != "ok":
        issues.append(f"Integrity check failed: {result}")
    return issues


def validate_schema(verbose: bool = False) -> tuple[bool, list]:
    """
    Validate the database schema.

    Returns:
        Tuple of (is_valid, list of issues)
    """
    conn = get_db()
    issues = []

    try:
        # Get existing tables
        existing_tables = get_tables(conn)

        if verbose:
            print(f"Found {len(existing_tables)} tables")

        # Check for missing tables
        missing_tables = EXPECTED_TABLES - existing_tables
        for table in missing_tables:
            issues.append(f"Missing table: {table}")

        # Check for unexpected tables (info only, not an error)
        extra_tables = existing_tables - EXPECTED_TABLES - {"sqlite_sequence"}
        if verbose and extra_tables:
            print(f"Note: Extra tables found: {', '.join(extra_tables)}")

        # Check required columns
        for table, required_cols in REQUIRED_COLUMNS.items():
            if table not in existing_tables:
                continue

            columns = get_columns(conn, table)
            for col in required_cols:
                if col not in columns:
                    issues.append(f"Missing column: {table}.{col}")

        # Check foreign keys
        fk_issues = check_foreign_keys(conn)
        issues.extend(fk_issues)

        # Check integrity
        integrity_issues = check_integrity(conn)
        issues.extend(integrity_issues)

        return len(issues) == 0, issues

    finally:
        conn.close()


def validate_data(verbose: bool = False) -> tuple[bool, list]:
    """
    Validate data consistency.

    Returns:
        Tuple of (is_valid, list of issues)
    """
    conn = get_db()
    issues = []

    try:
        # Check for orphaned conversations (user_id doesn't exist)
        cur = conn.execute("""
            SELECT c.id, c.user_id
            FROM conversations c
            LEFT JOIN users u ON c.user_id = u.id
            WHERE u.id IS NULL
        """)
        for row in cur.fetchall():
            issues.append(f"Orphaned conversation {row['id']}: user_id {row['user_id']} not found")

        # Check for orphaned messages (conversation_id doesn't exist)
        cur = conn.execute("""
            SELECT m.id, m.conversation_id
            FROM messages m
            LEFT JOIN conversations c ON m.conversation_id = c.id
            WHERE c.id IS NULL
        """)
        orphaned_messages = cur.fetchall()
        if orphaned_messages:
            issues.append(f"Found {len(orphaned_messages)} orphaned messages")

        # Check for orphaned project_files (project_id doesn't exist)
        cur = conn.execute("""
            SELECT pf.id, pf.project_id
            FROM project_files pf
            LEFT JOIN projects p ON pf.project_id = p.id
            WHERE p.id IS NULL AND pf.project_id IS NOT NULL
        """)
        orphaned_files = cur.fetchall()
        if orphaned_files:
            issues.append(f"Found {len(orphaned_files)} orphaned project files")

        # Check task status values
        cur = conn.execute("""
            SELECT DISTINCT status FROM detected_tasks
            WHERE status NOT IN (
                'needs_confirmation', 'confirmed', 'cancelled',
                'completed', 'failed', 'paused', 'running'
            )
        """)
        invalid_statuses = [row["status"] for row in cur.fetchall()]
        if invalid_statuses:
            issues.append(f"Invalid task statuses: {', '.join(invalid_statuses)}")

        return len(issues) == 0, issues

    finally:
        conn.close()


def print_summary(conn):
    """Print database summary statistics."""
    tables = get_tables(conn)

    print("\nDatabase Summary")
    print("=" * 40)

    for table in sorted(tables):
        if table == "sqlite_sequence":
            continue
        try:
            cur = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
            count = cur.fetchone()["count"]
            print(f"  {table}: {count} rows")
        except Exception as e:
            print(f"  {table}: ERROR ({e})")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Tamor Database Validation Utility"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show database summary"
    )

    args = parser.parse_args()

    print("Tamor Database Validation")
    print("=" * 40)

    # Schema validation
    print("\nValidating schema...")
    schema_valid, schema_issues = validate_schema(verbose=args.verbose)

    if schema_valid:
        print("  Schema: OK")
    else:
        print("  Schema: ISSUES FOUND")
        for issue in schema_issues:
            print(f"    - {issue}")

    # Data validation
    print("\nValidating data consistency...")
    data_valid, data_issues = validate_data(verbose=args.verbose)

    if data_valid:
        print("  Data: OK")
    else:
        print("  Data: ISSUES FOUND")
        for issue in data_issues:
            print(f"    - {issue}")

    # Summary
    if args.summary:
        conn = get_db()
        try:
            print_summary(conn)
        finally:
            conn.close()

    # Exit status
    all_valid = schema_valid and data_valid
    print()
    if all_valid:
        print("Validation passed.")
        sys.exit(0)
    else:
        print("Validation failed. See issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
