#!/bin/bash
# BGE-M3 Re-embedding Orchestration Script
#
# Runs the full pipeline:
#   1. Export library_chunks to JSONL (skip if exists)
#   2. Distribute worker script and start encoding on 4 machines
#   3. Monitor progress until all workers complete
#   4. Backup database
#   5. Stop Tamor API
#   6. Merge embeddings into database
#   7. Update config files
#   8. Restart API
#   9. Generate new reference embeddings
#
# Usage:
#   bash harvest/scripts/reembed_orchestrate.sh
#
# Prerequisites:
#   - bge-m3 pre-downloaded on all 4 machines
#   - NAS mounted on all machines
#   - SSH access to worker machines

set -euo pipefail

# ---- Configuration ----
TAMOR_HOME="/home/tamor/tamor-core"
DB_PATH="$TAMOR_HOME/api/memory/tamor.db"
REEMBED_DIR="/mnt/library/harvest/reembed"
WORKER_SCRIPT="$TAMOR_HOME/harvest/scripts/reembed_worker.py"
EXPORT_SCRIPT="$TAMOR_HOME/harvest/scripts/reembed_export.py"
MERGE_SCRIPT="$TAMOR_HOME/harvest/scripts/reembed_merge.py"

# Worker machines (machine-id 0 = Tamor, 1 = processor-1, 2 = processor-2, 3 = scraper)
REMOTE_WORKERS=("processor-1" "processor-2" "scraper")
TOTAL_MACHINES=4

# Python environments
LOCAL_VENV="$TAMOR_HOME/api/venv/bin/activate"
REMOTE_VENV="~/harvest-env/bin/activate"

MONITOR_INTERVAL=60  # seconds between progress checks

