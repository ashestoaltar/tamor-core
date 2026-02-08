#!/bin/bash
# BGE-M3 Re-embedding Monitor Dashboard
# Read-only — safe to run alongside the migration.
# Auto-refreshes every 30 seconds. Ctrl+C to exit.
#
# Usage: bash harvest/scripts/reembed_monitor.sh

REEMBED_DIR="/mnt/library/harvest/reembed"
JSONL="$REEMBED_DIR/chunks.jsonl"
TOTAL_CHUNKS=1115267
TOTAL_MACHINES=4
WORKERS=("tamor" "processor-1" "processor-2" "scraper")
HOSTS=("localhost" "processor-1" "processor-2" "scraper")

# Expected bytes per embedding: 1024 floats * 4 bytes + pickle overhead (~12 bytes/entry)
BYTES_PER_ENTRY=4108
CHUNKS_PER_MACHINE=$(( (TOTAL_CHUNKS + TOTAL_MACHINES - 1) / TOTAL_MACHINES ))

fmt_number() { printf "%'d" "$1" 2>/dev/null || echo "$1"; }
fmt_size() { numfmt --to=iec --suffix=B "$1" 2>/dev/null || echo "${1} bytes"; }
fmt_duration() {
    local secs=$1
    if [ "$secs" -ge 3600 ]; then
        printf "%dh %dm" $((secs/3600)) $(( (secs%3600)/60 ))
    elif [ "$secs" -ge 60 ]; then
        printf "%dm %ds" $((secs/60)) $((secs%60))
    else
        printf "%ds" "$secs"
    fi
}

