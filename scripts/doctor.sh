#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== Tamor Doctor =="

# Prefer backend venv if present
if [[ -f "$ROOT/api/venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/api/venv/bin/activate"
fi

echo "-- DB checks"
python3 "$ROOT/api/scripts/db_doctor.py"

echo "-- Backend health/status"
set +e
if curl -fsS "http://127.0.0.1:8080/api/health" >/dev/null 2>&1; then
  curl -fsS "http://127.0.0.1:8080/api/health" | (command -v jq >/dev/null && jq || cat)
else
  echo "[INFO] /api/health not available yet; falling back to /api/status"
  curl -fsS "http://127.0.0.1:8080/api/status" | (command -v jq >/dev/null && jq || cat)
fi
set -e

echo "-- UI checks (optional)"
if [[ -d "$ROOT/ui" ]]; then
  pushd "$ROOT/ui" >/dev/null

  # Install deps if node_modules missing (optional; comment out if you prefer manual)
  if [[ ! -d node_modules ]]; then
    echo "[INFO] ui/node_modules missing; run 'npm ci' if needed"
  fi

  # Only run if scripts exist
  if npm run -s | grep -qE '^\s+lint\b'; then
    npm run -s lint
  else
    echo "[SKIP] npm run lint not defined"
  fi

  if npm run -s | grep -qE '^\s+build\b'; then
    npm run -s build
  else
    echo "[SKIP] npm run build not defined"
  fi

  popd >/dev/null
else
  echo "[SKIP] ui/ directory not found"
fi

echo "== Doctor complete: OK =="
