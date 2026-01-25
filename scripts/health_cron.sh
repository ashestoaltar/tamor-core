#!/usr/bin/env bash
# Cron wrapper for health checks - logs output and can alert on issues
# Add to crontab: 0 8 * * * /home/tamor/tamor-core/scripts/health_cron.sh

set -euo pipefail

ROOT_DIR="/home/tamor/tamor-core"
LOG_FILE="$ROOT_DIR/logs/health_check.log"
SCRIPT="$ROOT_DIR/scripts/health_check.sh"

mkdir -p "$(dirname "$LOG_FILE")"

# Run health check and capture output (strip color codes for log)
output=$("$SCRIPT" 2>&1 | sed 's/\x1b\[[0-9;]*m//g')
exit_code=${PIPESTATUS[0]}

# Log with timestamp
{
    echo "========================================"
    echo "Health check: $(date)"
    echo "========================================"
    echo "$output"
    echo ""
} >> "$LOG_FILE"

# Keep log file from growing too large (keep last 1000 lines)
tail -1000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"

# Exit with the health check's exit code (for cron email alerts)
exit $exit_code