while true; do
    clear
    echo "  ╔══════════════════════════════════════════════════════════════════╗"
    echo "  ║            BGE-M3 RE-EMBEDDING MIGRATION MONITOR               ║"
    echo "  ║            $(date '+%Y-%m-%d %H:%M:%S')                                ║"
    echo "  ╚══════════════════════════════════════════════════════════════════╝"
    echo ""

    # ---- JSONL status ----
    if [ -f "$JSONL" ]; then
        jsonl_size=$(stat -c%s "$JSONL" 2>/dev/null || echo 0)
        jsonl_lines=$(wc -l < "$JSONL" 2>/dev/null || echo 0)
        echo "  Source: $(fmt_size $jsonl_size) — $(fmt_number $jsonl_lines) chunks exported"
    else
        echo "  Source: JSONL not yet created"
    fi
    echo ""

    # ---- Per-machine status ----
    total_done=0
    total_expected=0
    all_complete=true

    for i in $(seq 0 $((TOTAL_MACHINES - 1))); do
        name="${WORKERS[$i]}"
        host="${HOSTS[$i]}"
        marker="$REEMBED_DIR/done-${i}.marker"
        pkl="$REEMBED_DIR/embeddings-${i}.pkl"

        # Check completion marker
        if [ -f "$marker" ]; then
            status="DONE"
            marker_info=$(cat "$marker" 2>/dev/null)
            embed_count=$(echo "$marker_info" | grep "total embeddings" | grep -o '[0-9]*')
            embed_count=${embed_count:-$CHUNKS_PER_MACHINE}
        elif [ -f "$pkl" ]; then
            status="ENCODING"
            all_complete=false
            pkl_size=$(stat -c%s "$pkl" 2>/dev/null || echo 0)
            # Estimate count from pickle size (rough — pickle has overhead)
            embed_count=$(( pkl_size / BYTES_PER_ENTRY ))
        else
            status="WAITING"
            all_complete=false
            embed_count=0
        fi

        total_done=$(( total_done + embed_count ))
        total_expected=$(( total_expected + CHUNKS_PER_MACHINE ))

        # Machine pct
        if [ "$CHUNKS_PER_MACHINE" -gt 0 ]; then
            pct=$(( embed_count * 100 / CHUNKS_PER_MACHINE ))
        else
            pct=0
        fi

        # Progress bar (30 chars wide)
        bar_filled=$(( pct * 30 / 100 ))
        bar_empty=$(( 30 - bar_filled ))
        bar=$(printf '█%.0s' $(seq 1 $bar_filled 2>/dev/null) 2>/dev/null)
        bar_bg=$(printf '░%.0s' $(seq 1 $bar_empty 2>/dev/null) 2>/dev/null)

        # Status icon
        case "$status" in
            DONE)     icon="✓" ; color="\033[32m" ;;
            ENCODING) icon="⚡" ; color="\033[33m" ;;
            WAITING)  icon="○" ; color="\033[90m" ;;
        esac
        reset="\033[0m"

        echo -e "  ┌─ ${color}${icon} Machine $i: $name${reset} ─────────────────────────────────"

        # Pickle info
        if [ -f "$pkl" ]; then
            pkl_display=$(du -h "$pkl" | cut -f1)
            echo "  │  Pickle:   embeddings-${i}.pkl ($pkl_display)"
        fi

        echo -e "  │  Status:   ${color}${status}${reset}"
        echo "  │  Progress: ~$(fmt_number $embed_count) / $(fmt_number $CHUNKS_PER_MACHINE) chunks ($pct%)"
        echo -e "  │  [$bar$bar_bg]"

        # Check if worker process is running
        if [ "$status" = "ENCODING" ] || [ "$status" = "WAITING" ]; then
            if [ "$host" = "localhost" ]; then
                pid=$(pgrep -f "reembed_worker.*--machine-id $i" 2>/dev/null)
                if [ -n "$pid" ]; then
                    # Get CPU and memory
                    cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null | tr -d ' ')
                    mem=$(ps -p "$pid" -o rss= 2>/dev/null | tr -d ' ')
                    mem_mb=$(( ${mem:-0} / 1024 ))
                    echo "  │  Process:  PID $pid — CPU: ${cpu:-?}% — Mem: ${mem_mb}MB"
                else
                    echo -e "  │  Process:  \033[31mNOT RUNNING\033[0m"
                fi
            else
                remote_info=$(ssh -o ConnectTimeout=3 -o BatchMode=yes "$host" "
                    pid=\$(pgrep -f reembed_worker 2>/dev/null)
                    if [ -n \"\$pid\" ]; then
                        cpu=\$(ps -p \$pid -o %cpu= 2>/dev/null | tr -d ' ')
                        mem=\$(ps -p \$pid -o rss= 2>/dev/null | tr -d ' ')
                        mem_mb=\$(( \${mem:-0} / 1024 ))
                        echo \"PID \$pid — CPU: \${cpu}% — Mem: \${mem_mb}MB\"
                    else
                        echo 'NOT_RUNNING'
                    fi
                " 2>/dev/null)
                if [ "$remote_info" = "NOT_RUNNING" ] || [ -z "$remote_info" ]; then
                    echo -e "  │  Process:  \033[31mNOT RUNNING\033[0m"
                else
                    echo "  │  Process:  $remote_info"
                fi
            fi
        fi

        # Last log line
        if [ "$host" = "localhost" ]; then
            log_file="/home/tamor/tamor-core/reembed-local.log"
            if [ -f "$log_file" ]; then
                last_line=$(tail -1 "$log_file" 2>/dev/null | sed 's/^[[:space:]]*//' | cut -c1-70)
                [ -n "$last_line" ] && echo "  │  Log:      $last_line"
            fi
        else
            last_line=$(ssh -o ConnectTimeout=3 -o BatchMode=yes "$host" "tail -1 ~/reembed.log 2>/dev/null" 2>/dev/null | sed 's/^[[:space:]]*//' | cut -c1-70)
            [ -n "$last_line" ] && echo "  │  Log:      $last_line"
        fi

        echo "  └──────────────────────────────────────────────────────────────"
        echo ""
    done

    # ---- Overall progress ----
    if [ "$total_expected" -gt 0 ]; then
        overall_pct=$(( total_done * 100 / TOTAL_CHUNKS ))
    else
        overall_pct=0
    fi

    # Overall progress bar (50 chars)
    ofilled=$(( overall_pct * 50 / 100 ))
    oempty=$(( 50 - ofilled ))
    obar=$(printf '█%.0s' $(seq 1 $ofilled 2>/dev/null) 2>/dev/null)
    obar_bg=$(printf '░%.0s' $(seq 1 $oempty 2>/dev/null) 2>/dev/null)

    echo "  ┌─ Overall Progress ──────────────────────────────────────────"
    echo "  │  Chunks: ~$(fmt_number $total_done) / $(fmt_number $TOTAL_CHUNKS) ($overall_pct%)"
    echo -e "  │  [$obar$obar_bg]"

    # ETA estimate — based on pickle growth rate
    # Check if we have a start timestamp from the first pickle
    earliest_pkl=""
    for i in $(seq 0 $((TOTAL_MACHINES - 1))); do
        pkl="$REEMBED_DIR/embeddings-${i}.pkl"
        if [ -f "$pkl" ]; then
            earliest_pkl="$pkl"
            break
        fi
    done
    if [ -n "$earliest_pkl" ] && [ "$total_done" -gt 0 ]; then
        start_epoch=$(stat -c%Y "$JSONL" 2>/dev/null || echo 0)
        now_epoch=$(date +%s)
        elapsed=$(( now_epoch - start_epoch ))
        if [ "$elapsed" -gt 60 ] && [ "$total_done" -gt 1000 ]; then
            rate=$(( total_done / elapsed ))
            remaining_chunks=$(( TOTAL_CHUNKS - total_done ))
            if [ "$rate" -gt 0 ]; then
                eta_secs=$(( remaining_chunks / rate ))
                echo "  │  Rate:    ~$(fmt_number $rate) chunks/sec across cluster"
                echo "  │  Elapsed: $(fmt_duration $elapsed)"
                echo "  │  ETA:     ~$(fmt_duration $eta_secs)"
            fi
        fi
    fi

    if $all_complete; then
        echo -e "  │  \033[32mAll workers complete! Merge phase next.\033[0m"
    fi
    echo "  └──────────────────────────────────────────────────────────────"
    echo ""

    # ---- Cluster health ----
    echo "  ┌─ Cluster Health ────────────────────────────────────────────"
    for i in $(seq 0 $((TOTAL_MACHINES - 1))); do
        name="${WORKERS[$i]}"
        host="${HOSTS[$i]}"
        if [ "$host" = "localhost" ]; then
            cpu=$(top -bn1 2>/dev/null | grep 'Cpu(s)' | awk '{printf "%.0f%%", $2}')
            mem=$(free -h 2>/dev/null | awk '/Mem:/{printf "%s / %s", $3, $2}')
            echo "  │  $name: CPU $cpu — Mem $mem"
        else
            info=$(ssh -o ConnectTimeout=3 -o BatchMode=yes "$host" "
                cpu=\$(top -bn1 2>/dev/null | grep 'Cpu(s)' | awk '{printf \"%.0f%%\", \$2}')
                mem=\$(free -h 2>/dev/null | awk '/Mem:/{printf \"%s / %s\", \$3, \$2}')
                echo \"\$cpu — Mem \$mem\"
            " 2>/dev/null)
            if [ -n "$info" ]; then
                echo "  │  $name: CPU $info"
            else
                echo -e "  │  $name: \033[31mUNREACHABLE\033[0m"
            fi
        fi
    done

    # NAS space
    nas_free=$(df -h /mnt/library 2>/dev/null | awk 'NR==2{print $4}')
    reembed_used=$(du -sh "$REEMBED_DIR" 2>/dev/null | cut -f1)
    echo "  │  NAS: ${reembed_used:-?} used in reembed/ — ${nas_free:-?} free"
    echo "  └──────────────────────────────────────────────────────────────"
    echo ""

    # ---- Orchestrate script status ----
    orch_pid=$(pgrep -f "reembed_orchestrate" 2>/dev/null)
    if [ -n "$orch_pid" ]; then
        echo "  Orchestrate script: running (PID $orch_pid)"
    else
        echo "  Orchestrate script: not running"
    fi

    echo "  Refreshing every 30s. Press Ctrl+C to exit."
    sleep 30
done
