#!/bin/bash
# Deploy harvest toolkit to a worker machine from Tamor.
#
# Usage:
#   ./deploy_to_worker.sh processor-1 processor
#   ./deploy_to_worker.sh scraper network
#
# Args:
#   $1 = hostname or IP of the worker
#   $2 = role: "processor" or "network"

set -e

WORKER="${1:?Usage: deploy_to_worker.sh HOSTNAME ROLE}"
ROLE="${2:?Usage: deploy_to_worker.sh HOSTNAME ROLE}"
USER="harvest"
HARVEST_DIR="/home/tamor/tamor-core/harvest"
REMOTE_DIR="/home/$USER/harvest-tools"

echo "Deploying to $USER@$WORKER (role: $ROLE)"
echo ""

# 1. Run setup script
echo "=== Running setup script ==="
ssh "$USER@$WORKER" "bash -s $ROLE" < "$HARVEST_DIR/deploy/setup_worker.sh"

# 2. Deploy toolkit files
echo ""
echo "=== Deploying toolkit files ==="
ssh "$USER@$WORKER" "mkdir -p $REMOTE_DIR/{config,lib,processor,scrapers,downloaders}"

# Core files
scp "$HARVEST_DIR/config/harvest_config.py" "$USER@$WORKER:$REMOTE_DIR/config/"
scp "$HARVEST_DIR/config/__init__.py" "$USER@$WORKER:$REMOTE_DIR/config/"
scp "$HARVEST_DIR/lib/__init__.py" "$USER@$WORKER:$REMOTE_DIR/lib/"
scp "$HARVEST_DIR/lib/chunker.py" "$USER@$WORKER:$REMOTE_DIR/lib/"
scp "$HARVEST_DIR/lib/hebrew_corrections.py" "$USER@$WORKER:$REMOTE_DIR/lib/"
scp "$HARVEST_DIR/verify_embeddings.py" "$USER@$WORKER:$REMOTE_DIR/"

if [ "$ROLE" = "processor" ]; then
    scp "$HARVEST_DIR/lib/embedder.py" "$USER@$WORKER:$REMOTE_DIR/lib/"
    scp "$HARVEST_DIR/lib/packager.py" "$USER@$WORKER:$REMOTE_DIR/lib/"
    scp "$HARVEST_DIR/processor/process_raw.py" "$USER@$WORKER:$REMOTE_DIR/processor/"
fi

# 3. Generate and deploy reference embeddings (if not on NAS yet)
REFERENCE_FILE="/mnt/library/harvest/config/reference_embeddings.json"
if [ ! -f "$REFERENCE_FILE" ]; then
    echo ""
    echo "=== Generating reference embeddings on Tamor ==="
    cd /home/tamor/tamor-core/api
    source venv/bin/activate
    python3 -c "
import sys; sys.path.insert(0, '.')
import base64, json, numpy as np
from core.config import model
test_strings = [
    'The quick brown fox jumps over the lazy dog.',
    'Torah observance in the early church period.',
    'Shalom aleichem, welcome to today s teaching.'
]
refs = {}
for s in test_strings:
    vec = model.encode([s])[0]
    refs[s] = base64.b64encode(vec.astype(np.float32).tobytes()).decode('ascii')
import os; os.makedirs(os.path.dirname('$REFERENCE_FILE'), exist_ok=True)
with open('$REFERENCE_FILE', 'w') as f:
    json.dump(refs, f, indent=2)
print('Reference embeddings saved to NAS')
"
fi

# 4. Verify embeddings (processor only)
if [ "$ROLE" = "processor" ]; then
    echo ""
    echo "=== Verifying embeddings on $WORKER ==="
    ssh "$USER@$WORKER" "source ~/harvest-env/bin/activate && cd ~/harvest-tools && python3 verify_embeddings.py"
fi

echo ""
echo "============================================"
echo "  Deployment to $WORKER complete!"
echo "============================================"
