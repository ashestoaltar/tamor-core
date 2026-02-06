#!/bin/bash
# Complete library processing: ingest new files, transcribe audio, index everything
# Expected runtime: ~28-29 hours
# Log: /tmp/complete_library.log

set -e
LOG=/tmp/complete_library.log
COOKIES=/tmp/tamor-cookies.txt
API=http://localhost:5055

cd /home/tamor/tamor-core/api
source venv/bin/activate

echo "============================================" | tee -a "$LOG"
echo "  COMPLETE LIBRARY PROCESSING" | tee -a "$LOG"
echo "  Started: $(date)" | tee -a "$LOG"
echo "============================================" | tee -a "$LOG"

# ------------------------------------------------------------------
# STEP 1: Ingest new files from ~/Documents/Research materials/Books/
# ------------------------------------------------------------------
echo "" | tee -a "$LOG"
echo "=== STEP 1: Ingest new files ===" | tee -a "$LOG"
echo "$(date): Ingesting from ~/Documents/Research materials/Books/" | tee -a "$LOG"

result=$(curl -s -b "$COOKIES" -X POST "$API/api/library/ingest" \
  -H "Content-Type: application/json" \
  -d '{"path": "/home/tamor/Documents/Research materials/Books", "auto_index": false}')
echo "$result" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'  Created: {d.get(\"created\", 0)}, Duplicates: {d.get(\"duplicates\", 0)}, Errors: {d.get(\"errors\", 0)}')
" | tee -a "$LOG"

# ------------------------------------------------------------------
# STEP 2: Transcribe all queued audio (new MP3s + any remaining)
# ------------------------------------------------------------------
echo "" | tee -a "$LOG"
echo "=== STEP 2: Transcribe audio ===" | tee -a "$LOG"
echo "$(date): Queuing all untranscribed audio..." | tee -a "$LOG"

# Queue any new audio files
curl -s -b "$COOKIES" -X POST "$API/api/library/transcription/queue-all" \
  -H "Content-Type: application/json" -d '{}' >> "$LOG" 2>&1
echo "" >> "$LOG"

echo "$(date): Running transcriptions..." | tee -a "$LOG"
python3 scripts/run_transcriptions.py 2>&1 | tee -a "$LOG"
echo "$(date): Transcription complete" | tee -a "$LOG"

# ------------------------------------------------------------------
# STEP 3: Index everything (loop until queue empty)
# ------------------------------------------------------------------
echo "" | tee -a "$LOG"
echo "=== STEP 3: Index all files ===" | tee -a "$LOG"
echo "$(date): Starting indexing loop..." | tee -a "$LOG"

batch=0
while true; do
  batch=$((batch + 1))
  result=$(curl -s -b "$COOKIES" -X POST "$API/api/library/index/process" \
    -H "Content-Type: application/json" -d '{"count": 50}')

  remaining=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('remaining', 0))" 2>/dev/null || echo "error")
  processed=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('processed', 0))" 2>/dev/null || echo "0")

  if [ "$remaining" = "error" ]; then
    echo "$(date): API error, retrying in 30s..." | tee -a "$LOG"
    sleep 30
    continue
  fi

  # Log every 10 batches to avoid huge log files
  if [ $((batch % 10)) -eq 0 ] || [ "$remaining" -eq 0 ]; then
    echo "$(date): Batch $batch - Processed: $processed, Remaining: $remaining" | tee -a "$LOG"
  fi

  if [ "$remaining" -eq 0 ]; then
    echo "$(date): All files indexed!" | tee -a "$LOG"
    break
  fi

  sleep 1
done

# ------------------------------------------------------------------
# DONE
# ------------------------------------------------------------------
echo "" | tee -a "$LOG"
echo "============================================" | tee -a "$LOG"
echo "  COMPLETE" | tee -a "$LOG"
echo "  Finished: $(date)" | tee -a "$LOG"
echo "============================================" | tee -a "$LOG"

# Final status
echo "" | tee -a "$LOG"
curl -s -b "$COOKIES" "$API/api/library/index/queue" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'Final status: {d.get(\"indexed\", 0)} indexed, {d.get(\"unindexed\", 0)} unindexed')
" | tee -a "$LOG"