# ---- Helpers ----
log() { echo "[$(date '+%H:%M:%S')] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

check_ssh() {
    local host="$1"
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$host" "true" 2>/dev/null; then
        die "Cannot SSH to $host"
    fi
    log "$host: SSH OK"
}

# ---- Pre-flight checks ----
log "=== Pre-flight checks ==="

# Check NAS mount
mountpoint -q /mnt/library || die "NAS not mounted at /mnt/library"
log "NAS: mounted"

# Check SSH and NAS on all remote workers
for host in "${REMOTE_WORKERS[@]}"; do
    check_ssh "$host"
    ssh "$host" "mountpoint -q /mnt/library" 2>/dev/null || die "$host: NAS not mounted"
    log "$host: NAS mounted"
done

# Check DB exists
[ -f "$DB_PATH" ] || die "Database not found: $DB_PATH"

# Check disk space on Tamor (~14 GB needed: DB grows + backup)
local_free_gb=$(df --output=avail "$TAMOR_HOME/api/memory" | tail -1 | awk '{printf "%.0f", $1/1048576}')
log "Tamor disk free: ${local_free_gb} GB"
if [ "$local_free_gb" -lt 14 ]; then
    die "Need ~14 GB free on Tamor disk, have ${local_free_gb} GB"
fi

# Check NAS space (~7 GB needed with 4 workers)
nas_free_gb=$(df --output=avail /mnt/library | tail -1 | awk '{printf "%.0f", $1/1048576}')
log "NAS free: ${nas_free_gb} GB"
if [ "$nas_free_gb" -lt 7 ]; then
    die "Need ~7 GB free on NAS, have ${nas_free_gb} GB"
fi

log "Pre-flight checks passed."
echo ""

# ---- Step 1: Export chunks to JSONL ----
log "=== Step 1: Exporting chunks to JSONL ==="
mkdir -p "$REEMBED_DIR"

if [ -f "$REEMBED_DIR/chunks.jsonl" ]; then
    jsonl_size=$(du -h "$REEMBED_DIR/chunks.jsonl" | cut -f1)
    log "JSONL already exists ($jsonl_size) — skipping export"
else
    source "$LOCAL_VENV"
    python3 "$EXPORT_SCRIPT" --db "$DB_PATH" --output "$REEMBED_DIR/chunks.jsonl"
    [ -f "$REEMBED_DIR/chunks.jsonl" ] || die "Export failed — JSONL not created"
    jsonl_size=$(du -h "$REEMBED_DIR/chunks.jsonl" | cut -f1)
    log "Export complete: $jsonl_size"
fi
echo ""

# ---- Step 2: Deploy worker script and start encoding ----
log "=== Step 2: Starting workers ==="

# Copy worker script to all remote machines
for host in "${REMOTE_WORKERS[@]}"; do
    scp -q "$WORKER_SCRIPT" "$host:~/reembed_worker.py"
    log "$host: worker script deployed"
done

# Start remote workers (machine-id 1 = processor-1, 2 = processor-2, 3 = scraper)
for idx in "${!REMOTE_WORKERS[@]}"; do
    host="${REMOTE_WORKERS[$idx]}"
    mid=$((idx + 1))
    log "Starting worker on $host (machine-id $mid)..."
    ssh "$host" "nohup bash -c 'source $REMOTE_VENV && python3 ~/reembed_worker.py --machine-id $mid --total-machines $TOTAL_MACHINES' > ~/reembed.log 2>&1 &"
done

# Start local worker (machine-id 0) in background
log "Starting local worker (machine-id 0)..."
source "$LOCAL_VENV"
nohup python3 "$WORKER_SCRIPT" --machine-id 0 --total-machines "$TOTAL_MACHINES" > "$TAMOR_HOME/reembed-local.log" 2>&1 &
LOCAL_PID=$!
log "Local worker PID: $LOCAL_PID"
echo ""

# ---- Step 3: Monitor progress ----
log "=== Step 3: Monitoring workers (every ${MONITOR_INTERVAL}s) ==="
log "Press Ctrl+C to stop monitoring (workers continue in background)"
echo ""

while true; do
    all_done=true
    echo "--- $(date '+%Y-%m-%d %H:%M:%S') ---"

    for i in $(seq 0 $((TOTAL_MACHINES - 1))); do
        marker="$REEMBED_DIR/done-${i}.marker"
        pkl="$REEMBED_DIR/embeddings-${i}.pkl"

        if [ -f "$marker" ]; then
            echo "  Machine $i: DONE"
        elif [ -f "$pkl" ]; then
            pkl_size=$(du -h "$pkl" | cut -f1)
            echo "  Machine $i: in progress ($pkl_size)"
            all_done=false
        else
            echo "  Machine $i: not started or no output yet"
            all_done=false
        fi
    done

    # Check if remote workers are still running
    for idx in "${!REMOTE_WORKERS[@]}"; do
        host="${REMOTE_WORKERS[$idx]}"
        mid=$((idx + 1))
        marker="$REEMBED_DIR/done-${mid}.marker"
        if [ ! -f "$marker" ]; then
            running=$(ssh -o ConnectTimeout=3 "$host" "pgrep -f reembed_worker || true" 2>/dev/null)
            if [ -z "$running" ]; then
                echo "  WARNING: $host worker not running!"
            fi
        fi
    done

    # Check local worker
    if [ ! -f "$REEMBED_DIR/done-0.marker" ]; then
        if ! kill -0 "$LOCAL_PID" 2>/dev/null; then
            echo "  WARNING: Local worker (PID $LOCAL_PID) not running!"
        fi
    fi

    echo ""

    if $all_done; then
        log "All workers completed!"
        break
    fi

    sleep "$MONITOR_INTERVAL"
done

echo ""

# ---- Step 4: Backup database ----
log "=== Step 4: Backing up database ==="
BACKUP_PATH="${DB_PATH}.backup-pre-bge-m3"
if [ -f "$BACKUP_PATH" ]; then
    log "Backup already exists: $BACKUP_PATH"
else
    cp "$DB_PATH" "$BACKUP_PATH"
    backup_size=$(du -h "$BACKUP_PATH" | cut -f1)
    log "Backup created: $BACKUP_PATH ($backup_size)"
fi
echo ""

# ---- Step 5: Stop Tamor API ----
log "=== Step 5: Stopping Tamor API ==="
if sudo systemctl is-active --quiet tamor 2>/dev/null; then
    sudo systemctl stop tamor
    log "Tamor API stopped"
else
    log "Tamor API was not running (or not a systemd service)"
fi
echo ""

# ---- Step 6: Merge embeddings ----
log "=== Step 6: Merging embeddings into database ==="
source "$LOCAL_VENV"
python3 "$MERGE_SCRIPT" --db "$DB_PATH" --reembed-dir "$REEMBED_DIR" --total-machines "$TOTAL_MACHINES"
echo ""

# ---- Step 7: Update config files ----
log "=== Step 7: Updating config files ==="

# Update .env
ENV_FILE="$TAMOR_HOME/api/.env"
if grep -q "^EMBEDDING_MODEL=" "$ENV_FILE"; then
    sed -i 's/^EMBEDDING_MODEL=.*/EMBEDDING_MODEL=BAAI\/bge-m3/' "$ENV_FILE"
    log "Updated $ENV_FILE: EMBEDDING_MODEL=BAAI/bge-m3"
else
    echo "EMBEDDING_MODEL=BAAI/bge-m3" >> "$ENV_FILE"
    log "Added EMBEDDING_MODEL to $ENV_FILE"
fi

# Update harvest_config.py
HARVEST_CONFIG="$TAMOR_HOME/harvest/config/harvest_config.py"
sed -i 's/^EMBEDDING_MODEL = .*/EMBEDDING_MODEL = "BAAI\/bge-m3"/' "$HARVEST_CONFIG"
sed -i 's/^EMBEDDING_DIM = .*/EMBEDDING_DIM = 1024/' "$HARVEST_CONFIG"
log "Updated $HARVEST_CONFIG: model=BAAI/bge-m3, dim=1024"

echo ""

# ---- Step 8: Restart API ----
log "=== Step 8: Restarting Tamor API ==="
if sudo systemctl start tamor 2>/dev/null; then
    log "Tamor API started via systemd"
else
    log "No systemd service. Start manually: cd $TAMOR_HOME && make api"
fi
echo ""

# ---- Step 9: Generate new reference embeddings ----
log "=== Step 9: Generating new reference embeddings ==="
VERIFY_SCRIPT="$TAMOR_HOME/harvest/verify_embeddings.py"
if [ -f "$VERIFY_SCRIPT" ]; then
    source "$LOCAL_VENV"
    python3 "$VERIFY_SCRIPT" --generate
    log "Reference embeddings generated for bge-m3"
else
    log "verify_embeddings.py not found — skip reference generation"
fi
echo ""

# ---- Done ----
log "=========================================="
log "  BGE-M3 Migration Complete!"
log ""
log "  Model: BAAI/bge-m3 (1024-dim)"
log "  Database: $DB_PATH"
log "  Backup: $BACKUP_PATH"
log ""
log "  Rollback instructions:"
log "    sudo systemctl stop tamor"
log "    cp $BACKUP_PATH $DB_PATH"
log "    # Revert .env and harvest_config.py"
log "    sudo systemctl start tamor"
log "=========================================="
