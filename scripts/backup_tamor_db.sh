#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/tamor/tamor-core"
DB_PATH="$ROOT_DIR/api/memory/tamor.db"
BACKUP_DIR="$ROOT_DIR/memory/backups"

timestamp="$(date +'%Y%m%d_%H%M%S')"
backup_file="$BACKUP_DIR/tamor_$timestamp.db"

mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB_PATH" ]; then
  echo "ERROR: DB not found at $DB_PATH"
  exit 1
fi

echo "Backing up $DB_PATH -> $backup_file"

# Use sqlite3 .backup for a consistent copy
sqlite3 "$DB_PATH" ".backup '$backup_file'"

echo "Done."
