#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/tamor/tamor-core"
DB_PATH="$ROOT_DIR/api/memory/tamor.db"
UPLOADS_DIR="$ROOT_DIR/api/uploads"
BACKUP_DIR="$ROOT_DIR/memory/backups"

# Retention policy: keep backups for this many days
RETENTION_DAYS=30

timestamp="$(date +'%Y%m%d_%H%M%S')"
db_backup="$BACKUP_DIR/tamor_$timestamp.db"
uploads_backup="$BACKUP_DIR/uploads_$timestamp.tar.gz"

mkdir -p "$BACKUP_DIR"

# --- Database backup ---
if [ ! -f "$DB_PATH" ]; then
  echo "ERROR: DB not found at $DB_PATH"
  exit 1
fi

echo "Backing up database: $DB_PATH -> $db_backup"
sqlite3 "$DB_PATH" ".backup '$db_backup'"

# --- Uploads backup ---
if [ -d "$UPLOADS_DIR" ] && [ "$(ls -A "$UPLOADS_DIR" 2>/dev/null)" ]; then
  echo "Backing up uploads: $UPLOADS_DIR -> $uploads_backup"
  tar -czf "$uploads_backup" -C "$ROOT_DIR/api" uploads
else
  echo "Uploads directory empty or missing, skipping"
fi

# --- Retention: delete backups older than N days ---
echo "Pruning backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "tamor_*.db" -type f -mtime +$RETENTION_DAYS -delete -print
find "$BACKUP_DIR" -name "uploads_*.tar.gz" -type f -mtime +$RETENTION_DAYS -delete -print

echo "Done."
