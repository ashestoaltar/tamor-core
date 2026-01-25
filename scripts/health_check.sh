#!/usr/bin/env bash
set -euo pipefail

# Health check script for Tamor
# Run with sudo for full SMART disk checks

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

WARN_DISK_PERCENT=80
CRIT_DISK_PERCENT=90
WARN_TEMP_C=75
CRIT_TEMP_C=85

echo "=== Tamor Health Check ==="
echo "Date: $(date)"
echo ""

# --- Disk Space ---
echo "--- Disk Space ---"
disk_usage=$(df / --output=pcent | tail -1 | tr -d ' %')
disk_avail=$(df -h / --output=avail | tail -1 | tr -d ' ')

if [ "$disk_usage" -ge "$CRIT_DISK_PERCENT" ]; then
    echo -e "${RED}CRITICAL: Root disk at ${disk_usage}% (${disk_avail} free)${NC}"
    exit_code=2
elif [ "$disk_usage" -ge "$WARN_DISK_PERCENT" ]; then
    echo -e "${YELLOW}WARNING: Root disk at ${disk_usage}% (${disk_avail} free)${NC}"
    exit_code=1
else
    echo -e "${GREEN}OK: Root disk at ${disk_usage}% (${disk_avail} free)${NC}"
    exit_code=0
fi
echo ""

# --- SMART Disk Health ---
echo "--- Disk Health (SMART) ---"
if command -v smartctl &> /dev/null; then
    if [ "$EUID" -eq 0 ]; then
        smart_status=$(smartctl -H /dev/nvme0n1 2>&1)
        if echo "$smart_status" | grep -q "PASSED"; then
            echo -e "${GREEN}OK: NVMe health PASSED${NC}"
        else
            echo -e "${RED}CRITICAL: NVMe health check failed${NC}"
            echo "$smart_status"
            exit_code=2
        fi

        # Show wear level if available
        wear=$(smartctl -A /dev/nvme0n1 2>&1 | grep -i "percentage used" | awk '{print $3}' || true)
        if [ -n "$wear" ]; then
            echo "   NVMe wear level: ${wear}"
        fi
    else
        echo -e "${YELLOW}SKIP: Run with sudo for SMART checks${NC}"
    fi
else
    echo -e "${YELLOW}SKIP: smartctl not installed${NC}"
fi
echo ""

# --- Temperatures ---
echo "--- Temperatures ---"
if command -v sensors &> /dev/null; then
    # NVMe temp
    nvme_temp=$(sensors 2>/dev/null | grep -A2 "nvme-pci" | grep "Composite" | awk '{print $2}' | tr -d '+°C' || echo "")
    if [ -n "$nvme_temp" ]; then
        temp_int=${nvme_temp%.*}
        if [ "$temp_int" -ge "$CRIT_TEMP_C" ]; then
            echo -e "${RED}CRITICAL: NVMe temp ${nvme_temp}°C${NC}"
            exit_code=2
        elif [ "$temp_int" -ge "$WARN_TEMP_C" ]; then
            echo -e "${YELLOW}WARNING: NVMe temp ${nvme_temp}°C${NC}"
            [ "$exit_code" -lt 1 ] && exit_code=1
        else
            echo -e "${GREEN}OK: NVMe temp ${nvme_temp}°C${NC}"
        fi
    fi

    # CPU temp (k10temp for AMD)
    cpu_temp=$(sensors 2>/dev/null | grep -A2 "k10temp" | grep "Tctl" | awk '{print $2}' | tr -d '+°C' || echo "")
    if [ -n "$cpu_temp" ]; then
        temp_int=${cpu_temp%.*}
        if [ "$temp_int" -ge "$CRIT_TEMP_C" ]; then
            echo -e "${RED}CRITICAL: CPU temp ${cpu_temp}°C${NC}"
            exit_code=2
        elif [ "$temp_int" -ge "$WARN_TEMP_C" ]; then
            echo -e "${YELLOW}WARNING: CPU temp ${cpu_temp}°C${NC}"
            [ "$exit_code" -lt 1 ] && exit_code=1
        else
            echo -e "${GREEN}OK: CPU temp ${cpu_temp}°C${NC}"
        fi
    fi

    # GPU temp
    gpu_temp=$(sensors 2>/dev/null | grep -A5 "amdgpu" | grep "edge" | awk '{print $2}' | tr -d '+°C' || echo "")
    if [ -n "$gpu_temp" ]; then
        temp_int=${gpu_temp%.*}
        echo -e "${GREEN}OK: GPU temp ${gpu_temp}°C${NC}"
    fi
else
    echo -e "${YELLOW}SKIP: lm-sensors not installed${NC}"
fi
echo ""

# --- Memory ---
echo "--- Memory ---"
mem_avail=$(free -m | awk '/^Mem:/ {print $7}')
mem_total=$(free -m | awk '/^Mem:/ {print $2}')
mem_percent=$((100 - (mem_avail * 100 / mem_total)))
echo -e "${GREEN}OK: Memory ${mem_percent}% used (${mem_avail}MB available)${NC}"
echo ""

# --- Summary ---
echo "=== Summary ==="
if [ "$exit_code" -eq 0 ]; then
    echo -e "${GREEN}All checks passed${NC}"
elif [ "$exit_code" -eq 1 ]; then
    echo -e "${YELLOW}Warnings detected${NC}"
else
    echo -e "${RED}Critical issues detected${NC}"
fi

exit ${exit_code:-0}
