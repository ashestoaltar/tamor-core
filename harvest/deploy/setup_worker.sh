#!/bin/bash
# Setup script for harvest worker machines.
# Run via SSH from Tamor: ssh harvest@worker 'bash -s' < setup_worker.sh processor
#
# Args:
#   $1 = role: "processor" or "network"

set -e

ROLE="${1:-processor}"
HARVEST_HOME="/home/harvest"
VENV_DIR="$HARVEST_HOME/harvest-env"
NAS_IP="192.168.68.222"
NAS_SHARE="/volume1/library"
NAS_MOUNT="/mnt/library"

echo "============================================"
echo "  Harvest Worker Setup"
echo "  Role: $ROLE"
echo "  Host: $(hostname)"
echo "  Date: $(date)"
echo "============================================"

# 1. System packages
echo ""
echo "=== Installing system packages ==="
sudo apt update -qq
sudo apt install -y -qq python3 python3-pip python3-venv nfs-common git

if [ "$ROLE" = "network" ]; then
    sudo apt install -y -qq ffmpeg
fi

# 2. NAS mount
echo ""
echo "=== Setting up NAS mount ==="
if ! mountpoint -q "$NAS_MOUNT"; then
    sudo mkdir -p "$NAS_MOUNT"

    # Add to fstab if not already there
    if ! grep -q "$NAS_IP" /etc/fstab; then
        echo "$NAS_IP:$NAS_SHARE  $NAS_MOUNT  nfs  defaults,_netdev  0  0" | sudo tee -a /etc/fstab
    fi

    sudo mount -a
fi

# Verify NAS access
if [ -d "$NAS_MOUNT" ]; then
    echo "NAS mounted at $NAS_MOUNT"
    touch "$NAS_MOUNT/harvest/logs/setup-$(hostname)-$(date +%Y%m%d).log" 2>/dev/null \
        && echo "NAS write access: OK" \
        || echo "WARNING: Cannot write to NAS"
else
    echo "ERROR: NAS mount failed!"
    exit 1
fi

# 3. Python virtual environment
echo ""
echo "=== Setting up Python environment ==="
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# 4. Install requirements
echo ""
echo "=== Installing Python packages ==="
pip install --upgrade pip -q

if [ "$ROLE" = "processor" ]; then
    pip install -q sentence-transformers numpy faster-whisper pyyaml
else
    pip install -q requests beautifulsoup4 lxml pyyaml
fi

# Network workers also need yt-dlp
if [ "$ROLE" = "network" ]; then
    pip install -q yt-dlp
fi

# 5. Deploy harvest toolkit
echo ""
echo "=== Deploying harvest toolkit ==="
TOOLKIT_DIR="$HARVEST_HOME/harvest-tools"
mkdir -p "$TOOLKIT_DIR"

# The toolkit files are deployed separately via scp from Tamor
echo "Toolkit directory ready at $TOOLKIT_DIR"
echo "(Files will be deployed via scp from Tamor)"

# 6. Pre-download embedding model (processor only)
if [ "$ROLE" = "processor" ]; then
    echo ""
    echo "=== Pre-downloading embedding model ==="
    python3 -c "
from sentence_transformers import SentenceTransformer
print('Downloading all-MiniLM-L6-v2...')
model = SentenceTransformer('all-MiniLM-L6-v2')
result = model.encode(['test'])
print(f'Model loaded. Embedding dim: {result.shape[1]}')
print('Model cached for future use.')
"
fi

# 7. Create convenience aliases
echo ""
echo "=== Setting up shell aliases ==="
cat >> "$HARVEST_HOME/.bashrc" << 'ALIASES'

# Harvest worker aliases
alias henv='source ~/harvest-env/bin/activate'
alias htools='cd ~/harvest-tools'
alias hlog='tail -f /mnt/library/harvest/logs/$(hostname)/*.log'
alias hstatus='echo "Host: $(hostname)"; echo "NAS: $(df -h /mnt/library | tail -1)"; echo "Jobs: $(ps aux | grep python | grep -v grep | wc -l) running"'
ALIASES

echo ""
echo "============================================"
echo "  Setup complete!"
echo "  Role: $ROLE"
echo "  Python: $(python3 --version)"
echo "  venv: $VENV_DIR"
echo "  NAS: $(df -h $NAS_MOUNT | tail -1)"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Deploy toolkit: scp -r harvest-tools/* harvest@$(hostname):~/harvest-tools/"
echo "  2. Verify embeddings: source ~/harvest-env/bin/activate && python3 ~/harvest-tools/verify_embeddings.py"
echo "  3. Start processing!"
