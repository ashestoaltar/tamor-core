#!/bin/bash
# Monitor GPU re-embedding progress on Windows PC (192.168.68.127)
# Usage: bash harvest/scripts/reembed_gpu_monitor.sh [--loop]

WINDOWS_HOST="gutte@192.168.68.127"
SSH_OPTS="-o ConnectTimeout=5 -o BatchMode=yes"
TOTAL_CHUNKS=1115267
RECORD_SIZE=4100

check_status() {
    clear
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║       BGE-M3 GPU Re-embedding Monitor               ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo ""
    echo "  Host: $WINDOWS_HOST (GTX 1660 SUPER)"
    echo "  Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    # Check connectivity
    if ! ssh $SSH_OPTS "$WINDOWS_HOST" "echo ok" &>/dev/null; then
        echo "  Cannot reach Windows PC — is it on?"
        return
    fi

    # Check for completion marker
    done_check=$(ssh $SSH_OPTS "$WINDOWS_HOST" "powershell -NoProfile -Command \"Test-Path C:\reembed\embeddings-gpu.bin.done\"" 2>/dev/null | tr -d '\r')
    if [ "$done_check" = "True" ]; then
        echo "  Status: COMPLETE"
        echo ""
        ssh $SSH_OPTS "$WINDOWS_HOST" "powershell -NoProfile -Command \"Get-Content C:\reembed\embeddings-gpu.bin.done\"" 2>/dev/null | sed 's/^/  /'
        echo ""
        echo "  Next steps:"
        echo "    1. Copy to NAS:  scp $WINDOWS_HOST:C:/reembed/embeddings-gpu.bin /mnt/library/harvest/reembed/"
        echo "    2. Run merge:    python3 harvest/scripts/reembed_merge.py"
        return
    fi

    # Get file size
    file_bytes=$(ssh $SSH_OPTS "$WINDOWS_HOST" "powershell -NoProfile -Command \"(Get-Item C:\reembed\embeddings-gpu.bin -EA SilentlyContinue).Length\"" 2>/dev/null | tr -d '\r')
    file_bytes=${file_bytes:-0}

    # Get process info
    proc_info=$(ssh $SSH_OPTS "$WINDOWS_HOST" "powershell -NoProfile -Command \"Get-Process python -EA SilentlyContinue | Select-Object Id,CPU,WorkingSet64 | Format-List\"" 2>/dev/null)

    pid=$(echo "$proc_info" | grep "^Id" | awk '{print $NF}' | tr -d '\r')
    cpu_raw=$(echo "$proc_info" | grep "^CPU" | awk '{print $NF}' | tr -d '\r')
    mem_raw=$(echo "$proc_info" | grep "^WorkingSet64" | awk '{print $NF}' | tr -d '\r')

    # Calculate metrics
    records=$((file_bytes / RECORD_SIZE))
    remaining=$((TOTAL_CHUNKS - records))
    size_mb=$(echo "scale=1; $file_bytes / 1048576" | bc)
    expected_mb=$((TOTAL_CHUNKS * RECORD_SIZE / 1048576))

    if [ -n "$mem_raw" ] && [ "$mem_raw" -gt 0 ] 2>/dev/null; then
        mem_gb=$(echo "scale=1; $mem_raw / 1073741824" | bc)
    else
        mem_gb="?"
    fi

    if [ -n "$cpu_raw" ]; then
        cpu_sec=$(echo "$cpu_raw" | cut -d. -f1)
    else
        cpu_sec=0
    fi

    if [ "$cpu_sec" -gt 0 ] 2>/dev/null && [ "$records" -gt 0 ]; then
        rate=$(echo "scale=1; $records / $cpu_sec" | bc)
        eta_sec=$(echo "scale=0; $remaining / $rate" | bc 2>/dev/null)
        eta_h=$(echo "scale=1; $eta_sec / 3600" | bc)
    else
        rate="?"
        eta_h="?"
    fi

    pct_100x=$((records * 10000 / TOTAL_CHUNKS))
    pct_int=$((pct_100x / 100))
    pct_dec=$((pct_100x % 100))

    if [ -z "$pid" ]; then
        echo "  Status: STOPPED (no Python process)"
        echo ""
        echo "  Records written: $records / $TOTAL_CHUNKS"
        echo "  File: ${size_mb} MB"
        echo ""
        echo "  Worker may have crashed. To restart:"
        echo "    ssh $WINDOWS_HOST \"cd C:\\reembed && python reembed_gpu_worker.py --batch-size 128\""
        return
    fi

    echo "  Status: RUNNING (PID $pid)"
    echo ""

    # Progress bar (50 chars wide)
    bar_filled=$((pct_int / 2))
    [ $bar_filled -gt 50 ] && bar_filled=50
    bar_empty=$((50 - bar_filled))
    bar=""
    for ((i=0; i<bar_filled; i++)); do bar+="█"; done
    for ((i=0; i<bar_empty; i++)); do bar+="░"; done
    printf "  [%s] %d.%02d%%\n" "$bar" "$pct_int" "$pct_dec"
    echo ""

    printf "  Chunks:  %10s / %s\n" "$(printf '%d' $records)" "$(printf '%d' $TOTAL_CHUNKS)"
    printf "  File:    %10s / ~%s MB\n" "${size_mb} MB" "$expected_mb"
    printf "  Rate:    %10s\n" "${rate} chunks/sec"
    printf "  ETA:     %10s\n" "${eta_h} hours"
    printf "  Memory:  %10s\n" "${mem_gb} GB"
    echo ""
}

if [ "$1" = "--loop" ]; then
    while true; do
        check_status
        echo "  Refreshing every 60s... (Ctrl+C to quit)"
        sleep 60
    done
else
    check_status
fi
