#!/bin/bash
# Harvest Cluster Monitor
# Run: bash harvest/monitor.sh
# Auto-refreshes every 30 seconds. Ctrl+C to exit.

WORKERS="processor-1 scraper"
HARVEST="/mnt/library/harvest"

while true; do
  clear
  echo "  ╔══════════════════════════════════════════════════════════════╗"
  echo "  ║              TAMOR HARVEST CLUSTER MONITOR                  ║"
  echo "  ║              $(date '+%Y-%m-%d %H:%M:%S')                          ║"
  echo "  ╚══════════════════════════════════════════════════════════════╝"
  echo ""

  for host in $WORKERS; do
    # Check if host is reachable (1 second timeout)
    if ssh -o ConnectTimeout=2 -o BatchMode=yes $host "true" 2>/dev/null; then
      status=$(ssh -o ConnectTimeout=3 $host "
        # Hostname and uptime
        up=\$(uptime -p 2>/dev/null || uptime)

        # CPU usage
        cpu=\$(top -bn1 | grep 'Cpu(s)' | awk '{print \$2}' 2>/dev/null || echo '?')

        # Memory
        mem=\$(free -h | awk '/Mem:/{printf \"%s / %s\", \$3, \$2}')

        # Disk
        disk=\$(df -h / | awk 'NR==2{printf \"%s / %s (%s)\", \$3, \$2, \$5}')

        # Python processes (harvest jobs)
        jobs=\$(ps aux | grep -E 'python.*harvest|python.*process_raw|python.*scrape|python.*download|yt-dlp|whisper' | grep -v grep | wc -l)
        job_names=\$(ps aux | grep -E 'python.*harvest|python.*process_raw|python.*scrape|python.*download|yt-dlp|whisper' | grep -v grep | awk '{for(i=11;i<=NF;i++) printf \"%s \", \$i; print \"\"}' | head -3)

        # NAS mounted
        nas=\$(mountpoint -q /mnt/library && echo 'OK' || echo 'NOT MOUNTED')

        echo \"UP|\$up\"
        echo \"CPU|\${cpu}%\"
        echo \"MEM|\$mem\"
        echo \"DISK|\$disk\"
        echo \"NAS|\$nas\"
        echo \"JOBS|\$jobs\"
        echo \"JOBNAMES|\$job_names\"
      " 2>/dev/null)

      up=$(echo "$status" | grep '^UP|' | cut -d'|' -f2)
      cpu=$(echo "$status" | grep '^CPU|' | cut -d'|' -f2)
      mem=$(echo "$status" | grep '^MEM|' | cut -d'|' -f2)
      disk=$(echo "$status" | grep '^DISK|' | cut -d'|' -f2)
      nas=$(echo "$status" | grep '^NAS|' | cut -d'|' -f2)
      jobs=$(echo "$status" | grep '^JOBS|' | cut -d'|' -f2)
      jobnames=$(echo "$status" | grep '^JOBNAMES|' | cut -d'|' -f2-)

      echo "  ┌─ $host ──────────────────────────────── ● ONLINE"
      echo "  │  Uptime:  $up"
      echo "  │  CPU:     $cpu    Memory: $mem"
      echo "  │  Disk:    $disk"
      echo "  │  NAS:     $nas"
      if [ "$jobs" -gt 0 ] 2>/dev/null; then
        echo "  │  Jobs:    $jobs running"
        echo "$jobnames" | while IFS= read -r line; do
          [ -n "$line" ] && echo "  │           → $line"
        done
      else
        echo "  │  Jobs:    idle"
      fi
      echo "  └──────────────────────────────────────────────────────"
    else
      echo "  ┌─ $host ──────────────────────────────── ○ OFFLINE"
      echo "  │  Cannot connect"
      echo "  └──────────────────────────────────────────────────────"
    fi
    echo ""
  done

  # Harvest pipeline stats from NAS
  raw_count=$(find "$HARVEST/raw" -name "*.json" 2>/dev/null | wc -l)
  processed_count=$(find "$HARVEST/processed" -name "*.json" 2>/dev/null | wc -l)
  ready_count=$(find "$HARVEST/ready" -maxdepth 1 -name "*.json" 2>/dev/null | wc -l)
  imported_count=$(find "$HARVEST/ready/imported" -name "*.json" 2>/dev/null | wc -l)

  echo "  ┌─ Pipeline ────────────────────────────────────────────"
  echo "  │  Raw:        $raw_count files waiting"
  echo "  │  Processed:  $processed_count files"
  echo "  │  Ready:      $ready_count packages to import"
  echo "  │  Imported:   $imported_count packages done"
  echo "  └──────────────────────────────────────────────────────"
  echo ""
  echo "  Refreshing every 30s. Press Ctrl+C to exit."

  sleep 30
done
